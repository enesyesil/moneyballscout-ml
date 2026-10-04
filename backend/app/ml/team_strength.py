"""Team strength with penaltyblog's Dixon-Coles goal model (time-decayed).

Gives attack/defence ratings, W/D/L probabilities for upcoming fixtures and expected points for
played ones. Expected points for played matches come from the same fit (in-sample) - fine for
ranking teams and managers, not for betting.
"""

import numpy as np
import pandas as pd
import penaltyblog as pb
from scipy.stats import poisson

XI = 0.0018  # time-decay rate per day (penaltyblog default, ~ half-life of a year)
MIN_MATCHES = 30


class TeamStrengthModel:
    def __init__(self, fixtures: pd.DataFrame):
        played = fixtures[fixtures["finished"]].dropna(subset=["home_goals", "away_goals"]).sort_values("date")
        self.played = played
        self.ok = len(played) >= MIN_MATCHES
        self.model = None
        if not self.ok:
            return
        weights = pb.models.dixon_coles_weights(played["date"].dt.tz_localize(None), xi=XI)
        self.model = pb.models.DixonColesGoalModel(
            played["home_goals"].astype(int).to_numpy(),
            played["away_goals"].astype(int).to_numpy(),
            played["home_team_id"].astype(str).to_numpy(),
            played["away_team_id"].astype(str).to_numpy(),
            weights,
        )
        self.model.fit()

    @property
    def params(self) -> dict:
        return dict(self.model.params) if self.model else {}

    def team_params(self, team_id: int) -> tuple[float, float]:
        p = self.params
        return p.get(f"attack_{team_id}", 0.0), p.get(f"defence_{team_id}", 0.0)

    def ratings(self) -> pd.DataFrame:
        """Attack, defence and overall rating per team (rating = attack - defence, higher = better)."""
        teams = sorted(set(self.played["home_team_id"]) | set(self.played["away_team_id"]))
        rows = []
        for t in teams:
            att, dfc = self.team_params(t)
            rows.append({"team_id": int(t), "attack": att, "defence": dfc})
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df["rating"] = df["attack"] - df["defence"]
        return df

    def predict(self, home_id: int, away_id: int) -> dict:
        try:
            g = self.model.predict(str(home_id), str(away_id))
        except ValueError:
            # extreme mismatches can push the Dixon-Coles low-score correction negative;
            # fall back to the same fitted rates with independent Poisson goals
            return self._poisson_predict(home_id, away_id)
        return {
            "home_win": float(g.home_win),
            "draw": float(g.draw),
            "away_win": float(g.away_win),
            "exp_home_goals": float(g.home_goal_expectation),
            "exp_away_goals": float(g.away_goal_expectation),
        }


    def _poisson_predict(self, home_id: int, away_id: int) -> dict:
        p = self.params
        ah, dh = self.team_params(home_id)
        aa, da = self.team_params(away_id)
        lam_h = float(np.exp(p.get("home_advantage", 0.0) + ah + da))
        lam_a = float(np.exp(aa + dh))
        goals = np.arange(15)
        grid = np.outer(poisson.pmf(goals, lam_h), poisson.pmf(goals, lam_a))
        grid /= grid.sum()
        return {
            "home_win": float(np.tril(grid, -1).sum()),
            "draw": float(np.trace(grid)),
            "away_win": float(np.triu(grid, 1).sum()),
            "exp_home_goals": lam_h,
            "exp_away_goals": lam_a,
        }


def points(gf: float, ga: float) -> int:
    return 3 if gf > ga else 1 if gf == ga else 0


def team_match_points(model: TeamStrengthModel) -> pd.DataFrame:
    """Per team-match points vs expected points."""
    rows = []
    for fx in model.played.itertuples():
        p = model.predict(fx.home_team_id, fx.away_team_id)
        xh = 3 * p["home_win"] + p["draw"]
        xa = 3 * p["away_win"] + p["draw"]
        rows.append({"fixture_id": fx.id, "date": fx.date, "team_id": fx.home_team_id, "opponent_id": fx.away_team_id,
                     "gf": fx.home_goals, "ga": fx.away_goals, "pts": points(fx.home_goals, fx.away_goals), "xpts": xh})
        rows.append({"fixture_id": fx.id, "date": fx.date, "team_id": fx.away_team_id, "opponent_id": fx.home_team_id,
                     "gf": fx.away_goals, "ga": fx.home_goals, "pts": points(fx.away_goals, fx.home_goals), "xpts": xa})
    return pd.DataFrame(rows)


def predict_fixtures(model: TeamStrengthModel, fixtures: pd.DataFrame) -> pd.DataFrame:
    known = set(model.played["home_team_id"]) | set(model.played["away_team_id"])
    rows = []
    for fx in fixtures.itertuples():
        if fx.home_team_id in known and fx.away_team_id in known:
            rows.append({"fixture_id": fx.id, **model.predict(fx.home_team_id, fx.away_team_id)})
    return pd.DataFrame(rows)
