import httpx
import pytest

from app.core.config import get_settings
from app.core.storage import LocalStorage
from app.ingest import entity_resolution, loaders
from app.ingest.api_football import ApiFootballClient, QuotaExhausted, raw_key
from app.models import Fixture, PlayerLink, PlayerMatchStats


def _client(session, tmp_path, handler, quota=3):
    settings = get_settings().model_copy(update={"daily_quota": quota, "per_minute_limit": 1000})
    return ApiFootballClient(session, settings=settings, storage=LocalStorage(str(tmp_path)), transport=httpx.MockTransport(handler))


def test_client_caches_and_stops_at_quota(session, tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.headers["x-apisports-key"] == "test-key"
        return httpx.Response(200, json={"response": [{"n": len(calls)}], "errors": []},
                              headers={"x-ratelimit-requests-remaining": "99"})

    client = _client(session, tmp_path, handler, quota=2)
    used_before = client.used_today()
    client.settings = client.settings.model_copy(update={"daily_quota": used_before + 2})
    a = client.get("fixtures/players", {"fixture": 1})
    b = client.get("fixtures/players", {"fixture": 1})  # finished-fixture data is cached forever
    assert a["response"] == b["response"] and len(calls) == 1
    assert LocalStorage(str(tmp_path)).exists(raw_key("fixtures/players", {"fixture": 1}))
    client.get("fixtures/players", {"fixture": 2})
    with pytest.raises(QuotaExhausted):
        client.get("fixtures/players", {"fixture": 3})
    assert len(calls) == 2


def test_api_errors_in_body_are_raised(session, tmp_path):
    def handler(request):
        return httpx.Response(200, json={"errors": {"token": "Error/Missing application key."}, "response": []})

    client = _client(session, tmp_path, handler, quota=10_000)
    with pytest.raises(Exception, match="application key"):
        client.get("teams", {"league": 39, "season": 2025})


def test_loaders_parse_fixture_players(session, loaded_db):
    played = [f for f in loaded_db["fixtures"]["response"] if f["fixture"]["status"]["short"] == "FT"]
    fx = session.get(Fixture, played[0]["fixture"]["id"])
    assert fx.player_stats_synced and fx.home_goals is not None
    rows = session.query(PlayerMatchStats).filter_by(fixture_id=fx.id).all()
    assert rows and all(r.minutes > 0 for r in rows)
    assert all(r.passes_accurate <= r.passes_total for r in rows)


def test_accurate_passes_handles_percent_and_counts():
    assert loaders._accurate_passes({"total": 40, "accuracy": "30"}) == 30
    assert loaders._accurate_passes({"total": 40, "accuracy": "75%"}) == 30
    assert loaders._accurate_passes({"total": 10, "accuracy": None}) == 0


def test_entity_resolution(session, loaded_db):
    links = session.query(PlayerLink).count()
    assert links >= 0.95 * len(loaded_db["players"])
    assert entity_resolution.name_score(["B. Saka"], "Bukayo Saka") >= 90
    assert entity_resolution.name_score(["Martin Ødegaard"], "Martin Odegaard") == 100
    assert entity_resolution.name_score(["Bukayo Saka"], "Gabriel Jesus") < 60
