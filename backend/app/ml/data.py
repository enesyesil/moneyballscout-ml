"""DataFrame views over the source tables, shared by ratings and models."""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.loaders import FINISHED
from app.models import Fixture, Player, PlayerMatchStats

HERE = Path(__file__).parent


@lru_cache
def positions_config() -> dict:
    return yaml.safe_load((HERE / "positions.yaml").read_text())


def fixtures_df(session: Session) -> pd.DataFrame:
    df = pd.read_sql(select(Fixture), session.bind)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["finished"] = df["status"].isin(FINISHED)
    return df


def match_stats_df(session: Session) -> pd.DataFrame:
    """One row per player appearance, joined with match context and derived counts."""
    stats = pd.read_sql(select(PlayerMatchStats), session.bind)
    if stats.empty:
        return stats
    fx = fixtures_df(session)[["id", "date", "season", "league_id", "home_team_id", "away_team_id", "home_goals", "away_goals"]]
    df = stats.merge(fx.rename(columns={"id": "fixture_id"}), on="fixture_id", how="inner")
    home = df["team_id"] == df["home_team_id"]
    df["is_home"] = home
    df["opponent_id"] = np.where(home, df["away_team_id"], df["home_team_id"])
    df["team_goals"] = np.where(home, df["home_goals"], df["away_goals"]).astype(float)
    df["opp_goals"] = np.where(home, df["away_goals"], df["home_goals"]).astype(float)

    players = pd.read_sql(select(Player.id, Player.position, Player.birth_date), session.bind)
    df = df.merge(players.rename(columns={"id": "player_id", "position": "profile_position"}), on="player_id", how="left")
    cfg = positions_config()
    df["position_group"] = (
        df["position"].map(cfg["match_position"]).fillna(df["profile_position"].map(cfg["profile_position"])).fillna("MID")
    )
    df["shots_off"] = (df["shots_total"] - df["shots_on"]).clip(lower=0)
    df["dribbles_failed"] = (df["dribbles_attempts"] - df["dribbles_success"]).clip(lower=0)
    df["passes_failed"] = (df["passes_total"] - df["passes_accurate"]).clip(lower=0)
    df["duels_lost"] = (df["duels_total"] - df["duels_won"]).clip(lower=0)
    df["npg"] = (df["goals"] - df["pen_scored"]).clip(lower=0)
    df["key_passes"] = df["passes_key"]
    df["shots_faced"] = df["saves"] + df["conceded"]
    return df.sort_values(["date", "fixture_id"]).reset_index(drop=True)


def player_position_groups(session: Session) -> dict[int, str]:
    cfg = positions_config()
    rows = session.execute(select(Player.id, Player.position)).all()
    return {pid: cfg["profile_position"].get(pos or "", "MID") for pid, pos in rows}
