from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.api import schemas
from app.api.queries import team_ref
from app.core.db import get_session
from app.ingest.loaders import FINISHED
from app.models import Fixture, MatchPrediction, MatchRating, Player, PlayerMatchStats, Team

router = APIRouter(tags=["fixtures"])


def fixture_rows(session: Session, query) -> list[schemas.FixtureRow]:
    home, away = aliased(Team), aliased(Team)
    q = (
        query.add_columns(home, away, MatchPrediction)
        .join(home, home.id == Fixture.home_team_id)
        .join(away, away.id == Fixture.away_team_id)
        .outerjoin(MatchPrediction, MatchPrediction.fixture_id == Fixture.id)
    )
    return [
        schemas.FixtureRow(
            id=fx.id, date=fx.date, round=fx.round, status=fx.status, home=team_ref(h), away=team_ref(a),
            home_goals=fx.home_goals, away_goals=fx.away_goals,
            prediction=schemas.Prediction(
                home_win=p.home_win, draw=p.draw, away_win=p.away_win,
                exp_home_goals=p.exp_home_goals, exp_away_goals=p.exp_away_goals,
            ) if p else None,
        )
        for fx, h, a, p in session.execute(q)
    ]


@router.get("/fixtures", response_model=list[schemas.FixtureRow])
def list_fixtures(
    status: Literal["upcoming", "played"] = "played",
    team_id: int | None = None,
    limit: int = Query(20, le=400),
    session: Session = Depends(get_session),
):
    q = select(Fixture)
    if status == "played":
        q = q.where(Fixture.status.in_(FINISHED)).order_by(Fixture.date.desc())
    else:
        q = q.where(Fixture.status.in_(["NS", "TBD"])).order_by(Fixture.date)
    if team_id:
        q = q.where((Fixture.home_team_id == team_id) | (Fixture.away_team_id == team_id))
    return fixture_rows(session, q.limit(limit))


@router.get("/fixtures/{fixture_id}", response_model=schemas.FixtureDetail)
def fixture_detail(fixture_id: int, session: Session = Depends(get_session)):
    rows = fixture_rows(session, select(Fixture).where(Fixture.id == fixture_id))
    if not rows:
        raise HTTPException(404, "fixture not found")
    fx = rows[0]
    stats = session.execute(
        select(PlayerMatchStats, MatchRating, Player.photo)
        .outerjoin(
            MatchRating,
            (MatchRating.fixture_id == PlayerMatchStats.fixture_id) & (MatchRating.player_id == PlayerMatchStats.player_id),
        )
        .outerjoin(Player, Player.id == PlayerMatchStats.player_id)
        .where(PlayerMatchStats.fixture_id == fixture_id)
        .order_by(PlayerMatchStats.substitute, PlayerMatchStats.minutes.desc())
    ).all()
    lineups: dict[str, list[schemas.LineupPlayer]] = {"home": [], "away": []}
    for s, r, photo in stats:
        side = "home" if s.team_id == fx.home.id else "away"
        lineups[side].append(
            schemas.LineupPlayer(
                player_id=s.player_id, name=s.player_name or "?", photo=photo, position=s.position, minutes=s.minutes,
                substitute=s.substitute, rating=r.rating if r else None, api_rating=s.api_rating,
                components=(r.components if r else {}) or {}, goals=s.goals, assists=s.assists,
            )
        )
    return schemas.FixtureDetail(fixture=fx, lineups=lineups)
