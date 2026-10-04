"""The Moneyball core: what is a player worth given how he plays?

LightGBM quantile models (P10 / P50 / P90) on log market value, from performance, age, role, contract
and team context. The market value itself is never a feature, and undervaluation is computed from
**out-of-fold** predictions, so the model cannot simply memorise a player's price.
Optuna tunes the P50 model; SHAP TreeExplainer explains each player's valuation. The P10-P90 band is
calibrated with conformalized quantile regression so it really covers ~80% of players.
"""

import logging

import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
import shap
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold

log = logging.getLogger(__name__)
optuna.logging.set_verbosity(optuna.logging.WARNING)

FEATURES = [
    "perf_index", "form", "avg_rating", "age", "age_sq", "minutes_share", "apps",
    "contract_years_left", "team_rating", "league_coef", "pos_GK", "pos_DEF", "pos_MID", "pos_FWD",
]
QUANTILES = {"p10": 0.1, "p50": 0.5, "p90": 0.9}
MIN_ROWS = 40
BASE_PARAMS = {"n_estimators": 300, "learning_rate": 0.05, "num_leaves": 15, "min_child_samples": 10,
               "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.8, "verbose": -1}


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for c in ["perf_index", "form", "avg_rating", "age", "minutes_share", "apps", "contract_years_left", "team_rating", "league_coef"]:
        X[c] = pd.to_numeric(df.get(c), errors="coerce")
    X["age_sq"] = X["age"] ** 2
    for g in ["GK", "DEF", "MID", "FWD"]:
        X[f"pos_{g}"] = (df["position_group"] == g).astype(int)
    return X[FEATURES]


def _model(alpha: float, params: dict) -> lgb.LGBMRegressor:
    return lgb.LGBMRegressor(objective="quantile", alpha=alpha, random_state=0, **params)


def _oof(X: pd.DataFrame, y: np.ndarray, alpha: float, params: dict, folds: int = 5) -> np.ndarray:
    pred = np.zeros(len(y))
    for tr, te in KFold(folds, shuffle=True, random_state=0).split(X):
        m = _model(alpha, params).fit(X.iloc[tr], y[tr])
        pred[te] = m.predict(X.iloc[te])
    return pred


def tune(X: pd.DataFrame, y: np.ndarray, n_trials: int) -> dict:
    def objective(trial: optuna.Trial) -> float:
        params = BASE_PARAMS | {
            "num_leaves": trial.suggest_int("num_leaves", 4, 31),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 40),
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10, log=True),
        }
        return float(np.mean(np.abs(_oof(X, y, 0.5, params, folds=4) - y)))

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=0))
    study.optimize(objective, n_trials=n_trials, timeout=120)
    return BASE_PARAMS | study.best_params


def fit_predict(df: pd.DataFrame, n_trials: int = 20) -> tuple[pd.DataFrame, dict, dict]:
    """df: one row per player with market_value. Returns (valuations, metrics, fitted models)."""
    df = df[df["market_value"] > 0].copy()
    if len(df) < MIN_ROWS:
        return pd.DataFrame(), {"n_players": len(df), "skipped": "not enough valued players"}, {}
    X = build_features(df)
    y = np.log(df["market_value"].to_numpy(float))

    params = tune(X, y, n_trials) if n_trials > 0 else BASE_PARAMS
    oof = {k: _oof(X, y, a, params) for k, a in QUANTILES.items()}
    # quantile models can cross; enforce p10 <= p50 <= p90
    stacked = np.sort(np.vstack([oof["p10"], oof["p50"], oof["p90"]]), axis=0)
    oof = dict(zip(QUANTILES, stacked, strict=True))
    raw_coverage = float(np.mean((y >= oof["p10"]) & (y <= oof["p90"])))
    # conformalized quantile regression: widen the band so out-of-fold coverage hits the nominal 80%
    scores = np.maximum(oof["p10"] - y, y - oof["p90"])
    widen = float(np.quantile(scores, min(1.0, 0.8 * (1 + 1 / len(y)))))
    oof["p10"], oof["p90"] = oof["p10"] - widen, oof["p90"] + widen

    base_X = X[["perf_index", "age"]].fillna(X[["perf_index", "age"]].median())
    base_pred = np.zeros(len(y))
    for tr, te in KFold(5, shuffle=True, random_state=0).split(base_X):
        base_pred[te] = LinearRegression().fit(base_X.iloc[tr], y[tr]).predict(base_X.iloc[te])

    models = {k: _model(a, params).fit(X, y) for k, a in QUANTILES.items()}
    explainer = shap.TreeExplainer(models["p50"])
    sv = explainer.shap_values(X)

    out = pd.DataFrame(index=df.index)
    out["player_id"] = df["player_id"].to_numpy()
    out["market_value"] = df["market_value"].to_numpy()
    for k in QUANTILES:
        out[k] = np.exp(oof[k])
    out["undervalue_score"] = ((out["p50"] - out["market_value"]) / out["p50"]).round(4)
    out["below_p10"] = out["market_value"] < out["p10"]
    base_value = float(np.ravel(explainer.expected_value)[0])
    out["contributions"] = [
        {"base": round(base_value, 4), **{f: round(float(v), 4) for f, v in zip(FEATURES, row, strict=True)}} for row in sv
    ]

    metrics = {
        "n_players": int(len(df)),
        "mae_log_p50": round(float(np.mean(np.abs(oof["p50"] - y))), 4),
        "mae_log_linear_baseline": round(float(np.mean(np.abs(base_pred - y))), 4),
        "interval_coverage_p10_p90": round(float(np.mean((y >= oof["p10"]) & (y <= oof["p90"]))), 3),
        "interval_coverage_before_conformal": round(raw_coverage, 3),
        "conformal_widening_log": round(widen, 4),
        "median_abs_pct_error_p50": round(float(np.median(np.abs(np.exp(oof["p50"] - y) - 1))), 3),
        "params": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in params.items()},
    }
    return out, metrics, models
