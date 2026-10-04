# Moneyball Scout

Find football players whose market value doesn't match how they actually play, using live data.

The original course project ([`legacy/`](legacy/)) scored players from a frozen FBref/Transfermarkt CSV snapshot in a
notebook. This version runs as a service: it pulls match data from **API-Football**, market values from the open
**Transfermarkt dataset**, runs a small set of explainable models every day and serves the results to a React app.

## What it computes

| Output | How |
|---|---|
| **Match rating** (3–10, per player per match) | Action values (what a shot on target, tackle, failed pass… is worth in goal difference) are **learned from results** with a sign-constrained ridge regression (scikit-learn) and blended with priors. Raw value is adjusted for opponent strength, mapped to the rating scale per position (QuantileTransformer) and shrunk for cameos. Each rating stores its component breakdown. |
| **Form** | Local-level state-space model (statsmodels `UnobservedComponents`, Kalman filter) over each player's ratings → form ± 90% band, and an expected next-match rating. |
| **Season aggregates & Performance Index** | Per-90 stats with **empirical-Bayes shrinkage** (Gamma-Poisson for counts, Beta-Binomial via scipy for rates), percentiles within position, and a position-weighted composite (metric lists ported from the notebook). |
| **Team strength & match probabilities** | Time-decayed **Dixon–Coles** model (penaltyblog) → attack/defence, W/D/L probabilities, expected points. |
| **Valuation (the Moneyball part)** | **LightGBM quantile regression** (P10/P50/P90) of log market value from performance, age, role, contract and team, tuned with **Optuna**, explained with **SHAP**, intervals calibrated with **conformalized quantile regression**. Undervaluation is computed from out-of-fold predictions so the model can't memorise prices. |
| **Similar / cheaper players** | k-nearest neighbours (cosine) on percentile profiles within position. |
| **Manager rating** (0–100) | Points over Dixon–Coles expectation, points relative to squad value, and player rating development, each shrunk by matches managed. |

Every run is versioned in `model_runs` and logged to **MLflow**; artifacts go to object storage.

## Architecture

```
API-Football ─┐  quota-aware client       ┌─ ratings / form / aggregates ─┐
              ├─ (raw JSON archived in ───┤                               ├─ Postgres ─ FastAPI ─ nginx ─ React
Transfermarkt ┘   MinIO, replayable)      └─ Dixon–Coles / LightGBM / kNN ┘      │
                                                                               MLflow
```

- `backend/` FastAPI, SQLAlchemy, Alembic, the ingest jobs, models and the worker (APScheduler).
- `frontend/` Vite, React, TypeScript, TanStack Query, Recharts and Tailwind. API types are generated from OpenAPI.
- `deploy/mlflow/` MLflow tracking server image (Postgres backend, MinIO artifacts).
- `docker-compose.prod.yml` the full stack for Coolify. `docker-compose.yml` runs local Postgres, MinIO and MLflow.

### API quota (free plan: 100 requests/day, 10/minute)

The worker is the only service that calls API-Football. It works through a prioritized queue (fixtures, then
per-match player stats, then profiles, then coaches) and stops cleanly when the daily quota runs out. Every response is archived in
object storage first, so finished matches are never fetched twice, and `rebuild-from-raw` reloads the whole
database without any API calls. Backfilling a Premier League season takes about 4 days. After that, a matchweek costs
about 12 requests. On a paid plan, raise `DAILY_QUOTA` and add league ids to `LEAGUES`; no code changes are needed.

## Run locally

```bash
cd backend && python3.12 -m venv .venv && .venv/bin/pip install --only-binary=:all: -r requirements-dev.txt
```

On macOS LightGBM needs OpenMP (`brew install libomp`).

Try it without an API key, using a synthetic 20-team season:

```bash
cd backend && .venv/bin/alembic upgrade head && .venv/bin/python -m app.cli seed-demo && .venv/bin/python -m app.cli train
```

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to port 8000.

With real data, put `API_FOOTBALL_KEY` in `.env` (see [.env.example](.env.example)), then:

