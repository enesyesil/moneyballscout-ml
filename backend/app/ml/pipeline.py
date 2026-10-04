"""End-to-end model run: team strength -> match ratings -> form -> aggregates -> valuation ->
similarity -> managers. Every derived table is rewritten in one transaction and stamped with the
`model_runs` id; the run is logged to MLflow (when configured) and artifacts go to object storage."""

import io
import logging
import os
import subprocess

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.storage import Storage, get_storage
from app.ml import form as form_mod
from app.ml import manager as manager_mod
from app.ml import shrinkage, similarity, team_strength, valuation
from app.ml.data import fixtures_df, match_stats_df, positions_config
from app.models import (
    CoachTenure, MarketValue, MatchPrediction, MatchRating, ManagerRating, ModelRun, Player, PlayerForm,
    PlayerLink, PlayerSeasonAgg, SimilarPlayer, TeamStrength, TMPlayer, Valuation,
)
from app.ratings import action_values, match_rating

log = logging.getLogger(__name__)

DERIVED = [MatchRating, PlayerForm, PlayerSeasonAgg, TeamStrength, MatchPrediction, Valuation, SimilarPlayer, ManagerRating]


def _py(v):
    """numpy / pandas scalars -> plain Python for the DB and JSON columns."""
    if isinstance(v, dict):
        return {k: _py(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [_py(x) for x in v]
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and np.isnan(v):
        return None
    if v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp):
        return v.to_pydatetime()
    return v


def _records(df: pd.DataFrame, cols: list[str], **extra) -> list[dict]:
    return [{**{c: _py(r[c]) for c in cols}, **extra} for r in df[cols].to_dict("records")]


def _git_sha() -> str | None:
    if os.getenv("GIT_SHA"):
        return os.environ["GIT_SHA"][:40]
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:  # noqa: BLE001
        return None


def market_values_now(session: Session) -> pd.DataFrame:
    """player_id -> current market value and contract expiry, via the Transfermarkt link."""
    links = pd.read_sql(select(PlayerLink.player_id, PlayerLink.tm_player_id), session.bind)
    tm = pd.read_sql(select(TMPlayer.id, TMPlayer.market_value, TMPlayer.contract_expiration), session.bind)
    if links.empty or tm.empty:
        return pd.DataFrame(columns=["player_id", "tm_player_id", "market_value", "contract_expiration"])
    latest = pd.read_sql(select(MarketValue.tm_player_id, MarketValue.date, MarketValue.value_eur), session.bind)
    if not latest.empty:
        latest = latest.sort_values("date").groupby("tm_player_id")["value_eur"].last()
        tm["market_value"] = tm["market_value"].fillna(tm["id"].map(latest))
    return links.merge(tm.rename(columns={"id": "tm_player_id"}), on="tm_player_id", how="left")


def run(session: Session, storage: Storage | None = None, n_trials: int = 20) -> ModelRun:
    storage = storage or get_storage()
    s = get_settings()
    mr = ModelRun(status="running", git_sha=_git_sha(), params={"season": s.season, "leagues": s.leagues, "optuna_trials": n_trials})
    session.add(mr)
    session.commit()
    metrics: dict = {}
    try:
        _run(session, storage, mr, metrics, n_trials)
        mr.status = "success"
    except Exception as e:
        session.rollback()
        mr = session.get(ModelRun, mr.id)
        mr.status = "failed"
        metrics["error"] = repr(e)[:500]
        log.exception("model run failed")
    mr.metrics = _py(metrics)
    _log_mlflow(mr, mr.metrics)
    session.commit()
    return mr


def _run(session: Session, storage: Storage, mr: ModelRun, metrics: dict, n_trials: int) -> None:
    s = get_settings()
    fixtures = fixtures_df(session)
    if fixtures.empty:
        raise RuntimeError("no fixtures loaded - run a sync first")
    fixtures = fixtures[fixtures["season"] == s.season]
    stats = match_stats_df(session)
    stats = stats[stats["season"] == s.season] if not stats.empty else stats
    if stats.empty:
        raise RuntimeError("no player match stats loaded yet")
    mr.data_cutoff = fixtures.loc[fixtures["finished"], "date"].max().to_pydatetime()
    cutoff = pd.Timestamp(mr.data_cutoff)

    # 1. team strength (Dixon-Coles)
    ts = team_strength.TeamStrengthModel(fixtures)
    team_df = ts.ratings() if ts.ok else pd.DataFrame(columns=["team_id", "attack", "defence", "rating"])
    opp_z = {}
    if not team_df.empty:
        team_df["rating_z"] = (team_df["rating"] - team_df["rating"].mean()) / (team_df["rating"].std() or 1)
        opp_z = dict(zip(team_df["team_id"], team_df["rating_z"], strict=True))
        metrics["team_strength"] = {"matches": int(len(ts.played)), "home_advantage": round(float(ts.params.get("home_advantage", 0)), 4),
                                    "rho": round(float(ts.params.get("rho", 0)), 4)}

    # 2. match ratings
    values, av_metrics = action_values.learn(stats)
    rated = match_rating.rate(stats, values, opp_z)
    metrics["action_values"] = {"values": values.round(5).to_dict(), **av_metrics}
    metrics["match_rating"] = match_rating.validation_metrics(rated)

    # 3. form (Kalman)
    form_series, form_params = form_mod.compute_form(rated)
    metrics["form"] = form_params

    # 4. season aggregates, shrinkage, percentiles, Performance Index
    season_stats = stats[stats["minutes"] > 0]
    totals = shrinkage.season_totals(season_stats)
    raw90, shrunk90 = shrinkage.shrink(totals)
    pct = shrinkage.percentiles(shrunk90, totals)
    pi = shrinkage.performance_index(shrunk90, totals, values)

    players = pd.read_sql(select(Player.id, Player.birth_date, Player.team_id), session.bind).set_index("id")
    team_matches = pd.concat([fixtures.loc[fixtures["finished"], "home_team_id"], fixtures.loc[fixtures["finished"], "away_team_id"]]).value_counts()
    last_form = form_series.sort_values("date").groupby("player_id").last() if not form_series.empty else pd.DataFrame()
    mins_w = rated.assign(w=rated["rating"] * rated["minutes"]).groupby("player_id")[["w", "minutes"]].sum()
    avg_rating = (mins_w["w"] / mins_w["minutes"]).round(3)
    upcoming = fixtures[fixtures["status"].isin(["NS", "TBD"])].sort_values("date")
    next_opp: dict[int, int] = {}
    for fx in upcoming.itertuples():
        next_opp.setdefault(fx.home_team_id, fx.away_team_id)
        next_opp.setdefault(fx.away_team_id, fx.home_team_id)
    adj = action_values.weights_config()["rating_scale"]["opponent_adjust"]

    agg = totals.copy()
    agg["player_id"] = agg.index
    birth = pd.to_datetime(players["birth_date"].reindex(agg.index))
    agg["age"] = ((cutoff.tz_localize(None) - birth).dt.days / 365.25).round(1)
    agg["avg_rating"] = avg_rating.reindex(agg.index)
    if not last_form.empty:
        agg["form"] = last_form["form"].reindex(agg.index)
        agg["form_sd"] = last_form["form_sd"].reindex(agg.index)
    else:
        agg["form"], agg["form_sd"] = np.nan, np.nan
    opp_next_z = agg["team_id"].map(next_opp).map(opp_z).fillna(0.0)
    # opponent effect in rating units: adj (share of process value per SD) x rating SD
    rating_sd = action_values.weights_config()["rating_scale"]["sd"]
    agg["expected_next"] = (agg["form"] - adj * rating_sd * opp_next_z).round(2)
    agg["perf_index"] = pi.reindex(agg.index)
    agg["per90"] = [_py(r) for r in raw90.round(3).to_dict("records")]
    agg["shrunk_per90"] = [_py(r) for r in shrunk90.round(3).to_dict("records")]
    agg["percentiles"] = [_py(r) for r in pct.to_dict("records")]
    agg["minutes_share"] = agg["minutes"] / (agg["team_id"].map(team_matches).fillna(1) * 90)

    # 5. valuation (LightGBM quantiles + SHAP)
    mv = market_values_now(session).set_index("player_id")
    agg["market_value"] = mv["market_value"].reindex(agg.index)
    contract = pd.to_datetime(mv["contract_expiration"].reindex(agg.index))
    agg["contract_expiration"] = contract.dt.date
    agg["contract_years_left"] = ((contract - cutoff.tz_localize(None)).dt.days / 365.25).clip(lower=0).round(2)
    agg["team_rating"] = agg["team_id"].map(dict(zip(team_df["team_id"], team_df["rating"], strict=True)) if not team_df.empty else {})
    league_scores = positions_config()["league_scores"]
    agg["league_coef"] = league_scores.get(s.leagues[0], 3.0)
    train = agg[(agg["minutes"] >= 270) & agg["market_value"].notna()]
    vals, val_metrics, models = valuation.fit_predict(train, n_trials=n_trials)
    metrics["valuation"] = val_metrics

    # 6. similar players
    sims = similarity.similar_players(pct, totals)

    # 7. team aggregates + predictions
    team_pts = team_strength.team_match_points(ts) if ts.ok else pd.DataFrame()
    squad_value = agg.groupby("team_id")["market_value"].sum(min_count=1)
    team_avg_rating = rated.groupby("team_id")["rating"].mean()
    preds = team_strength.predict_fixtures(ts, upcoming) if ts.ok else pd.DataFrame()
    if ts.ok and not preds.empty:
        played_preds = team_strength.predict_fixtures(ts, fixtures[fixtures["finished"]])
        preds = pd.concat([preds, played_preds], ignore_index=True)
        actual = fixtures[fixtures["finished"]].set_index("id")
        pp = played_preds.set_index("fixture_id").join(actual[["home_goals", "away_goals"]])
        outcome = np.select([pp["home_goals"] > pp["away_goals"], pp["home_goals"] == pp["away_goals"]], [0, 1], 2)
        probs = pp[["home_win", "draw", "away_win"]].to_numpy()
        onehot = np.eye(3)[outcome]
        base = onehot.mean(axis=0)
        metrics["team_strength"]["brier"] = round(float(((probs - onehot) ** 2).sum(axis=1).mean()), 4)
        metrics["team_strength"]["brier_base_rates"] = round(float(((base - onehot) ** 2).sum(axis=1).mean()), 4)
    elif ts.ok:
        preds = team_strength.predict_fixtures(ts, fixtures[fixtures["finished"]])

    # 8. managers
    tenures = pd.read_sql(select(CoachTenure.coach_id, CoachTenure.team_id, CoachTenure.start, CoachTenure.end), session.bind)
    managers = manager_mod.rate_managers(tenures, team_pts, squad_value, rated)

    # ---- write everything in one transaction
    for table in DERIVED:
        session.execute(delete(table))
    run_id = mr.id
    session.bulk_insert_mappings(MatchRating, _records(
        rated, ["fixture_id", "player_id", "team_id", "position_group", "minutes", "rating", "raw_score", "components"], model_run_id=run_id))
    if not form_series.empty:
        session.bulk_insert_mappings(PlayerForm, _records(
            form_series, ["player_id", "fixture_id", "date", "rating", "form", "form_lo", "form_hi"], model_run_id=run_id))
    agg_cols = ["player_id", "team_id", "position_group", "age", "apps", "minutes", "goals", "assists", "avg_rating", "form",
                "form_sd", "expected_next", "perf_index", "market_value", "contract_expiration", "per90", "shrunk_per90", "percentiles"]
    session.bulk_insert_mappings(PlayerSeasonAgg, _records(agg, agg_cols, model_run_id=run_id, season=s.season))
    if not team_df.empty:
        tp = team_pts.groupby("team_id").agg(played=("pts", "size"), points=("pts", "sum"), xpts=("xpts", "sum"),
                                             goals_for=("gf", "sum"), goals_against=("ga", "sum"))
        team_df = team_df.join(tp, on="team_id")
        team_df["avg_player_rating"] = team_df["team_id"].map(team_avg_rating).round(3)
        team_df["squad_value"] = team_df["team_id"].map(squad_value)
        team_df["series"] = [
            [{"date": d.date().isoformat(), "fixture_id": int(f), "opponent_id": int(o), "gf": int(gf), "ga": int(ga),
              "pts": int(p), "xpts": round(float(x), 3)}
             for f, d, o, gf, ga, p, x in team_pts[team_pts["team_id"] == t].sort_values("date")[
                 ["fixture_id", "date", "opponent_id", "gf", "ga", "pts", "xpts"]].itertuples(index=False)]
            for t in team_df["team_id"]
        ]
        team_df["xpts"] = team_df["xpts"].round(2)
        session.bulk_insert_mappings(TeamStrength, _records(
            team_df, ["team_id", "attack", "defence", "rating", "played", "points", "xpts", "goals_for", "goals_against",
                      "avg_player_rating", "squad_value", "series"], model_run_id=run_id))
    if not preds.empty:
        session.bulk_insert_mappings(MatchPrediction, _records(
            preds.drop_duplicates("fixture_id"), ["fixture_id", "home_win", "draw", "away_win", "exp_home_goals", "exp_away_goals"],
            model_run_id=run_id))
    if not vals.empty:
        session.bulk_insert_mappings(Valuation, _records(
            vals, ["player_id", "market_value", "p10", "p50", "p90", "undervalue_score", "below_p10", "contributions"], model_run_id=run_id))
    if not sims.empty:
        session.bulk_insert_mappings(SimilarPlayer, _records(sims, ["player_id", "similar_player_id", "similarity", "rank"], model_run_id=run_id))
    if not managers.empty:
        session.bulk_insert_mappings(ManagerRating, _records(
            managers, ["coach_id", "team_id", "tenure_start", "matches", "ppg", "xppg", "pts_over_exp", "squad_efficiency",
                       "development", "score", "series"], model_run_id=run_id))
    session.flush()

    # ---- artifacts
    prefix = f"models/run-{run_id}"
    buf = io.BytesIO()
    joblib.dump({"action_values": values, "valuation_models": models, "dixon_coles_params": ts.params, "form_params": form_params}, buf)
    storage.put_bytes(f"{prefix}/models.joblib", buf.getvalue())
    mr.artifact_prefix = prefix
    metrics["counts"] = {"ratings": len(rated), "players": len(agg), "valuations": len(vals), "managers": len(managers),
                         "teams": len(team_df)}


def _log_mlflow(mr: ModelRun, metrics: dict) -> None:
    s = get_settings()
    if not s.mlflow_tracking_uri:
        return
    try:
        import mlflow

        mlflow.set_tracking_uri(s.mlflow_tracking_uri)
        mlflow.set_experiment(s.mlflow_experiment)
        flat: dict[str, float] = {}

        def walk(prefix: str, d: dict) -> None:
            for k, v in d.items():
                if isinstance(v, dict) and k not in ("values", "learned", "params"):
                    walk(f"{prefix}{k}.", v)
                elif isinstance(v, int | float) and not isinstance(v, bool) and v is not None:
                    flat[f"{prefix}{k}"] = float(v)

        walk("", metrics)
        with mlflow.start_run(run_name=f"run-{mr.id}") as r:
            mlflow.set_tags({"status": mr.status, "git_sha": mr.git_sha or "", "model_run_id": str(mr.id)})
            mlflow.log_params({k: str(v) for k, v in (mr.params or {}).items()})
            mlflow.log_metrics({k.replace("%", "pct"): v for k, v in flat.items()})
            mlflow.log_dict(metrics, "metrics.json")
            mr.mlflow_run_id = r.info.run_id
    except Exception:  # noqa: BLE001 - tracking must never break a run
        log.exception("mlflow logging failed")


def latest_run(session: Session) -> ModelRun | None:
    return session.scalar(select(ModelRun).where(ModelRun.status == "success").order_by(ModelRun.id.desc()).limit(1))

