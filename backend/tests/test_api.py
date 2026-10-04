import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client(run):  # noqa: ARG001 - depends on the pipeline run fixture
    return TestClient(app)


@pytest.fixture(scope="module")
def run(loaded_db):
    from app.core.db import SessionLocal
    from app.ml import pipeline

    with SessionLocal() as s:
        mr = pipeline.run(s, n_trials=0)
        s.commit()
        return mr.id


def test_endpoints(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    meta = client.get("/api/meta").json()
    assert meta["latest_run"]["status"] == "success"

    players = client.get("/api/players", params={"min_minutes": 450, "limit": 10}).json()
    assert len(players) == 10
    assert players[0]["perf_index"] >= players[-1]["perf_index"]
    pid = players[0]["id"]

    detail = client.get(f"/api/players/{pid}").json()
    assert detail["percentiles"] and detail["valuation"]["p50"] > 0
    ratings = client.get(f"/api/players/{pid}/ratings").json()
    assert ratings and "components" in ratings[0] and ratings[0]["form"] is not None
    assert client.get(f"/api/players/{pid}/similar").status_code == 200

    assert client.get("/api/moneyball/scatter").json()
    assert isinstance(client.get("/api/moneyball/undervalued").json(), list)

    fixtures = client.get("/api/fixtures", params={"status": "played"}).json()
    fx = client.get(f"/api/fixtures/{fixtures[0]['id']}").json()
    assert fx["lineups"]["home"] and fx["lineups"]["home"][0]["rating"] is not None
    upcoming = client.get("/api/fixtures", params={"status": "upcoming"}).json()
    assert upcoming and upcoming[0]["prediction"]

    teams = client.get("/api/teams").json()
    assert len(teams) == 10
    team = client.get(f"/api/teams/{teams[0]['team']['id']}").json()
    assert team["series"] and team["squad"] and team["managers"]
    managers = client.get("/api/managers").json()
    assert managers and 0 <= managers[0]["score"] <= 100
    assert client.get(f"/api/managers/{managers[0]['coach_id']}").json()["series"]

    dash = client.get("/api/dashboard").json()
    assert len(dash["team_of_the_week"]) == 11
    assert client.get("/api/models/runs").json()
    assert client.get("/api/admin/sync-status").json()["fixtures_finished"] > 0
    assert client.get("/api/players/999999").status_code == 404
