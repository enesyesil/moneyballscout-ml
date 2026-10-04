"""python -m app.cli <command>

  sync              quota-aware API-Football sync (fixtures, match stats, profiles, coaches)
  backfill          sync repeatedly until the quota runs out (same as sync; kept for clarity)
  transfermarkt     download + load the weekly Transfermarkt snapshot, then link players
  link              re-run player linking only
  train             full model run (ratings, form, aggregates, valuation, similarity, managers)
  rebuild-from-raw  reload source tables from object storage (no network), then link
  status            print quota / backfill status
  daily             sync -> link -> train  (what the worker runs)
  seed-demo         load a synthetic league (no API key needed) for local UI work
"""

import argparse
import json
import logging
import sys

from app.core.db import advisory_lock, session_scope
from app.ingest import entity_resolution, jobs, transfermarkt
from app.ml import pipeline

log = logging.getLogger("cli")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="app.cli")
    parser.add_argument("command", choices=["sync", "backfill", "transfermarkt", "link", "train", "rebuild-from-raw", "status", "daily", "seed-demo"])
    parser.add_argument("--trials", type=int, default=20, help="Optuna trials for the valuation model")
    parser.add_argument("--no-download", action="store_true", help="transfermarkt: reuse the latest stored snapshot")
    args = parser.parse_args(argv)

    if args.command == "status":
        with session_scope() as s:
            print(json.dumps(jobs.sync_status(s), indent=2))
        return 0

    with advisory_lock() as acquired:
        if not acquired:
            log.warning("another pipeline run holds the lock; exiting")
            return 1
        with session_scope() as s:
            if args.command in ("sync", "backfill"):
                print(json.dumps(jobs.run_sync(s), indent=2))
            elif args.command == "transfermarkt":
                print(json.dumps(transfermarkt.refresh(s, download=not args.no_download), indent=2))
                s.commit()
                print(json.dumps(entity_resolution.resolve(s), indent=2))
            elif args.command == "link":
                print(json.dumps(entity_resolution.resolve(s), indent=2))
            elif args.command == "train":
                run = pipeline.run(s, n_trials=args.trials)
                print(json.dumps({"run_id": run.id, "status": run.status, "metrics": run.metrics}, indent=2, default=str))
                return 0 if run.status == "success" else 2
            elif args.command == "rebuild-from-raw":
                print(json.dumps(jobs.rebuild_from_raw(s), indent=2))
                try:
                    print(json.dumps(transfermarkt.refresh(s, download=False), indent=2))
                except FileNotFoundError:
                    log.warning("no transfermarkt snapshot stored; skipping market values")
                s.commit()
                print(json.dumps(entity_resolution.resolve(s), indent=2))
            elif args.command == "seed-demo":
                from app import demo

                print(json.dumps(demo.seed(s), indent=2))
            elif args.command == "daily":
                daily(s, n_trials=args.trials)
    return 0


def daily(session, n_trials: int = 20) -> None:
    report = jobs.run_sync(session)
    log.info("sync: %s", report)
    session.commit()
    entity_resolution.resolve(session)
    session.commit()
    run = pipeline.run(session, n_trials=n_trials)
    log.info("model run %s: %s", run.id, run.status)


if __name__ == "__main__":
    sys.exit(main())
