"""ORM tables.

Source tables mirror API-Football / Transfermarkt. Derived tables (ratings, aggregates, model outputs)
are fully rewritten by each pipeline run and point at the `model_runs` row that produced them.
"""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# ---------------------------------------------------------------- source: API-Football


class League(Base):
    __tablename__ = "leagues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # api-football id
    name: Mapped[str] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(80))
    logo: Mapped[str | None] = mapped_column(String(300))


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str | None] = mapped_column(String(10))
    logo: Mapped[str | None] = mapped_column(String(300))
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id"))


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    firstname: Mapped[str | None] = mapped_column(String(120))
    lastname: Mapped[str | None] = mapped_column(String(120))
    birth_date: Mapped[date | None] = mapped_column(Date)
    nationality: Mapped[str | None] = mapped_column(String(80))
    height_cm: Mapped[int | None] = mapped_column(Integer)
    photo: Mapped[str | None] = mapped_column(String(300))
    position: Mapped[str | None] = mapped_column(String(20))  # Goalkeeper / Defender / Midfielder / Attacker
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)


class Coach(Base):
    __tablename__ = "coaches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    nationality: Mapped[str | None] = mapped_column(String(80))
    birth_date: Mapped[date | None] = mapped_column(Date)
    photo: Mapped[str | None] = mapped_column(String(300))


class CoachTenure(Base):
    __tablename__ = "coach_tenures"
    __table_args__ = (UniqueConstraint("coach_id", "team_id", "start"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("coaches.id"), index=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    start: Mapped[date | None] = mapped_column(Date)
    end: Mapped[date | None] = mapped_column(Date)


class Fixture(Base):
    __tablename__ = "fixtures"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    round: Mapped[str | None] = mapped_column(String(60))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(10))  # NS, FT, AET, PEN, PST, ...
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    home_goals: Mapped[int | None] = mapped_column(Integer)
    away_goals: Mapped[int | None] = mapped_column(Integer)
    player_stats_synced: Mapped[bool] = mapped_column(Boolean, default=False)


class PlayerMatchStats(Base):
    __tablename__ = "player_match_stats"
    __table_args__ = (UniqueConstraint("fixture_id", "player_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(ForeignKey("fixtures.id"), index=True)
    player_id: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    player_name: Mapped[str | None] = mapped_column(String(120))
    position: Mapped[str | None] = mapped_column(String(2))  # G / D / M / F
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    substitute: Mapped[bool] = mapped_column(Boolean, default=False)
    captain: Mapped[bool] = mapped_column(Boolean, default=False)
    api_rating: Mapped[float | None] = mapped_column(Float)
    offsides: Mapped[int] = mapped_column(Integer, default=0)
    shots_total: Mapped[int] = mapped_column(Integer, default=0)
    shots_on: Mapped[int] = mapped_column(Integer, default=0)
    goals: Mapped[int] = mapped_column(Integer, default=0)
    conceded: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    passes_total: Mapped[int] = mapped_column(Integer, default=0)
    passes_key: Mapped[int] = mapped_column(Integer, default=0)
    passes_accurate: Mapped[int] = mapped_column(Integer, default=0)
    tackles: Mapped[int] = mapped_column(Integer, default=0)
    blocks: Mapped[int] = mapped_column(Integer, default=0)
    interceptions: Mapped[int] = mapped_column(Integer, default=0)
    duels_total: Mapped[int] = mapped_column(Integer, default=0)
    duels_won: Mapped[int] = mapped_column(Integer, default=0)
    dribbles_attempts: Mapped[int] = mapped_column(Integer, default=0)
    dribbles_success: Mapped[int] = mapped_column(Integer, default=0)
    dribbled_past: Mapped[int] = mapped_column(Integer, default=0)
    fouls_drawn: Mapped[int] = mapped_column(Integer, default=0)
    fouls_committed: Mapped[int] = mapped_column(Integer, default=0)
    yellow: Mapped[int] = mapped_column(Integer, default=0)
    red: Mapped[int] = mapped_column(Integer, default=0)
    pen_won: Mapped[int] = mapped_column(Integer, default=0)
    pen_committed: Mapped[int] = mapped_column(Integer, default=0)
    pen_scored: Mapped[int] = mapped_column(Integer, default=0)
    pen_missed: Mapped[int] = mapped_column(Integer, default=0)
    pen_saved: Mapped[int] = mapped_column(Integer, default=0)


class ApiUsage(Base):
    __tablename__ = "api_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    day: Mapped[date] = mapped_column(Date, index=True)
    endpoint: Mapped[str] = mapped_column(String(60))
    params: Mapped[str] = mapped_column(String(300))
    status: Mapped[int] = mapped_column(Integer)
    remaining: Mapped[int | None] = mapped_column(Integer)


# ---------------------------------------------------------------- source: Transfermarkt


class TMPlayer(Base):
    __tablename__ = "tm_players"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # transfermarkt player_id
    name: Mapped[str] = mapped_column(String(120), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date, index=True)
    club_name: Mapped[str | None] = mapped_column(String(160))
    competition_id: Mapped[str | None] = mapped_column(String(10), index=True)
    position: Mapped[str | None] = mapped_column(String(40))
    sub_position: Mapped[str | None] = mapped_column(String(40))
    contract_expiration: Mapped[date | None] = mapped_column(Date)
    market_value: Mapped[float | None] = mapped_column(Float)
    image_url: Mapped[str | None] = mapped_column(String(300))


class MarketValue(Base):
    __tablename__ = "market_values"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tm_player_id: Mapped[int] = mapped_column(Integer, index=True)
    date: Mapped[date] = mapped_column(Date)
    value_eur: Mapped[float] = mapped_column(Float)


class PlayerLink(Base):
    __tablename__ = "player_links"
    player_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tm_player_id: Mapped[int] = mapped_column(Integer, index=True)
    confidence: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(20))


class PlayerLinkOverride(Base):
    __tablename__ = "player_link_overrides"
    player_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tm_player_id: Mapped[int | None] = mapped_column(Integer)  # NULL = force "no match"


# ---------------------------------------------------------------- derived


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="running")
    git_sha: Mapped[str | None] = mapped_column(String(40))
    data_cutoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64))
    artifact_prefix: Mapped[str | None] = mapped_column(String(200))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    params: Mapped[dict] = mapped_column(JSON, default=dict)


