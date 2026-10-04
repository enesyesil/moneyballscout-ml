import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import fixtures, players, system, teams
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Moneyball Scout API",
    version="0.1.0",
    description="Live football data from API-Football, match ratings, form, valuations and manager ratings.",
)
app.add_middleware(
    CORSMiddleware, allow_origins=get_settings().cors_origins, allow_methods=["GET"], allow_headers=["*"]
)
for r in (system.router, players.router, fixtures.router, teams.router):
    app.include_router(r, prefix="/api")
