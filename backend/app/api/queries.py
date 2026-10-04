"""Shared read queries for the routers."""

import time
from collections.abc import Callable
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.api import schemas
from app.models import Coach, ManagerRating, ModelRun, Player, PlayerSeasonAgg, Team, Valuation

_cache: dict[tuple, tuple[float, int | None, Any]] = {}
TTL_SECONDS = 120


def cached(session: Session, key: tuple, fn: Callable[[], Any]) -> Any:
    """Short in-process TTL cache, invalidated as soon as a newer model run lands."""
    run_id = session.scalar(select(ModelRun.id).where(ModelRun.status == "success").order_by(ModelRun.id.desc()).limit(1))
    hit = _cache.get(key)
    if hit and hit[1] == run_id and time.monotonic() - hit[0] < TTL_SECONDS:
        return hit[2]
    value = fn()
    _cache[key] = (time.monotonic(), run_id, value)
    return value


def team_ref(team: Team | None) -> schemas.TeamRef | None:
    return schemas.TeamRef(id=team.id, name=team.name, logo=team.logo) if team else None


def player_rows_query() -> Select:
    return (
        select(PlayerSeasonAgg, Player, Team, Valuation)
        .join(Player, Player.id == PlayerSeasonAgg.player_id)
        .outerjoin(Team, Team.id == PlayerSeasonAgg.team_id)
        .outerjoin(Valuation, Valuation.player_id == PlayerSeasonAgg.player_id)
    )


def to_player_row(agg: PlayerSeasonAgg, p: Player, team: Team | None, val: Valuation | None) -> schemas.PlayerRow:
    return schemas.PlayerRow(
        id=p.id,
        name=p.name,
        photo=p.photo,
        team=team_ref(team),
        position_group=agg.position_group,
        age=agg.age,
        apps=agg.apps,
        minutes=agg.minutes,
        goals=agg.goals,
        assists=agg.assists,
        avg_rating=agg.avg_rating,
        form=agg.form,
        expected_next=agg.expected_next,
        perf_index=agg.perf_index,
        market_value=agg.market_value,
        p50=val.p50 if val else None,
        undervalue_score=val.undervalue_score if val else None,
    )


def run_out(run: ModelRun | None) -> schemas.ModelRunOut | None:
    if run is None:
        return None
    return schemas.ModelRunOut(
        id=run.id, created_at=run.created_at, status=run.status, git_sha=run.git_sha,
        data_cutoff=run.data_cutoff, mlflow_run_id=run.mlflow_run_id, metrics=run.metrics or {},
    )


def latest_run(session: Session) -> ModelRun | None:
    return session.scalar(select(ModelRun).where(ModelRun.status == "success").order_by(ModelRun.id.desc()).limit(1))


def manager_rows(session: Session, *, team_id: int | None = None, coach_id: int | None = None) -> list[schemas.ManagerRow]:
    q = (
        select(ManagerRating, Coach, Team)
        .join(Coach, Coach.id == ManagerRating.coach_id)
        .join(Team, Team.id == ManagerRating.team_id)
        .order_by(ManagerRating.score.desc())
    )
    if team_id is not None:
        q = q.where(ManagerRating.team_id == team_id)
    if coach_id is not None:
        q = q.where(ManagerRating.coach_id == coach_id)
    return [
        schemas.ManagerRow(
            coach_id=c.id, name=c.name, photo=c.photo, team=team_ref(t), tenure_start=m.tenure_start, matches=m.matches,
            ppg=m.ppg, xppg=m.xppg, pts_over_exp=m.pts_over_exp, squad_efficiency=m.squad_efficiency,
            development=m.development, score=m.score,
        )
        for m, c, t in session.execute(q)
    ]
