"""Learn what each on-ball action is worth from what actually wins matches.

API-Football has no event coordinates, so a full possession-value model (VAEP/xT) is out of reach.
Instead: one row per team per match, target = goal difference, features = (team - opponent) action
counts. A sign-constrained ridge (scikit-learn `Ridge(positive=True)` on sign-flipped features) gives a
value per action, which is blended with priors while the sample is small.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_score

HERE = Path(__file__).parent


@lru_cache
def weights_config() -> dict:
    return yaml.safe_load((HERE / "weights.yaml").read_text())


def action_names() -> list[str]:
    return list(weights_config()["process_actions"])


def priors() -> pd.Series:
    return pd.Series({k: v["prior"] for k, v in weights_config()["process_actions"].items()})


def team_match_table(stats: pd.DataFrame) -> pd.DataFrame:
    """(team - opponent) action differences and goal difference, one row per team per match."""
    actions = action_names()
    team = stats.groupby(["fixture_id", "team_id"])[actions].sum()
    goals = stats.groupby(["fixture_id", "team_id"])[["team_goals", "opp_goals"]].first()
    team = team.join(goals).reset_index()
    opp = team[["fixture_id", "team_id", *actions]].rename(columns={"team_id": "opp_id", **{a: f"opp_{a}" for a in actions}})
    merged = team.merge(opp, on="fixture_id")
    merged = merged[merged["team_id"] != merged["opp_id"]]
    out = pd.DataFrame({a: merged[a] - merged[f"opp_{a}"] for a in actions})
    out["goal_diff"] = merged["team_goals"] - merged["opp_goals"]
    return out.dropna()


def learn(stats: pd.DataFrame, alpha: float = 10.0) -> tuple[pd.Series, dict]:
    """Return blended action values and fit metrics."""
    cfg = weights_config()
    prior = priors()
    actions = list(prior.index)
    table = team_match_table(stats) if not stats.empty else pd.DataFrame()
    n_matches = len(table) // 2
    if n_matches < 20:
        return prior, {"n_matches": n_matches, "blend_weight": 0.0}

    signs = pd.Series({k: v["sign"] for k, v in cfg["process_actions"].items()})
    X = table[actions].to_numpy(float) * signs.to_numpy()
    scale = X.std(axis=0)
    scale[scale == 0] = 1.0
    y = table["goal_diff"].to_numpy(float)
    model = Ridge(alpha=alpha, positive=True, fit_intercept=False)
    model.fit(X / scale, y)
    learned = pd.Series(model.coef_ / scale * signs.to_numpy(), index=actions)

    half = cfg["blend_half_life_matches"]
    w = n_matches / (n_matches + half)
    blended = w * learned + (1 - w) * prior
    r2 = cross_val_score(Ridge(alpha=alpha, positive=True, fit_intercept=False), X / scale, y, cv=5, scoring="r2").mean()
    metrics = {"n_matches": n_matches, "blend_weight": round(w, 3), "cv_r2_goal_diff": round(float(r2), 4)}
    return blended, metrics | {"learned": learned.round(5).to_dict()}


def player_process_values(stats: pd.DataFrame, values: pd.Series) -> pd.DataFrame:
    """Per-appearance value of each action (count x value)."""
    return stats[values.index].astype(float).mul(values, axis=1)


def components_of(contrib: pd.DataFrame) -> pd.DataFrame:
    groups = weights_config()["components"]
    return pd.DataFrame({g: contrib[[a for a in acts if a in contrib]].sum(axis=1) for g, acts in groups.items()})


def priors_array() -> np.ndarray:
    return priors().to_numpy()
