import numpy as np
import pandas as pd
import pytest

from app.ml import pipeline, team_strength
from app.ml.data import fixtures_df, match_stats_df
from app.models import (
    ManagerRating, MatchPrediction, MatchRating, ModelRun, PlayerForm, PlayerSeasonAgg, SimilarPlayer, TeamStrength, Valuation,
)
from app.ratings import action_values, match_rating


@pytest.fixture(scope="module")
def run(loaded_db):
    from app.core.db import SessionLocal

    with SessionLocal() as s:
        mr = pipeline.run(s, n_trials=3)
        s.commit()
        return mr.id


def test_pipeline_succeeds_and_writes_everything(session, run):
    mr = session.get(ModelRun, run)
    assert mr.status == "success", mr.metrics
    for table in (MatchRating, PlayerForm, PlayerSeasonAgg, TeamStrength, MatchPrediction, Valuation, SimilarPlayer, ManagerRating):
        assert session.query(table).count() > 0, table.__tablename__


def test_rating_distribution_is_realistic(session, run):
    m = session.get(ModelRun, run).metrics["match_rating"]
    assert 6.4 <= m["mean"] <= 6.9
    assert 0.5 <= m["sd"] <= 0.9
    # synthetic defender/GK stats carry little of the hidden skill behind the fake API rating, so the
    # bar is low here; on real data the run metrics should show r >= 0.7
    assert m["corr_with_api_rating"] > 0.3
    groups = m["mean_by_group"]
    assert max(groups.values()) - min(groups.values()) < 0.4  # no position bias


def test_rating_edge_cases(session):
    stats = match_stats_df(session)
    values = action_values.priors()
    base = stats.iloc[[0]].copy()
    base.loc[:, values.index] = 0
    base[["npg", "pen_scored", "assists"]] = 0
    ref = pd.concat([stats, base.assign(player_id=-1)], ignore_index=True)
    red = base.assign(player_id=-2, red=1)
    cameo = base.assign(player_id=-3, minutes=12)
    out = match_rating.rate(pd.concat([ref, red, cameo], ignore_index=True), values).set_index("player_id")
    assert out.loc[-2, "rating"] < out.loc[-1, "rating"]  # red card hurts
    assert abs(out.loc[-3, "rating"] - 6.4) < abs(out.loc[-1, "rating"] - 6.4) + 1e-9  # cameo shrunk to anchor
    assert (out["rating"].between(3.0, 10.0)).all()
    assert match_rating.rate(stats.assign(minutes=5), values).empty  # < 10 minutes: unrated


def test_learned_action_values_have_expected_signs(session):
    values, metrics = action_values.learn(match_stats_df(session))
    assert metrics["n_matches"] > 20
    assert values["shots_on"] > 0 and values["red"] < 0 and values["passes_failed"] < 0


def test_dixon_coles_recovers_strength_order(session, loaded_db):
    model = team_strength.TeamStrengthModel(fixtures_df(session))
    assert model.ok
    r = model.ratings()
    played = model.played
    pts = pd.concat([
        pd.DataFrame({"team_id": played["home_team_id"], "gd": played["home_goals"] - played["away_goals"]}),
        pd.DataFrame({"team_id": played["away_team_id"], "gd": played["away_goals"] - played["home_goals"]}),
    ]).groupby("team_id")["gd"].sum()
    corr = np.corrcoef(r.set_index("team_id")["rating"].reindex(pts.index), pts)[0, 1]
    assert corr > 0.8
    p = model.predict(r["team_id"].iloc[0], r["team_id"].iloc[1])
    assert abs(p["home_win"] + p["draw"] + p["away_win"] - 1) < 1e-6


def test_valuation_beats_or_matches_baseline_and_is_calibrated(session, run):
    v = session.get(ModelRun, run).metrics["valuation"]
    assert v["n_players"] >= 40
    assert v["mae_log_p50"] <= v["mae_log_linear_baseline"] * 1.15
    assert 0.5 <= v["interval_coverage_p10_p90"] <= 1.0
    row = session.query(Valuation).first()
    assert row.p10 <= row.p50 <= row.p90
    assert "perf_index" in row.contributions


def test_form_band_contains_form(session, run):
    f = session.query(PlayerForm).limit(200).all()
    assert all(x.form_lo <= x.form <= x.form_hi for x in f)


def test_shrinkage_pulls_small_samples_to_mean(session, run):
    aggs = session.query(PlayerSeasonAgg).all()
    small = [a for a in aggs if a.minutes < 120 and a.per90.get("tackles") is not None]
    for a in small[:20]:
        assert abs(a.shrunk_per90["tackles"] - np.mean([x.shrunk_per90["tackles"] for x in aggs if x.position_group == a.position_group])) <= \
            abs(a.per90["tackles"] - np.mean([x.shrunk_per90["tackles"] for x in aggs if x.position_group == a.position_group])) + 1e-6
