from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas
from app.api.queries import manager_rows, player_rows_query, team_ref, to_player_row
from app.core.db import get_session
from app.models import Coach, ManagerRating, PlayerSeasonAgg, Team, TeamStrength

router = APIRouter(tags=["teams"])


def _team_row(team: Team, ts: TeamStrength | None) -> schemas.TeamRow:
    if ts is None:
        return schemas.TeamRow(team=team_ref(team))
    return schemas.TeamRow(
        team=team_ref(team), attack=ts.attack, defence=ts.defence, rating=ts.rating, played=ts.played, points=ts.points,
        xpts=ts.xpts, goals_for=ts.goals_for, goals_against=ts.goals_against, avg_player_rating=ts.avg_player_rating,
        squad_value=ts.squad_value,
    )


@router.get("/teams", response_model=list[schemas.TeamRow])
def list_teams(session: Session = Depends(get_session)):
    rows = session.execute(select(Team, TeamStrength).join(TeamStrength, TeamStrength.team_id == Team.id)).all()
    rows.sort(key=lambda r: (-(r[1].points or 0), -(r[1].goals_for - r[1].goals_against)))
    return [_team_row(t, ts) for t, ts in rows]


@router.get("/teams/{team_id}", response_model=schemas.TeamDetail)
def team_detail(team_id: int, session: Session = Depends(get_session)):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(404, "team not found")
    ts = session.get(TeamStrength, team_id)
    squad = [
        to_player_row(*r)
        for r in session.execute(player_rows_query().where(PlayerSeasonAgg.team_id == team_id).order_by(PlayerSeasonAgg.minutes.desc()))
    ]
    return schemas.TeamDetail(
        team=_team_row(team, ts),
        series=[schemas.TeamMatchPoint(**p) for p in (ts.series if ts else [])],
        squad=squad,
        managers=manager_rows(session, team_id=team_id),
    )


@router.get("/managers", response_model=list[schemas.ManagerRow])
def list_managers(session: Session = Depends(get_session)):
    return manager_rows(session)


@router.get("/managers/{coach_id}", response_model=schemas.ManagerDetail)
def manager_detail(coach_id: int, session: Session = Depends(get_session)):
    rows = manager_rows(session, coach_id=coach_id)
    coach = session.get(Coach, coach_id)
    if not rows or coach is None:
        raise HTTPException(404, "manager not found")
    rating = session.scalar(select(ManagerRating).where(ManagerRating.coach_id == coach_id).order_by(ManagerRating.matches.desc()))
    return schemas.ManagerDetail(
        manager=rows[0], nationality=coach.nationality, series=[schemas.ManagerPoint(**p) for p in (rating.series or [])]
    )
