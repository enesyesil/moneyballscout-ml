"""Turn raw API-Football payloads into rows. Pure functions of the payload, so they are shared by
live syncs and `rebuild-from-raw`."""

from datetime import date, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Coach, CoachTenure, Fixture, League, Player, PlayerMatchStats, Team

FINISHED = {"FT", "AET", "PEN"}


def _int(v) -> int:
    if v is None or v == "":
        return 0
    try:
        return int(float(str(v).rstrip("%")))
    except ValueError:
        return 0


def _float(v) -> float | None:
    try:
        return None if v in (None, "", "-") else float(v)
    except ValueError:
        return None


def _date(v) -> date | None:
    try:
        return date.fromisoformat(v[:10]) if v else None
    except ValueError:
        return None


def _height(v) -> int | None:
    n = _int(str(v).replace("cm", "").strip()) if v else 0
    return n or None


def load_teams(session: Session, payload: dict, league_id: int) -> int:
    for item in payload.get("response", []):
        t = item["team"]
        session.merge(Team(id=t["id"], name=t["name"], code=t.get("code"), logo=t.get("logo"), league_id=league_id))
    return len(payload.get("response", []))


def load_fixtures(session: Session, payload: dict) -> int:
    n = 0
    for item in payload.get("response", []):
        fx, lg, teams, goals = item["fixture"], item["league"], item["teams"], item["goals"]
        session.merge(League(id=lg["id"], name=lg["name"], country=lg.get("country"), logo=lg.get("logo")))
        for side in ("home", "away"):
            t = teams[side]
            if session.get(Team, t["id"]) is None:
                session.add(Team(id=t["id"], name=t["name"], logo=t.get("logo"), league_id=lg["id"]))
        existing = session.get(Fixture, fx["id"])
        session.merge(
            Fixture(
                id=fx["id"],
                league_id=lg["id"],
                season=lg["season"],
                round=lg.get("round"),
                date=datetime.fromisoformat(fx["date"]),
                status=fx["status"]["short"],
                home_team_id=teams["home"]["id"],
                away_team_id=teams["away"]["id"],
                home_goals=goals.get("home"),
                away_goals=goals.get("away"),
                player_stats_synced=existing.player_stats_synced if existing else False,
            )
        )
        n += 1
    session.flush()
    return n


def _accurate_passes(passes: dict) -> int:
    """`passes.accuracy` is a count in /fixtures/players but can come back as a percentage string."""
    total, acc = _int(passes.get("total")), passes.get("accuracy")
    if acc is None:
        return 0
    if isinstance(acc, str) and acc.endswith("%"):
        return round(total * _int(acc) / 100)
    return min(_int(acc), total) if total else _int(acc)


def load_fixture_players(session: Session, fixture_id: int, payload: dict) -> int:
    session.execute(delete(PlayerMatchStats).where(PlayerMatchStats.fixture_id == fixture_id))
    n = 0
    for team_block in payload.get("response", []):
        team_id = team_block["team"]["id"]
        for p in team_block.get("players", []):
            s = (p.get("statistics") or [{}])[0]
            games = s.get("games") or {}
            minutes = _int(games.get("minutes"))
            if minutes <= 0:
                continue
            g = lambda k: s.get(k) or {}  # noqa: E731
            session.add(
                PlayerMatchStats(
                    fixture_id=fixture_id,
                    player_id=p["player"]["id"],
                    team_id=team_id,
                    player_name=p["player"].get("name"),
                    position=games.get("position"),
                    minutes=minutes,
                    substitute=bool(games.get("substitute")),
                    captain=bool(games.get("captain")),
                    api_rating=_float(games.get("rating")),
                    offsides=_int(s.get("offsides")),
                    shots_total=_int(g("shots").get("total")),
                    shots_on=_int(g("shots").get("on")),
                    goals=_int(g("goals").get("total")),
                    conceded=_int(g("goals").get("conceded")),
                    assists=_int(g("goals").get("assists")),
                    saves=_int(g("goals").get("saves")),
                    passes_total=_int(g("passes").get("total")),
                    passes_key=_int(g("passes").get("key")),
                    passes_accurate=_accurate_passes(g("passes")),
                    tackles=_int(g("tackles").get("total")),
                    blocks=_int(g("tackles").get("blocks")),
                    interceptions=_int(g("tackles").get("interceptions")),
                    duels_total=_int(g("duels").get("total")),
                    duels_won=_int(g("duels").get("won")),
                    dribbles_attempts=_int(g("dribbles").get("attempts")),
                    dribbles_success=_int(g("dribbles").get("success")),
                    dribbled_past=_int(g("dribbles").get("past")),
                    fouls_drawn=_int(g("fouls").get("drawn")),
                    fouls_committed=_int(g("fouls").get("committed")),
                    yellow=_int(g("cards").get("yellow")),
                    red=_int(g("cards").get("red")),
                    pen_won=_int(g("penalty").get("won")),
                    pen_committed=_int(g("penalty").get("commited") or g("penalty").get("committed")),
                    pen_scored=_int(g("penalty").get("scored")),
                    pen_missed=_int(g("penalty").get("missed")),
                    pen_saved=_int(g("penalty").get("saved")),
                )
            )
            if session.get(Player, p["player"]["id"]) is None:
                session.add(
                    Player(id=p["player"]["id"], name=p["player"].get("name") or "?", photo=p["player"].get("photo"), team_id=team_id)
                )
            n += 1
    fx = session.get(Fixture, fixture_id)
    if fx is not None:
        fx.player_stats_synced = True
    session.flush()
    return n


def load_players(session: Session, items: list[dict], league_id: int, season: int) -> int:
    """Profiles from paged /players?league&season (birth date, position, current team)."""
    for item in items:
        p = item["player"]
        stats = [s for s in item.get("statistics", []) if (s.get("league") or {}).get("id") == league_id]
        # most minutes in this league = current team for our purposes
        stats.sort(key=lambda s: _int((s.get("games") or {}).get("minutes")), reverse=True)
        main = stats[0] if stats else (item.get("statistics") or [{}])[0]
        team = main.get("team") or {}
        session.merge(
            Player(
                id=p["id"],
                name=p.get("name") or f"{p.get('firstname', '')} {p.get('lastname', '')}".strip(),
                firstname=p.get("firstname"),
                lastname=p.get("lastname"),
                birth_date=_date((p.get("birth") or {}).get("date")),
                nationality=p.get("nationality"),
                height_cm=_height(p.get("height")),
                photo=p.get("photo"),
                position=(main.get("games") or {}).get("position"),
                team_id=team.get("id") if team.get("id") and session.get(Team, team["id"]) else None,
            )
        )
    session.flush()
    return len(items)


def load_coaches(session: Session, payload: dict) -> int:
    n = 0
    for c in payload.get("response", []):
        session.merge(
            Coach(
                id=c["id"],
                name=c.get("name") or "?",
                nationality=c.get("nationality"),
                birth_date=_date((c.get("birth") or {}).get("date")),
                photo=c.get("photo"),
            )
        )
        for job in c.get("career", []):
            team_id = (job.get("team") or {}).get("id")
            start = _date(job.get("start"))
            if not team_id:
                continue
            row = session.scalar(
                select(CoachTenure).where(
                    CoachTenure.coach_id == c["id"], CoachTenure.team_id == team_id, CoachTenure.start == start
                )
            )
            if row is None:
                session.add(CoachTenure(coach_id=c["id"], team_id=team_id, start=start, end=_date(job.get("end"))))
            else:
                row.end = _date(job.get("end"))
        n += 1
    session.flush()
    return n
