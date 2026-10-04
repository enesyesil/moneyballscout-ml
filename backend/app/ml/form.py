"""Form as a local-level state-space model (statsmodels UnobservedComponents, Kalman filter).

rating_t = form_t + noise,   form_t = form_{t-1} + drift
Noise and drift variances are estimated once per position group (MLE on the players with the most
appearances), then every player is filtered with those fixed variances. The filtered (causal) state
is "form", with a 90% band from the state variance.
"""

import logging
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.structural import UnobservedComponents

log = logging.getLogger(__name__)

Z90 = 1.645
DEFAULT_PARAMS = np.array([0.45, 0.02])  # sigma2.irregular, sigma2.level


def _model(y: np.ndarray, prior_mean: float, prior_var: float) -> UnobservedComponents:
    mod = UnobservedComponents(y, level="llevel")
    mod.ssm.initialize_known(np.array([prior_mean]), np.array([[prior_var]]))
    return mod


def estimate_group_params(rated: pd.DataFrame, top_n: int = 25) -> dict[str, np.ndarray]:
    params: dict[str, np.ndarray] = {}
    for group, g in rated.groupby("position_group"):
        counts = g["player_id"].value_counts()
        estimates = []
        for pid in counts[counts >= 8].index[:top_n]:
            y = g.loc[g["player_id"] == pid].sort_values("date")["rating"].to_numpy()
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    res = _model(y, y.mean(), 0.5).fit(disp=False)
                estimates.append(res.params)
            except Exception as e:  # noqa: BLE001 - a bad fit for one player should not stop the run
                log.debug("form fit failed for %s: %s", pid, e)
        params[group] = np.median(estimates, axis=0) if len(estimates) >= 3 else DEFAULT_PARAMS
        params[group] = np.maximum(params[group], [0.05, 0.002])
    return params


def filter_player(y: np.ndarray, params: np.ndarray, prior_mean: float) -> tuple[np.ndarray, np.ndarray]:
    mod = _model(y, prior_mean, params[0])
    res = mod.filter(params)
    level = res.filtered_state[0]
    sd = np.sqrt(res.filtered_state_cov[0, 0])
    return level, sd


def compute_form(rated: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return per-appearance form series and the per-group variance parameters."""
    params = estimate_group_params(rated)
    group_mean = rated.groupby("position_group")["rating"].mean().to_dict()
    rows = []
    for (pid, group), g in rated.sort_values("date").groupby(["player_id", "position_group"]):
        y = g["rating"].to_numpy(float)
        level, sd = filter_player(y, params[group], group_mean.get(group, 6.7))
        rows.append(
            pd.DataFrame(
                {
                    "player_id": pid,
                    "fixture_id": g["fixture_id"].to_numpy(),
                    "date": g["date"].to_numpy(),
                    "rating": y,
                    "form": level.round(3),
                    "form_lo": (level - Z90 * sd).round(3),
                    "form_hi": (level + Z90 * sd).round(3),
                    "form_sd": sd.round(3),
                }
            )
        )
    series = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    # a player who changed position group gets two series; keep the latest point per fixture
    if not series.empty:
        series = series.drop_duplicates(["player_id", "fixture_id"], keep="last")
    meta = {g: {"sigma2_irregular": round(float(p[0]), 4), "sigma2_level": round(float(p[1]), 4)} for g, p in params.items()}
    return series, meta
