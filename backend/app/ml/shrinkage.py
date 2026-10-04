"""Season aggregates with empirical-Bayes shrinkage, percentiles and the Performance Index.

Counts per 90 use a Gamma-Poisson prior (method of moments per position group); success rates use a
Beta-Binomial prior fitted with scipy.stats. A player with 200 minutes therefore no longer tops a
per-90 leaderboard: their numbers are pulled toward the position average until the sample supports them.
"""

import numpy as np
import pandas as pd
from scipy import stats as st

from app.ml.data import positions_config

COUNT_METRICS = [
    "npg", "goals", "assists", "shots_total", "shots_on", "key_passes", "dribbles_success", "duels_won",
    "fouls_drawn", "passes_accurate", "tackles", "interceptions", "blocks", "dribbled_past", "saves",
    "conceded", "pen_saved",
]
# rate name -> (successes, attempts)
RATE_METRICS = {
    "pass_pct": ("passes_accurate", "passes_total"),
    "duel_pct": ("duels_won", "duels_total"),
    "dribble_pct": ("dribbles_success", "dribbles_attempts"),
    "save_pct": ("saves", "shots_faced"),
}
MIN_MINUTES_RANKED = 450


def season_totals(stats: pd.DataFrame) -> pd.DataFrame:
    df = stats
    sums = ["minutes", *COUNT_METRICS, "passes_total", "duels_total", "dribbles_attempts", "shots_faced"]
    sums = list(dict.fromkeys(sums))
    agg = df.groupby("player_id")[sums].sum()
    agg["apps"] = df.groupby("player_id").size()
    agg["position_group"] = df.groupby("player_id")["position_group"].agg(lambda s: s.value_counts().index[0])
    agg["team_id"] = df.sort_values("date").groupby("player_id")["team_id"].last()
    return agg


def _gamma_prior(k: pd.Series, t: pd.Series) -> tuple[float, float]:
    """Method-of-moments Gamma prior for per-90 rates; returns (alpha, beta) in per-90 units."""
    mask = t >= 3
    if mask.sum() < 5 or k[mask].sum() == 0:
        mu = (k.sum() + 0.5) / (t.sum() + 1)
        return mu * 2, 2.0
    k, t = k[mask], t[mask]
    mu = k.sum() / t.sum()
    rates = k / t
    var_r = np.average((rates - mu) ** 2, weights=t)
    tau2 = max(var_r - mu / t.mean(), (0.1 * mu) ** 2, 1e-6)
    return mu**2 / tau2, mu / tau2


def _beta_prior(s: pd.Series, n: pd.Series) -> tuple[float, float]:
    mask = n >= 30
    p = (s[mask] / n[mask]).clip(0.01, 0.99)
    if len(p) >= 8 and p.std() > 0:
        a, b, _, _ = st.beta.fit(p, floc=0, fscale=1)
        return float(a), float(b)
    mean = (s.sum() + 1) / (n.sum() + 2)
    return mean * 20, (1 - mean) * 20


def shrink(totals: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (raw per-90 + rates, shrunk per-90 + rates)."""
    raw = pd.DataFrame(index=totals.index)
    shrunk = pd.DataFrame(index=totals.index)
    t = totals["minutes"] / 90
    for group, idx in totals.groupby("position_group").groups.items():
        tg = t.loc[idx]
        for m in COUNT_METRICS:
            k = totals.loc[idx, m]
            a, b = _gamma_prior(k, tg)
            raw.loc[idx, m] = k / tg.replace(0, np.nan)
            shrunk.loc[idx, m] = (a + k) / (b + tg)
        for m, (succ, att) in RATE_METRICS.items():
            s, n = totals.loc[idx, succ], totals.loc[idx, att]
            a, b = _beta_prior(s, n)
            raw.loc[idx, m] = s / n.replace(0, np.nan)
            shrunk.loc[idx, m] = (a + s) / (a + b + n)
    return raw, shrunk


def percentiles(shrunk: pd.DataFrame, totals: pd.DataFrame) -> pd.DataFrame:
    """Percentile of each player's shrunk metric vs ranked players (>= 450 min) in the same group."""
    cfg = positions_config()["groups"]
    out = pd.DataFrame(index=shrunk.index, dtype=float)
    for group, idx in totals.groupby("position_group").groups.items():
        ref_idx = [i for i in idx if totals.at[i, "minutes"] >= MIN_MINUTES_RANKED] or list(idx)
        inverse = set(cfg.get(group, {}).get("inverse", []))
        for m in shrunk.columns:
            ref = np.sort(shrunk.loc[ref_idx, m].dropna().to_numpy())
            if len(ref) == 0:
                continue
            vals = shrunk.loc[idx, m].to_numpy()
            pct = np.searchsorted(ref, vals, side="right") / len(ref) * 100
            out.loc[idx, m] = 100 - pct if m in inverse else pct
    return out.clip(0, 100).round(1)


def performance_index(shrunk: pd.DataFrame, totals: pd.DataFrame, action_values: pd.Series) -> pd.Series:
    """Position-specific weighted z-score composite, scaled to mean 50 / sd 15 within each group.

    Weight of a metric = |value of one unit| x its spread across the group, i.e. how much a
    one-SD difference in that metric moves goal difference.
    """
    cfg = positions_config()["groups"]
    # outcome-type metrics are not process actions; give them their outcome credit
    unit_value = {"npg": 1.0, "goals": 1.0, "assists": 0.6, "conceded": 0.3,
                  "shots_total": float(abs(action_values.get("shots_off", 0.02)))}
    pi = pd.Series(index=totals.index, dtype=float)
    for group, idx in totals.groupby("position_group").groups.items():
        metrics = cfg.get(group, cfg["MID"])["metrics"]
        inverse = set(cfg.get(group, {}).get("inverse", []))
        ref = [i for i in idx if totals.at[i, "minutes"] >= MIN_MINUTES_RANKED] or list(idx)
        zs, ws = [], []
        for m in metrics:
            col = shrunk.loc[idx, m].astype(float)
            mu, sd = shrunk.loc[ref, m].mean(), shrunk.loc[ref, m].std()
            if not sd or np.isnan(sd):
                continue
            z = (col - mu) / sd
            zs.append(-z if m in inverse else z)
            if m in RATE_METRICS:  # rates have no per-unit value; weight like a typical metric
                w = float(np.median(ws)) if ws else 0.05
            else:
                w = unit_value.get(m, float(abs(action_values.get(m, 0.03)))) * sd
            ws.append(w)
        if not zs:
            continue
        comp = sum(w * z for w, z in zip(ws, zs, strict=True)) / sum(ws)
        ref_comp = comp.loc[ref]
        pi.loc[idx] = 50 + 15 * (comp - ref_comp.mean()) / (ref_comp.std() or 1)
    return pi.round(1)
