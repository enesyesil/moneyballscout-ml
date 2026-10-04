from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.api import schemas
from app.api.queries import cached, player_rows_query, team_ref, to_player_row
from app.core.db import get_session
from app.models import (
    Fixture, MarketValue, MatchRating, Player, PlayerForm, PlayerLink, PlayerMatchStats, PlayerSeasonAgg, SimilarPlayer,
    Team, Valuation,
)

router = APIRouter(tags=["players"])

SORTS = {
    "perf_index": PlayerSeasonAgg.perf_index,
    "form": PlayerSeasonAgg.form,
    "avg_rating": PlayerSeasonAgg.avg_rating,
    "market_value": PlayerSeasonAgg.market_value,
    "minutes": PlayerSeasonAgg.minutes,
    "goals": PlayerSeasonAgg.goals,
    "undervalue": Valuation.undervalue_score,
}


@router.get("/players", response_model=list[schemas.PlayerRow])
def list_players(
    position: Literal["GK", "DEF", "MID", "FWD"] | None = None,
    team_id: int | None = None,
    age_max: float | None = None,
    value_max: float | None = Query(None, description="EUR"),
    min_minutes: int = 0,
    q: str | None = None,
    sort: Literal["perf_index", "form", "avg_rating", "market_value", "minutes", "goals", "undervalue"] = "perf_index",
    limit: int = Query(50, le=500),
    offset: int = 0,
    session: Session = Depends(get_session),
):
    query = player_rows_query().where(PlayerSeasonAgg.minutes >= min_minutes)
    if position:
        query = query.where(PlayerSeasonAgg.position_group == position)
    if team_id:
        query = query.where(PlayerSeasonAgg.team_id == team_id)
    if age_max:
        query = query.where(PlayerSeasonAgg.age <= age_max)
    if value_max:
        query = query.where(PlayerSeasonAgg.market_value <= value_max)
    if q:
        query = query.where(or_(Player.name.ilike(f"%{q}%"), Player.lastname.ilike(f"%{q}%")))
    col = SORTS[sort]
    query = query.where(col.is_not(None)).order_by(col.desc()).limit(limit).offset(offset)
    return [to_player_row(*r) for r in session.execute(query)]


@router.get("/players/{player_id}", response_model=schemas.PlayerDetail)
def player_detail(player_id: int, session: Session = Depends(get_session)):
    row = session.execute(player_rows_query().where(PlayerSeasonAgg.player_id == player_id)).first()
    if row is None:
        raise HTTPException(404, "player not found or has no minutes this season")
    agg, p, team, val = row
    history = []
    link = session.get(PlayerLink, player_id)
    if link:
        history = [
            schemas.ValuePoint(date=d, value=v)
            for d, v in session.execute(
                select(MarketValue.date, MarketValue.value_eur)
                .where(MarketValue.tm_player_id == link.tm_player_id)
                .order_by(MarketValue.date)
            )
        ]
    return schemas.PlayerDetail(
        player=to_player_row(agg, p, team, val),
        nationality=p.nationality,
        birth_date=p.birth_date,
        height_cm=p.height_cm,
        profile_position=p.position,
        form_sd=agg.form_sd,
        per90=agg.per90 or {},
        shrunk_per90=agg.shrunk_per90 or {},
        percentiles=agg.percentiles or {},
        valuation=schemas.Valuation(
            market_value=val.market_value, p10=val.p10, p50=val.p50, p90=val.p90,
            undervalue_score=val.undervalue_score, below_p10=val.below_p10, contributions=val.contributions or {},
        ) if val else None,
        value_history=history,
        contract_expiration=agg.contract_expiration,
    )