```bash
cd backend && .venv/bin/python -m app.cli transfermarkt && .venv/bin/python -m app.cli daily
```

Other commands: `sync`, `link`, `train --trials 20`, `status`, `rebuild-from-raw`.

Tests (synthetic league, no network):

```bash
cd backend && .venv/bin/pytest -q
```

After changing API schemas, regenerate the frontend types:

```bash
cd backend && .venv/bin/python -c "import json; from app.main import app; json.dump(app.openapi(), open('openapi.json','w'), indent=1)" && cd ../frontend && npm run gen:api
```

## Deploy (Coolify + GitHub Actions)

Two workflows in [`.github/workflows/`](.github/workflows/), both driving Coolify through its API
([`deploy/coolify.py`](deploy/coolify.py)):

| Workflow | When | What it does |
|---|---|---|
| **Bootstrap** | once, by hand (Actions → Bootstrap → Run workflow); safe to re-run | Writes the app's env vars on Coolify (API key, leagues, season, quota; generates the Postgres and MinIO passwords once, never overwrites them), runs a clean build, waits for `/api/health`, then for the worker's first data load and model run. |
| **Deploy** | every push to `main` (PRs: tests only); daily monitor at 06:30 UTC | Backend tests, OpenAPI/TS type drift checks and the frontend build; if green, deploys to Coolify, waits for the build, health-checks the new commit and smoke-tests the main pages. The daily run only checks the live site and fails (GitHub emails you) if it is down or no model run has succeeded in 30h. |

Redeploys don't spend API quota: the worker only runs its start-up sync if there was no successful model run in the
last 20 hours, otherwise it waits for the daily schedule.

### One-time setup

1. **Coolify:** New resource → **Public/Private Repository** (this repo, branch `main`) → build pack **Docker
   Compose**, compose file `/docker-compose.prod.yml`. Don't deploy yet.
   - Set your domain on the **web** service (port 80); Coolify's proxy handles TLS. Optional: a domain on **mlflow**
     (port 5000) behind basic auth.
   - Turn **off** Auto Deploy (GitHub Actions deploys only after the tests pass), and turn **on** "Include Source
     Commit in Build" so `/api/health` reports the running commit.
   - Enable scheduled backups for the `pgdata` volume.
   - Note the application's UUID (in its URL), and create an API token under **Keys & Tokens → API tokens** with
     `write`, `deploy` and `read:sensitive` permissions.
2. **GitHub:**
   - Settings → Environments → **New environment** `production`, with secrets `COOLIFY_TOKEN` (the token above) and
     `API_FOOTBALL_KEY` (from dashboard.api-football.com).
   - Settings → Secrets and variables → Actions → **Variables** (repository level, so the daily monitor sees them
     too): `COOLIFY_URL` (e.g. `https://coolify.example.com`), `COOLIFY_APP_UUID` and `SITE_URL`
     (e.g. `https://scout.example.com`).
3. **Actions → Bootstrap → Run workflow.** The defaults are the Premier League, 2026-27 season, free-plan quota.

After that, `git push` to `main` is all a release takes. The Deploy workflow skips the deploy step (with a warning)
until the `production` environment is configured.

On first start the worker loads Transfermarkt values, syncs what the quota allows and trains; then it runs daily at
`SYNC_CRON_HOUR` UTC (Transfermarkt weekly). To run commands by hand, open the `worker` container's terminal in
Coolify and run e.g. `python -m app.cli status` or `python -m app.cli train`. Progress is on the **Models** page.

## Known limits

- API-Football has no xG or event coordinates, so FBref metrics are mapped to the closest available stats
  (see [positions.yaml](backend/app/ml/positions.yaml)) and possession-value models such as VAEP are out of reach.
- Expected points for played matches come from the same Dixon–Coles fit (in-sample). That's fine for ranking, but not for betting.
- With one league, the league coefficient is constant. It starts to matter once `LEAGUES` lists several leagues.
- Scout accounts and shortlists are planned after the MVP.
