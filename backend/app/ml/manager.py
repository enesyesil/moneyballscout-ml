"""Manager rating per coach tenure (0-100).

  points over expectation  - actual points minus Dixon-Coles expected points, per match
  squad efficiency         - points per game above what the squad's market value predicts
  player development       - how much players' match ratings rose during the tenure
Each part is shrunk toward 0 by matches managed (empirical Bayes style), then combined.
"""

import numpy as np
import pandas as pd

SHRINK_MATCHES = 10
WEIGHTS = {"pts_over_exp": 0.6, "squad_efficiency": 0.25, "development": 0.15}


def _z(s: pd.Series) -> pd.Series:
    sd = s.std()
    return (s - s.mean()) / sd if sd and not np.isnan(sd) else s * 0


def rate_managers(
    tenures: pd.DataFrame,  # coach_id, team_id, start, end
    team_points: pd.DataFrame,  # fixture_id, date, team_id, pts, xpts
    squad_values: pd.Series,  # team_id -> squad value (EUR)
    ratings: pd.DataFrame,  # fixture_id, player_id, team_id, date, rating
) -> pd.DataFrame:
    if tenures.empty or team_points.empty:
        return pd.DataFrame()
    team_points = team_points.copy()
    team_points["day"] = pd.to_datetime(team_points["date"], utc=True).dt.tz_localize(None).dt.normalize()

    # squad efficiency: residual of ppg on log squad value, per team
    per_team = team_points.groupby("team_id").agg(ppg=("pts", "mean"), n=("pts", "size"))
    per_team["log_value"] = np.log(squad_values.reindex(per_team.index).astype(float))
    fit = per_team.dropna()
    if len(fit) >= 5:
        slope, intercept = np.polyfit(fit["log_value"], fit["ppg"], 1)
    else:
        slope, intercept = 0.0, per_team["ppg"].mean()

    rows = []
    for t in tenures.itertuples():
        start = pd.Timestamp(t.start) if pd.notna(t.start) else pd.Timestamp.min
        end = pd.Timestamp(t.end) if pd.notna(t.end) else pd.Timestamp.max
        m = team_points[(team_points["team_id"] == t.team_id) & (team_points["day"] >= start) & (team_points["day"] <= end)]
        if m.empty:
            continue
        m = m.sort_values("day")
        n = len(m)
        shrink = n / (n + SHRINK_MATCHES)
        poe = (m["pts"] - m["xpts"]).mean() * shrink
        log_value = np.log(squad_values.get(t.team_id, np.nan)) if squad_values.get(t.team_id) else np.nan
        squad_eff = None if np.isnan(log_value) else (m["pts"].mean() - (intercept + slope * log_value)) * shrink

        r = ratings[ratings["fixture_id"].isin(m["fixture_id"]) & (ratings["team_id"] == t.team_id)].sort_values("date")
        dev_vals = []
        for _, pr in r.groupby("player_id"):
            if len(pr) >= 6:
                half = len(pr) // 2
                dev_vals.append(pr["rating"].iloc[half:].mean() - pr["rating"].iloc[:half].mean())
        development = float(np.mean(dev_vals)) * shrink if dev_vals else None

        series = [{"date": d.date().isoformat(), "pts": int(p), "xpts": round(float(x), 3)}
                  for d, p, x in zip(m["day"], m["pts"], m["xpts"], strict=True)]
        rows.append({
            "coach_id": t.coach_id, "team_id": t.team_id, "tenure_start": None if pd.isna(t.start) else t.start,
            "matches": n, "ppg": round(m["pts"].mean(), 3), "xppg": round(m["xpts"].mean(), 3),
            "pts_over_exp": round(float(poe), 4),
            "squad_efficiency": None if squad_eff is None else round(float(squad_eff), 4),
            "development": None if development is None else round(development, 4),
            "series": series,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    comp = sum(w * _z(df[k].astype(float).fillna(0.0)) for k, w in WEIGHTS.items())
    df["score"] = (50 + 15 * _z(comp)).clip(0, 100).round(1)
    return df
