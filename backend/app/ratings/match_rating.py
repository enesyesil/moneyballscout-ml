"""Per-match player rating on the familiar 3-10 scale.

raw = process value (learned action values x counts, scaled by opponent strength)
      + outcome credit (goals, assists, clean sheets, share of goals conceded)
Raw scores are mapped to the rating scale within each position group with scikit-learn's
QuantileTransformer, so defenders are not systematically rated below forwards, and short cameos are
shrunk toward a neutral anchor.
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import QuantileTransformer

from app.ratings.action_values import components_of, player_process_values, weights_config


def outcome_credit(stats: pd.DataFrame) -> pd.DataFrame:
    o = weights_config()["outcomes"]
    defensive = stats["position_group"].isin(["GK", "DEF"])
    share = (stats["minutes"].clip(upper=90) / 90).where(defensive, 0.0)
    cs_bonus = stats["position_group"].map(o["clean_sheet"]).fillna(0.0)
    clean = (stats["opp_goals"] == 0) & (stats["minutes"] >= 60)
    return pd.DataFrame(
        {
            "goals": stats["npg"] * o["goal"] + stats["pen_scored"] * o["penalty_goal"],
            "assists": stats["assists"] * o["assist"],
            "defensive_outcome": stats["opp_goals"].fillna(0) * share * o["conceded_share"] + clean * cs_bonus,
        },
        index=stats.index,
    )


def rate(stats: pd.DataFrame, values: pd.Series, opp_strength_z: dict[int, float] | None = None) -> pd.DataFrame:
    """Return one rating row per appearance with >= min_minutes."""
    scale = weights_config()["rating_scale"]
    stats = stats[stats["minutes"] >= scale["min_minutes"]].copy()
    if stats.empty:
        return pd.DataFrame()

    contrib = player_process_values(stats, values)
    comps = components_of(contrib)
    opp_z = stats["opponent_id"].map(opp_strength_z or {}).fillna(0.0).clip(-2.5, 2.5)
    opp_factor = 1 + scale["opponent_adjust"] * opp_z
    comps = comps.mul(opp_factor, axis=0)
    outcome = outcome_credit(stats)
    comps = comps.join(outcome)
    raw = comps.sum(axis=1)

    rating = pd.Series(index=stats.index, dtype=float)
    for group, idx in stats.groupby("position_group").groups.items():
        r = raw.loc[idx].to_numpy().reshape(-1, 1)
        if len(r) < 5:
            z = (r - r.mean()) / (r.std() + 1e-9)
        else:
            qt = QuantileTransformer(output_distribution="normal", n_quantiles=min(1000, len(r)), random_state=0)
            z = qt.fit_transform(r)
        rating.loc[idx] = scale["mean"] + scale["sd"] * z.ravel()

    w = (stats["minutes"] / scale["full_weight_minutes"]).clip(upper=1.0)
    rating = w * rating + (1 - w) * scale["cameo_anchor"]
    rating = rating.clip(scale["min"], scale["max"]).round(2)

    out = stats[["fixture_id", "player_id", "team_id", "position_group", "minutes", "date", "api_rating", "opponent_id"]].copy()
    out["rating"] = rating
    out["raw_score"] = raw.round(4)
    out["opp_factor"] = opp_factor.round(3)
    out["components"] = [
        {k: round(float(v), 4) for k, v in row.items()} | {"opponent_factor": round(float(f), 3)}
        for row, f in zip(comps.to_dict("records"), opp_factor, strict=True)
    ]
    return out


def validation_metrics(rated: pd.DataFrame) -> dict:
    both = rated.dropna(subset=["api_rating"])
    corr = float(np.corrcoef(both["rating"], both["api_rating"])[0, 1]) if len(both) > 10 else None
    by_group = rated.groupby("position_group")["rating"].mean().round(3).to_dict()
    return {
        "n_ratings": int(len(rated)),
        "mean": round(float(rated["rating"].mean()), 3),
        "sd": round(float(rated["rating"].std()), 3),
        "corr_with_api_rating": None if corr is None else round(corr, 3),
        "mean_by_group": by_group,
    }
