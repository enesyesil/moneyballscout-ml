"""Market values from the open dcaribou/transfermarkt-datasets (refreshed weekly, CC0).

Each refresh snapshots the CSVs to object storage (`raw/transfermarkt/{date}/...`) and loads only the
competitions we track.
"""

import io
import logging
from datetime import UTC, datetime

import httpx
import pandas as pd
import pandera as pa
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.storage import Storage, get_storage
from app.models import MarketValue, TMPlayer

log = logging.getLogger(__name__)

FILES = ("players", "player_valuations")

players_schema = pa.DataFrameSchema(
    {
        "player_id": pa.Column(int),
        "name": pa.Column(str),
        "date_of_birth": pa.Column(nullable=True),
        "market_value_in_eur": pa.Column(float, nullable=True, checks=pa.Check.ge(0)),
    },
    coerce=True,
)
valuations_schema = pa.DataFrameSchema(
    {
        "player_id": pa.Column(int),
        "date": pa.Column("datetime64[ns]"),
        "market_value_in_eur": pa.Column(float, checks=pa.Check.ge(0)),
    },
    coerce=True,
)


def latest_snapshot_prefix(storage: Storage) -> str | None:
    keys = storage.list_keys("raw/transfermarkt/")
    dates = sorted({k.split("/")[2] for k in keys if k.count("/") >= 3})
    return f"raw/transfermarkt/{dates[-1]}" if dates else None


def download_snapshot(storage: Storage | None = None) -> str:
    storage = storage or get_storage()
    s = get_settings()
    prefix = f"raw/transfermarkt/{datetime.now(UTC).date().isoformat()}"
    with httpx.Client(timeout=120, follow_redirects=True) as http:
        for name in FILES:
            resp = http.get(f"{s.transfermarkt_base_url}/{name}.csv.gz")
            resp.raise_for_status()
            storage.put_bytes(f"{prefix}/{name}.csv.gz", resp.content)
            log.info("transfermarkt %s: %.1f MB", name, len(resp.content) / 1e6)
    return prefix


def _read(storage: Storage, key: str) -> pd.DataFrame:
    data = storage.get_bytes(key)
    if data is None:
        raise FileNotFoundError(key)
    return pd.read_csv(io.BytesIO(data), compression="gzip", low_memory=False)


def _none(v):
    return None if pd.isna(v) else v


def load_snapshot(session: Session, prefix: str, storage: Storage | None = None) -> dict:
    storage = storage or get_storage()
    comps = set(get_settings().tm_competitions.values())

    players = _read(storage, f"{prefix}/players.csv.gz")
    players = players[players["current_club_domestic_competition_id"].isin(comps)]
    players = players[players["last_season"] >= players["last_season"].max() - 1]
    players = players_schema.validate(players)
    vals = _read(storage, f"{prefix}/player_valuations.csv.gz")
    vals = valuations_schema.validate(vals[vals["player_id"].isin(players["player_id"])])

    session.execute(delete(MarketValue))
    session.execute(delete(TMPlayer))
    session.add_all(
        TMPlayer(
            id=int(r.player_id),
            name=r.name,
            birth_date=pd.to_datetime(r.date_of_birth).date() if pd.notna(r.date_of_birth) else None,
            club_name=_none(r.current_club_name),
            competition_id=_none(r.current_club_domestic_competition_id),
            position=_none(r.position),
            sub_position=_none(r.sub_position),
            contract_expiration=pd.to_datetime(r.contract_expiration_date).date()
            if pd.notna(r.contract_expiration_date)
            else None,
            market_value=_none(r.market_value_in_eur),
            image_url=_none(r.image_url),
        )
        for r in players.itertuples()
    )
    session.bulk_insert_mappings(
        MarketValue,
        [
            {"tm_player_id": int(r.player_id), "date": r.date.date(), "value_eur": float(r.market_value_in_eur)}
            for r in vals.itertuples()
        ],
    )
    session.flush()
    return {"tm_players": len(players), "market_values": len(vals)}


def refresh(session: Session, storage: Storage | None = None, download: bool = True) -> dict:
    storage = storage or get_storage()
    prefix = download_snapshot(storage) if download else latest_snapshot_prefix(storage)
    if prefix is None:
        raise FileNotFoundError("no transfermarkt snapshot in storage")
    return load_snapshot(session, prefix, storage)
