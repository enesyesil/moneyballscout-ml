"""Quota-aware API-Football v3 client.

Every response is archived to object storage (gzipped JSON) before it is used, so storage is a
replayable cache: finished fixtures are never fetched twice, and `rebuild-from-raw` can reload the
whole database without spending quota.
"""

import hashlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings, get_settings
from app.core.storage import Storage, get_json_gz, get_storage, put_json_gz
from app.models import ApiUsage

log = logging.getLogger(__name__)

RAW_PREFIX = "raw/api-football"

# how long a cached response stays fresh, per endpoint (None = forever)
TTL: dict[str, timedelta | None] = {
    "fixtures": timedelta(hours=6),
    "fixtures/players": None,  # only fetched for finished matches, which never change
    "players": timedelta(days=7),
    "teams": timedelta(days=30),
    "coachs": timedelta(days=30),
    "leagues": timedelta(days=30),
}


class QuotaExhausted(Exception):
    pass


class ApiError(Exception):
    pass


class _Transient(Exception):
    pass


def raw_key(endpoint: str, params: dict) -> str:
    canon = json.dumps(params, sort_keys=True)
    digest = hashlib.sha1(f"{endpoint}?{canon}".encode()).hexdigest()[:16]
    return f"{RAW_PREFIX}/{endpoint}/{digest}.json.gz"


class TokenBucket:
    """Simple per-minute limiter: at most `rate` calls in any rolling 60s window."""

    def __init__(self, rate: int):
        self.rate = rate
        self.calls: list[float] = []

    def wait(self) -> None:
        now = time.monotonic()
        self.calls = [t for t in self.calls if now - t < 60]
        if len(self.calls) >= self.rate:
            time.sleep(60 - (now - self.calls[0]) + 0.1)
        self.calls.append(time.monotonic())


class ApiFootballClient:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        storage: Storage | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.settings = settings or get_settings()
        self.session = session
        self.storage = storage or get_storage()
        self.bucket = TokenBucket(self.settings.per_minute_limit)
        self.http = httpx.Client(
            base_url=self.settings.api_football_base_url,
            headers={"x-apisports-key": self.settings.api_football_key},
            timeout=30,
            transport=transport,
        )

    # ---- quota

    def used_today(self) -> int:
        today = datetime.now(UTC).date()
        return self.session.scalar(select(func.count()).select_from(ApiUsage).where(ApiUsage.day == today)) or 0

    def remaining_today(self) -> int:
        return max(0, self.settings.daily_quota - self.used_today())

    # ---- calls

    def get(self, endpoint: str, params: dict | None = None, *, force: bool = False) -> dict:
        """Return the API payload, from storage when fresh, else from the network."""
        params = params or {}
        key = raw_key(endpoint, params)
        if not force:
            cached = get_json_gz(self.storage, key)
            if cached is not None and self._fresh(endpoint, cached.get("_fetched_at")):
                return cached
        if self.remaining_today() <= 0:
            raise QuotaExhausted(f"daily quota of {self.settings.daily_quota} requests used")
        payload = self._fetch(endpoint, params)
        payload["_fetched_at"] = datetime.now(UTC).isoformat()
        payload["_endpoint"] = endpoint
        payload["_params"] = params
        put_json_gz(self.storage, key, payload)
        return payload

    def get_cached(self, endpoint: str, params: dict) -> dict | None:
        return get_json_gz(self.storage, raw_key(endpoint, params))

    def get_all_pages(self, endpoint: str, params: dict) -> list[dict]:
        first = self.get(endpoint, {**params, "page": 1})
        out = list(first.get("response", []))
        total = (first.get("paging") or {}).get("total", 1)
        for page in range(2, total + 1):
            out.extend(self.get(endpoint, {**params, "page": page}).get("response", []))
        return out

    def _fresh(self, endpoint: str, fetched_at: str | None) -> bool:
        ttl = TTL.get(endpoint, timedelta(days=1))
        if ttl is None:
            return True
        if not fetched_at:
            return False
        return datetime.now(UTC) - datetime.fromisoformat(fetched_at) < ttl

    @retry(
        retry=retry_if_exception_type(_Transient),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, max=30),
        reraise=True,
    )
    def _fetch(self, endpoint: str, params: dict) -> dict:
        self.bucket.wait()
        resp = self.http.get(f"/{endpoint}", params=params)
        remaining = resp.headers.get("x-ratelimit-requests-remaining")
        self.session.add(
            ApiUsage(
                day=datetime.now(UTC).date(),
                endpoint=endpoint,
                params=json.dumps(params, sort_keys=True)[:300],
                status=resp.status_code,
                remaining=int(remaining) if remaining and remaining.isdigit() else None,
            )
        )
        self.session.commit()
        if resp.status_code == 429 or resp.status_code >= 500:
            raise _Transient(f"{endpoint} -> HTTP {resp.status_code}")
        resp.raise_for_status()
        payload = resp.json()
        errors = payload.get("errors")
        if errors:  # API-Football reports most errors with HTTP 200
            text = json.dumps(errors)
            if "rateLimit" in text:
                raise _Transient(text)
            if "requests" in text and "limit" in text.lower():
                raise QuotaExhausted(text)
            raise ApiError(text)
        if remaining is not None and remaining.isdigit() and int(remaining) == 0:
            log.warning("API-Football reports 0 requests remaining today")
        return payload
