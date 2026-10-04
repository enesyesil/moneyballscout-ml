"""Prioritized, quota-aware sync.

Each job asks the client for data; cached responses cost nothing. When the daily quota runs out the
current job stops cleanly and the rest resume tomorrow (fixtures still flagged unsynced are retried).
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.storage import Storage, get_json_gz, get_storage
from app.ingest import loaders
from app.ingest.api_football import RAW_PREFIX, ApiFootballClient, QuotaExhausted
from app.models import Fixture, League, Team

log = logging.getLogger(__name__)


def sync_fixtures(client: ApiFootballClient, league: int, season: int) -> int:
    payload = client.get("fixtures", {"league": league, "season": season})
    n = loaders.load_fixtures(client.session, payload)
    client.session.commit()
    return n


def sync_teams(client: ApiFootballClient, league: int, season: int) -> int:
    n = loaders.load_teams(client.session, client.get("teams", {"league": league, "season": season}), league)
    client.session.commit()
    return n


def sync_fixture_players(client: ApiFootballClient, league: int, season: int, limit: int | None = None) -> int:
    """Per-match player stats for finished fixtures we have not loaded yet, oldest first."""
    pending = client.session.scalars(
        select(Fixture)
        .where(
            Fixture.league_id == league,
            Fixture.season == season,
            Fixture.status.in_(loaders.FINISHED),
            Fixture.player_stats_synced.is_(False),
        )
        .order_by(Fixture.date)
        .limit(limit)
    ).all()
    done = 0
    for fx in pending:
        payload = client.get("fixtures/players", {"fixture": fx.id})
        if not payload.get("response"):
            continue  # stats not published yet
        loaders.load_fixture_players(client.session, fx.id, payload)
        client.session.commit()
        done += 1
    return done


def sync_players(client: ApiFootballClient, league: int, season: int) -> int:
    items = client.get_all_pages("players", {"league": league, "season": season})
    n = loaders.load_players(client.session, items, league, season)
    client.session.commit()
    return n


def sync_coaches(client: ApiFootballClient, league: int) -> int:
    n = 0
    for team in client.session.scalars(select(Team).where(Team.league_id == league)):
        n += loaders.load_coaches(client.session, client.get("coachs", {"team": team.id}))
        client.session.commit()
    return n


def run_sync(session: Session, storage: Storage | None = None) -> dict:
    """Run all jobs in priority order until done or out of quota."""
    s = get_settings()
    client = ApiFootballClient(session, storage=storage)
    report: dict = {"started": datetime.now(UTC).isoformat(), "jobs": {}, "quota_exhausted": False}
    for league in s.leagues:
        jobs = [
            ("fixtures", lambda lg=league: sync_fixtures(client, lg, s.season)),
            ("teams", lambda lg=league: sync_teams(client, lg, s.season)),
            ("fixture_players", lambda lg=league: sync_fixture_players(client, lg, s.season)),
            ("players", lambda lg=league: sync_players(client, lg, s.season)),
            ("coaches", lambda lg=league: sync_coaches(client, lg)),
        ]
        for name, job in jobs:
            try:
                report["jobs"][f"{league}:{name}"] = job()
            except QuotaExhausted as e:
                log.warning("quota exhausted during %s: %s", name, e)
                report["quota_exhausted"] = True
                session.rollback()
                break
        if report["quota_exhausted"]:
            break
    report["requests_remaining"] = client.remaining_today()
    return report


def rebuild_from_raw(session: Session, storage: Storage | None = None) -> dict:
    """Reload every source table from archived raw responses. Makes no network calls."""
    storage = storage or get_storage()
    counts: dict[str, int] = {}

    def payloads(endpoint: str):
        for key in storage.list_keys(f"{RAW_PREFIX}/{endpoint}/"):
            p = get_json_gz(storage, key)
            if p is not None:
                yield p

    for p in payloads("fixtures"):
        counts["fixtures"] = counts.get("fixtures", 0) + loaders.load_fixtures(session, p)
    for p in payloads("teams"):
        league = int(p["_params"]["league"])
        if session.get(League, league) is None:
            session.add(League(id=league, name=str(league)))
        counts["teams"] = counts.get("teams", 0) + loaders.load_teams(session, p, league)
    session.commit()
    for p in payloads("fixtures/players"):
        fid = int(p["_params"]["fixture"])
        if session.get(Fixture, fid) is not None:
            counts["fixture_players"] = counts.get("fixture_players", 0) + loaders.load_fixture_players(session, fid, p)
    session.commit()
    for p in payloads("players"):
        prm = p["_params"]
        counts["players"] = counts.get("players", 0) + loaders.load_players(
            session, p.get("response", []), int(prm["league"]), int(prm["season"])
        )
    for p in payloads("coachs"):
        counts["coaches"] = counts.get("coaches", 0) + loaders.load_coaches(session, p)
    session.commit()
    return counts


def sync_status(session: Session) -> dict:
    from sqlalchemy import func

    from app.models import ApiUsage

    s = get_settings()
    today = datetime.now(UTC).date()
    used = session.scalar(select(func.count()).select_from(ApiUsage).where(ApiUsage.day == today)) or 0
    week = session.execute(
        select(ApiUsage.day, func.count()).where(ApiUsage.day >= today - timedelta(days=6)).group_by(ApiUsage.day)
    ).all()
    fixtures = session.execute(
        select(Fixture.status.in_(loaders.FINISHED), Fixture.player_stats_synced, func.count()).group_by(
            Fixture.status.in_(loaders.FINISHED), Fixture.player_stats_synced
        )
    ).all()
    finished = sum(c for fin, _, c in fixtures if fin)
    synced = sum(c for fin, syn, c in fixtures if fin and syn)
    return {
        "leagues": s.leagues,
        "season": s.season,
        "daily_quota": s.daily_quota,
        "used_today": used,
        "remaining_today": max(0, s.daily_quota - used),
        "usage_last_7_days": [{"day": d.isoformat(), "requests": c} for d, c in sorted(week)],
        "fixtures_total": sum(c for *_, c in fixtures),
        "fixtures_finished": finished,
        "fixtures_with_player_stats": synced,
        "backfill_pending": finished - synced,
    }
