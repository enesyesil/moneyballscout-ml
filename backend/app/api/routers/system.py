import os

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.queries import cached, latest_run, player_rows_query, run_out, team_ref, to_player_row
from app.api.routers.fixtures import fixture_rows
from app.core.config import get_settings
from app.core.db import get_session
from app.ingest.jobs import sync_status
from app.ingest.loaders import FINISHED
from app.models import Fixture, MatchRating, ModelRun, Player, PlayerSeasonAgg, Team, Valuation

router = APIRouter()

FORMATION = {"GK": 1, "DEF": 4, "MID": 3, "FWD": 3}


@router.get("/health", tags=["system"])
def health(session: Session = Depends(get_session)):
    session.execute(text("SELECT 1"))
    return {"status": "ok", "git_sha": os.getenv("GIT_SHA") or None}


@router.get("/meta", response_model=schemas.Meta, tags=["system"])
def meta(session: Session = Depends(get_session)):
    s = get_settings()
    teams = session.scalars(select(Team).where(Team.league_id.in_(s.leagues)).order_by(Team.name)).all()
    return schemas.Meta(leagues=s.leagues, season=s.season, teams=[team_ref(t) for t in teams], latest_run=run_out(latest_run(session)))


def team_of_the_week(session: Session) -> tuple[str | None, list[schemas.TeamOfWeekPlayer]]:
    last = session.scalar(
        select(Fixture).join(MatchRating, MatchRating.fixture_id == Fixture.id).where(Fixture.status.in_(FINISHED))
        .order_by(Fixture.date.desc()).limit(1)
    )
    if last is None:
        return None, []
    rows = session.execute(
        select(MatchRating, Player, Team)
        .join(Fixture, Fixture.id == MatchRating.fixture_id)
        .join(Player, Player.id == MatchRating.player_id)
        .join(Team, Team.id == MatchRating.team_id)
        .where(Fixture.round == last.round, Fixture.season == last.season, MatchRating.minutes >= 45)
        .order_by(MatchRating.rating.desc())
    ).all()
    picked: list[schemas.TeamOfWeekPlayer] = []
    need = dict(FORMATION)
    for r, p, t in rows:
        if need.get(r.position_group, 0) > 0:
            need[r.position_group] -= 1
            picked.append(schemas.TeamOfWeekPlayer(player_id=p.id, name=p.name, photo=p.photo, team=team_ref(t),
                                                   position_group=r.position_group, rating=r.rating))
    order = list(FORMATION)
    picked.sort(key=lambda x: order.index(x.position_group))
    return last.round, picked


@router.get("/dashboard", response_model=schemas.Dashboard, tags=["system"])
def dashboard(session: Session = Depends(get_session)):
    def build():
        rnd, totw = team_of_the_week(session)
        in_form = [
            to_player_row(*r) for r in session.execute(
                player_rows_query().where(PlayerSeasonAgg.minutes >= 450, PlayerSeasonAgg.form.is_not(None))
                .order_by(PlayerSeasonAgg.form.desc()).limit(8))
        ]
        under = [
            to_player_row(*r) for r in session.execute(
                player_rows_query().where(PlayerSeasonAgg.minutes >= 450, Valuation.undervalue_score > 0)
                .order_by(Valuation.undervalue_score.desc()).limit(8))
        ]
        upcoming = fixture_rows(session, select(Fixture).where(Fixture.status.in_(["NS", "TBD"])).order_by(Fixture.date).limit(10))
        return schemas.Dashboard(round=rnd, team_of_the_week=totw, in_form=in_form, undervalued=under, upcoming=upcoming,
                                 latest_run=run_out(latest_run(session)))

    return cached(session, ("dashboard",), build)


@router.get("/models/runs", response_model=list[schemas.ModelRunOut], tags=["system"])
def model_runs(limit: int = Query(20, le=100), session: Session = Depends(get_session)):
    return [run_out(r) for r in session.scalars(select(ModelRun).order_by(ModelRun.id.desc()).limit(limit))]


@router.get("/admin/sync-status", tags=["system"])
def admin_sync_status(session: Session = Depends(get_session)):
    return sync_status(session)