class MatchRating(Base):
    __tablename__ = "match_ratings"
    __table_args__ = (UniqueConstraint("fixture_id", "player_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_run_id: Mapped[int] = mapped_column(Integer, index=True)
    fixture_id: Mapped[int] = mapped_column(Integer, index=True)
    player_id: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer)
    position_group: Mapped[str] = mapped_column(String(3))
    minutes: Mapped[int] = mapped_column(Integer)
    rating: Mapped[float] = mapped_column(Float)
    raw_score: Mapped[float] = mapped_column(Float)
    components: Mapped[dict] = mapped_column(JSON, default=dict)


class PlayerForm(Base):
    __tablename__ = "player_form"
    __table_args__ = (UniqueConstraint("player_id", "fixture_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_run_id: Mapped[int] = mapped_column(Integer)
    player_id: Mapped[int] = mapped_column(Integer, index=True)
    fixture_id: Mapped[int] = mapped_column(Integer)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rating: Mapped[float] = mapped_column(Float)
    form: Mapped[float] = mapped_column(Float)
    form_lo: Mapped[float] = mapped_column(Float)
    form_hi: Mapped[float] = mapped_column(Float)


class PlayerSeasonAgg(Base):
    __tablename__ = "player_season_agg"
    player_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_run_id: Mapped[int] = mapped_column(Integer)
    season: Mapped[int] = mapped_column(Integer)
    team_id: Mapped[int | None] = mapped_column(Integer, index=True)
    position_group: Mapped[str] = mapped_column(String(3), index=True)
    age: Mapped[float | None] = mapped_column(Float)
    apps: Mapped[int] = mapped_column(Integer)
    minutes: Mapped[int] = mapped_column(Integer)
    goals: Mapped[int] = mapped_column(Integer)
    assists: Mapped[int] = mapped_column(Integer)
    avg_rating: Mapped[float | None] = mapped_column(Float)
    form: Mapped[float | None] = mapped_column(Float)
    form_sd: Mapped[float | None] = mapped_column(Float)
    expected_next: Mapped[float | None] = mapped_column(Float)
    perf_index: Mapped[float | None] = mapped_column(Float, index=True)
    market_value: Mapped[float | None] = mapped_column(Float)
    contract_expiration: Mapped[date | None] = mapped_column(Date)
    per90: Mapped[dict] = mapped_column(JSON, default=dict)
    shrunk_per90: Mapped[dict] = mapped_column(JSON, default=dict)
    percentiles: Mapped[dict] = mapped_column(JSON, default=dict)


class TeamStrength(Base):
    __tablename__ = "team_strength"
    team_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_run_id: Mapped[int] = mapped_column(Integer)
    attack: Mapped[float] = mapped_column(Float)
    defence: Mapped[float] = mapped_column(Float)
    rating: Mapped[float] = mapped_column(Float)
    played: Mapped[int] = mapped_column(Integer)
    points: Mapped[int] = mapped_column(Integer)
    xpts: Mapped[float] = mapped_column(Float)
    goals_for: Mapped[int] = mapped_column(Integer)
    goals_against: Mapped[int] = mapped_column(Integer)
    avg_player_rating: Mapped[float | None] = mapped_column(Float)
    squad_value: Mapped[float | None] = mapped_column(Float)
    series: Mapped[list] = mapped_column(JSON, default=list)  # per-match points vs xpts


class MatchPrediction(Base):
    __tablename__ = "match_predictions"
    fixture_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_run_id: Mapped[int] = mapped_column(Integer)
    home_win: Mapped[float] = mapped_column(Float)
    draw: Mapped[float] = mapped_column(Float)
    away_win: Mapped[float] = mapped_column(Float)
    exp_home_goals: Mapped[float] = mapped_column(Float)
    exp_away_goals: Mapped[float] = mapped_column(Float)


class Valuation(Base):
    __tablename__ = "valuations"
    player_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_run_id: Mapped[int] = mapped_column(Integer)
    market_value: Mapped[float] = mapped_column(Float)
    p10: Mapped[float] = mapped_column(Float)
    p50: Mapped[float] = mapped_column(Float)
    p90: Mapped[float] = mapped_column(Float)
    undervalue_score: Mapped[float] = mapped_column(Float, index=True)  # (p50 - actual) / p50
    below_p10: Mapped[bool] = mapped_column(Boolean, default=False)
    contributions: Mapped[dict] = mapped_column(JSON, default=dict)  # SHAP, log-value space


class SimilarPlayer(Base):
    __tablename__ = "similar_players"
    __table_args__ = (UniqueConstraint("player_id", "similar_player_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_run_id: Mapped[int] = mapped_column(Integer)
    player_id: Mapped[int] = mapped_column(Integer, index=True)
    similar_player_id: Mapped[int] = mapped_column(Integer)
    similarity: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)


class ManagerRating(Base):
    __tablename__ = "manager_ratings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_run_id: Mapped[int] = mapped_column(Integer)
    coach_id: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer)
    tenure_start: Mapped[date | None] = mapped_column(Date)
    matches: Mapped[int] = mapped_column(Integer)
    ppg: Mapped[float] = mapped_column(Float)
    xppg: Mapped[float] = mapped_column(Float)
    pts_over_exp: Mapped[float] = mapped_column(Float)  # per match, shrunk
    squad_efficiency: Mapped[float | None] = mapped_column(Float)
    development: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float, index=True)
    series: Mapped[list] = mapped_column(JSON, default=list)
