from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"), extra="ignore", populate_by_name=True
    )

    # database
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'scout.db'}"

    # api-football
    api_football_key: str = ""
    api_football_base_url: str = "https://v3.football.api-sports.io"
    daily_quota: int = 100
    per_minute_limit: int = 10
    leagues_csv: str = Field("39", alias="LEAGUES")
    season: int = 2025

    # transfermarkt open dataset (dcaribou/transfermarkt-datasets)
    transfermarkt_base_url: str = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data"
    # api-football league id -> transfermarkt competition id
    tm_competitions: dict[int, str] = {39: "GB1", 140: "ES1", 78: "L1", 135: "IT1", 61: "FR1"}

    # object storage: "local" (filesystem) or "s3" (MinIO / any S3-compatible)
    storage_backend: str = "local"
    local_storage_dir: str = str(BACKEND_DIR / "data" / "objects")
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "scout"
    s3_region: str = "us-east-1"

    # mlflow (empty = disabled, runs are still recorded in model_runs)
    mlflow_tracking_uri: str = ""
    mlflow_experiment: str = "moneyball-scout"

    # scheduler
    sync_cron_hour: int = 4
    cors_origins_csv: str = Field("http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def leagues(self) -> list[int]:
        return [int(x) for x in self.leagues_csv.replace(" ", "").split(",") if x]

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins_csv.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