@router.get("/players/{player_id}/ratings", response_model=list[schemas.RatingPoint])
def player_ratings(player_id: int, session: Session = Depends(get_session)):
    home, away = aliased(Team), aliased(Team)
    rows = session.execute(
        select(MatchRating, Fixture, PlayerForm, PlayerMatchStats.api_rating, home, away)
        .join(Fixture, Fixture.id == MatchRating.fixture_id)
        .join(home, home.id == Fixture.home_team_id)
        .join(away, away.id == Fixture.away_team_id)
        .outerjoin(PlayerForm, (PlayerForm.player_id == MatchRating.player_id) & (PlayerForm.fixture_id == MatchRating.fixture_id))
        .outerjoin(
            PlayerMatchStats,
            (PlayerMatchStats.player_id == MatchRating.player_id) & (PlayerMatchStats.fixture_id == MatchRating.fixture_id),
        )
        .where(MatchRating.player_id == player_id)
        .order_by(Fixture.date)
    ).all()
    out = []
    for r, fx, f, api_rating, h, a in rows:
        is_home = r.team_id == fx.home_team_id
        out.append(
            schemas.RatingPoint(
                fixture_id=fx.id, date=fx.date, opponent=team_ref(a if is_home else h), home=is_home,
                score=f"{fx.home_goals}-{fx.away_goals}", minutes=r.minutes, rating=r.rating, api_rating=api_rating,
                form=f.form if f else None, form_lo=f.form_lo if f else None, form_hi=f.form_hi if f else None,
                components=r.components or {},
            )
        )
    return out


@router.get("/players/{player_id}/similar", response_model=list[schemas.SimilarRow])
def similar(
    player_id: int,
    max_value: float | None = None,
    max_age: float | None = None,
    limit: int = Query(10, le=15),
    session: Session = Depends(get_session),
):
    query = (
        player_rows_query()
        .add_columns(SimilarPlayer.similarity)
        .join(SimilarPlayer, SimilarPlayer.similar_player_id == PlayerSeasonAgg.player_id)
        .where(SimilarPlayer.player_id == player_id)
        .order_by(SimilarPlayer.rank)
    )
    if max_value:
        query = query.where(PlayerSeasonAgg.market_value <= max_value)
    if max_age:
        query = query.where(PlayerSeasonAgg.age <= max_age)
    return [
        schemas.SimilarRow(**to_player_row(agg, p, t, v).model_dump(), similarity=sim)
        for agg, p, t, v, sim in session.execute(query.limit(limit))
    ]


@router.get("/moneyball/undervalued", response_model=list[schemas.PlayerRow])
def undervalued(
    position: Literal["GK", "DEF", "MID", "FWD"] | None = None,
    age_max: float | None = None,
    value_max: float | None = None,
    min_minutes: int = 450,
    limit: int = Query(25, le=200),
    session: Session = Depends(get_session),
):
    query = player_rows_query().where(Valuation.undervalue_score > 0, PlayerSeasonAgg.minutes >= min_minutes)
    if position:
        query = query.where(PlayerSeasonAgg.position_group == position)
    if age_max:
        query = query.where(PlayerSeasonAgg.age <= age_max)
    if value_max:
        query = query.where(PlayerSeasonAgg.market_value <= value_max)
    query = query.order_by(Valuation.undervalue_score.desc()).limit(limit)
    return [to_player_row(*r) for r in session.execute(query)]


@router.get("/moneyball/scatter", response_model=list[schemas.ScatterPoint])
def scatter(
    position: Literal["GK", "DEF", "MID", "FWD"] | None = None,
    min_minutes: int = 270,
    session: Session = Depends(get_session),
):
    def build():
        query = (
            select(PlayerSeasonAgg, Player.name, Team.name, Valuation)
            .join(Player, Player.id == PlayerSeasonAgg.player_id)
            .outerjoin(Team, Team.id == PlayerSeasonAgg.team_id)
            .outerjoin(Valuation, Valuation.player_id == PlayerSeasonAgg.player_id)
            .where(PlayerSeasonAgg.market_value.is_not(None), PlayerSeasonAgg.perf_index.is_not(None),
                   PlayerSeasonAgg.minutes >= min_minutes)
        )
        if position:
            query = query.where(PlayerSeasonAgg.position_group == position)
        return [
            schemas.ScatterPoint(
                id=a.player_id, name=name, team=team, position_group=a.position_group, age=a.age, perf_index=a.perf_index,
                market_value=a.market_value, p10=v.p10 if v else None, p50=v.p50 if v else None, p90=v.p90 if v else None,
                undervalue_score=v.undervalue_score if v else None,
            )
            for a, name, team, v in session.execute(query)
        ]

    return cached(session, ("scatter", position, min_minutes), build)

