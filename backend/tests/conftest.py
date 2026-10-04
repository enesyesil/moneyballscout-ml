import os
import tempfile
from datetime import date

_tmp = tempfile.mkdtemp(prefix="scout-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_DIR"] = f"{_tmp}/objects"
os.environ["MLFLOW_TRACKING_URI"] = ""
os.environ["API_FOOTBALL_KEY"] = "test-key"
os.environ["SEASON"] = "2025"
os.environ["LEAGUES"] = "39"

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.ingest import entity_resolution, loaders  # noqa: E402
from app.models import MarketValue, TMPlayer  # noqa: E402
from app import demo as synthetic  # noqa: E402


@pytest.fixture(scope="session")
def league():
    return synthetic.make_league()


@pytest.fixture(scope="session")
def loaded_db(league):
    """Fresh database with the synthetic league loaded through the real loaders."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    rng = np.random.default_rng(1)
    with SessionLocal() as s:
        loaders.load_fixtures(s, league["fixtures"])
        loaders.load_teams(s, {"response": [{"team": t} for t in league["teams"]]}, 39)
        for fid, payload in league["fixture_players"].items():
            loaders.load_fixture_players(s, fid, payload)
        loaders.load_players(s, synthetic.players_payload(league["players"]), 39, 2025)
        loaders.load_coaches(s, synthetic.coaches_payload(league["teams"]))
        # market values that track true quality + noise, under Transfermarkt-style names
        for p in league["players"]:
            q = p["skill"] * 0.6 + p["team_strength"] * 2
            value = float(np.exp(16 + 0.8 * q + rng.normal(0, 0.4)))
            s.add(TMPlayer(id=p["id"] + 1, name=f"{p['firstname']} {p['lastname']}",
                           birth_date=date.fromisoformat(p["birth"]), market_value=value, competition_id="GB1",
                           contract_expiration=date(2027, 6, 30)))
            s.add(MarketValue(tm_player_id=p["id"] + 1, date=date(2025, 6, 1), value_eur=value * 0.9))
        s.commit()
        entity_resolution.resolve(s)
        s.commit()
    return league


@pytest.fixture
def session(loaded_db):
    with SessionLocal() as s:
        yield s
