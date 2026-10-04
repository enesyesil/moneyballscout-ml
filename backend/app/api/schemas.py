from datetime import UTC, date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel

# SQLite drops tzinfo; every stored timestamp is UTC, so make that explicit in responses
UTCDateTime = Annotated[datetime, AfterValidator(lambda d: d if d.tzinfo else d.replace(tzinfo=UTC))]


class TeamRef(BaseModel):
    id: int
    name: str
    logo: str | None = None


class PlayerRow(BaseModel):
    id: int
    name: str
    photo: str | None = None
    team: TeamRef | None = None
    position_group: str
    age: float | None = None
    apps: int
    minutes: int
    goals: int
    assists: int
    avg_rating: float | None = None
    form: float | None = None
    expected_next: float | None = None
    perf_index: float | None = None
    market_value: float | None = None
    p50: float | None = None
    undervalue_score: float | None = None


class SimilarRow(PlayerRow):
    similarity: float


class Valuation(BaseModel):
    market_value: float
    p10: float
    p50: float
    p90: float
    undervalue_score: float
    below_p10: bool
    contributions: dict[str, float]


class ValuePoint(BaseModel):
    date: date
    value: float


class PlayerDetail(BaseModel):
    player: PlayerRow
    nationality: str | None = None
    birth_date: date | None = None
    height_cm: int | None = None
    profile_position: str | None = None
    form_sd: float | None = None
    per90: dict[str, float | None]
    shrunk_per90: dict[str, float | None]
    percentiles: dict[str, float | None]
    valuation: Valuation | None = None
    value_history: list[ValuePoint]
    contract_expiration: date | None = None


class RatingPoint(BaseModel):
    fixture_id: int
    date: UTCDateTime
    opponent: TeamRef
    home: bool
    score: str
    minutes: int
    rating: float
    api_rating: float | None = None
    form: float | None = None
    form_lo: float | None = None
    form_hi: float | None = None
    components: dict[str, float]


class ScatterPoint(BaseModel):
    id: int
    name: str
    team: str | None = None
    position_group: str
    age: float | None = None
    perf_index: float
    market_value: float
    p10: float | None = None
    p50: float | None = None
    p90: float | None = None
    undervalue_score: float | None = None


class Prediction(BaseModel):
    home_win: float
    draw: float
    away_win: float
    exp_home_goals: float
    exp_away_goals: float


class FixtureRow(BaseModel):
    id: int
    date: UTCDateTime
    round: str | None = None
    status: str
    home: TeamRef
    away: TeamRef
    home_goals: int | None = None
    away_goals: int | None = None
    prediction: Prediction | None = None


class LineupPlayer(BaseModel):
    player_id: int
    name: str
    photo: str | None = None
    position: str | None = None
    minutes: int
    substitute: bool
    rating: float | None = None
    api_rating: float | None = None
    components: dict[str, float] = {}
    goals: int
    assists: int


class FixtureDetail(BaseModel):
    fixture: FixtureRow
    lineups: dict[str, list[LineupPlayer]]


class TeamRow(BaseModel):
    team: TeamRef
    attack: float | None = None
    defence: float | None = None
    rating: float | None = None
    played: int | None = None
    points: int | None = None
    xpts: float | None = None
    goals_for: int | None = None
    goals_against: int | None = None
    avg_player_rating: float | None = None
    squad_value: float | None = None


class TeamMatchPoint(BaseModel):
    date: date
    fixture_id: int
    opponent_id: int
    gf: int
    ga: int
    pts: int
    xpts: float


class ManagerRow(BaseModel):
    coach_id: int
    name: str
    photo: str | None = None
    team: TeamRef
    tenure_start: date | None = None
    matches: int
    ppg: float
    xppg: float
    pts_over_exp: float
    squad_efficiency: float | None = None
    development: float | None = None
    score: float


class TeamDetail(BaseModel):
    team: TeamRow
    series: list[TeamMatchPoint]
    squad: list[PlayerRow]
    managers: list[ManagerRow]


class ManagerPoint(BaseModel):
    date: date
    pts: int
    xpts: float


class ManagerDetail(BaseModel):
    manager: ManagerRow
    nationality: str | None = None
    series: list[ManagerPoint]


class ModelRunOut(BaseModel):
    id: int
    created_at: UTCDateTime
    status: str
    git_sha: str | None = None
    data_cutoff: UTCDateTime | None = None
    mlflow_run_id: str | None = None
    metrics: dict


class TeamOfWeekPlayer(BaseModel):
    player_id: int
    name: str
    photo: str | None = None
    team: TeamRef
    position_group: str
    rating: float


class Dashboard(BaseModel):
    round: str | None = None
    team_of_the_week: list[TeamOfWeekPlayer]
    in_form: list[PlayerRow]
    undervalued: list[PlayerRow]
    upcoming: list[FixtureRow]
    latest_run: ModelRunOut | None = None


class Meta(BaseModel):
    leagues: list[int]
    season: int
    teams: list[TeamRef]
    latest_run: ModelRunOut | None = None
