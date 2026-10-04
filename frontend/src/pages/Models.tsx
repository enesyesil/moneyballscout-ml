import { useModelRuns, useSyncStatus } from "../api/client";
import ContributionBars from "../components/charts/ContributionBars";
import { Card, Empty, ErrorBox, Loading, Stat, Table, td, th } from "../components/ui";

type M = Record<string, unknown>;
const get = (o: unknown, ...path: string[]): unknown => path.reduce<unknown>((a, k) => (a && typeof a === "object" ? (a as M)[k] : undefined), o);
const n = (v: unknown, d = 3) => (typeof v === "number" ? v.toFixed(d) : "—");

const ACTION_LABEL: Record<string, string> = {
  shots_on: "Shot on target", shots_off: "Shot off target", key_passes: "Key pass", dribbles_success: "Dribble won",
  dribbles_failed: "Dribble lost", passes_accurate: "Accurate pass", passes_failed: "Failed pass", tackles: "Tackle",
  interceptions: "Interception", blocks: "Block", duels_won: "Duel won", duels_lost: "Duel lost", fouls_drawn: "Foul drawn",
  fouls_committed: "Foul committed", dribbled_past: "Dribbled past", offsides: "Offside", yellow: "Yellow card", red: "Red card",
  saves: "Save", pen_won: "Penalty won", pen_committed: "Penalty conceded", pen_missed: "Penalty missed", pen_saved: "Penalty saved",
};

export default function Models() {
  const runs = useModelRuns();
  const sync = useSyncStatus();
  if (runs.isLoading) return <Loading />;
  if (runs.error) return <ErrorBox error={runs.error} />;
  const list = runs.data ?? [];
  const latest = list.find((r) => r.status === "success");
  const m = latest?.metrics;
  const values = (get(m, "action_values", "values") ?? {}) as Record<string, number>;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Models</h1>
        <p className="max-w-3xl text-sm text-ink-3">
          Every daily run is versioned. Ratings come from action values learned from match outcomes; form is a Kalman filter;
          team strength is Dixon–Coles (penaltyblog); valuations are LightGBM quantiles with SHAP explanations and conformal intervals.
        </p>
      </div>

      {!latest ? <Card><Empty>No successful model run yet.</Empty></Card> : (
        <>
          <div className="grid gap-5 lg:grid-cols-3">
            <Card title="Match ratings" subtitle={`Run #${latest.id}`}>
              <div className="grid grid-cols-2 gap-4">
                <Stat label="Mean / SD" value={`${n(get(m, "match_rating", "mean"), 2)} / ${n(get(m, "match_rating", "sd"), 2)}`} hint="target 6.7 / 0.75" />
                <Stat label="r vs API-Football" value={n(get(m, "match_rating", "corr_with_api_rating"), 2)} hint="sanity check, not a target" />
                <Stat label="Matches learned from" value={String(get(m, "action_values", "n_matches") ?? "—")}
                  hint={`blend weight ${n(get(m, "action_values", "blend_weight"), 2)}`} />
                <Stat label="CV R² (goal diff)" value={n(get(m, "action_values", "cv_r2_goal_diff"), 2)} />
              </div>
            </Card>
            <Card title="Valuation" subtitle="LightGBM quantile regression, 5-fold out-of-fold">
              <div className="grid grid-cols-2 gap-4">
                <Stat label="MAE (log)" value={n(get(m, "valuation", "mae_log_p50"))} hint={`linear baseline ${n(get(m, "valuation", "mae_log_linear_baseline"))}`} />
                <Stat label="Median error" value={typeof get(m, "valuation", "median_abs_pct_error_p50") === "number"
                  ? `${Math.round((get(m, "valuation", "median_abs_pct_error_p50") as number) * 100)}%` : "—"} />
                <Stat label="P10–P90 coverage" value={n(get(m, "valuation", "interval_coverage_p10_p90"), 2)}
                  hint={`before conformal ${n(get(m, "valuation", "interval_coverage_before_conformal"), 2)}`} />
                <Stat label="Players" value={String(get(m, "valuation", "n_players") ?? "—")} />
              </div>
            </Card>
            <Card title="Team strength" subtitle="Dixon–Coles, time-decayed">
              <div className="grid grid-cols-2 gap-4">
                <Stat label="Brier score" value={n(get(m, "team_strength", "brier"))} hint={`base rates ${n(get(m, "team_strength", "brier_base_rates"))}`} />
                <Stat label="Home advantage" value={n(get(m, "team_strength", "home_advantage"), 2)} hint="log goals" />
                <Stat label="Matches" value={String(get(m, "team_strength", "matches") ?? "—")} />
                <Stat label="rho" value={n(get(m, "team_strength", "rho"), 3)} hint="low-score correction" />
              </div>
            </Card>
          </div>

          <Card title="What each action is worth" subtitle="Goal-difference value of one action, learned from results and blended with priors">
            <ContributionBars valueLabel="Goal-diff value" format={(x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(3)}`}
              items={Object.entries(values).map(([k, v]) => ({ label: ACTION_LABEL[k] ?? k, value: v }))} />
          </Card>
        </>
      )}

      {sync.data && (
        <Card title="Data sync" subtitle="API-Football quota and backfill">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Quota today" value={`${sync.data.used_today}/${sync.data.daily_quota}`} />
            <Stat label="Fixtures" value={`${sync.data.fixtures_finished}/${sync.data.fixtures_total}`} hint="finished / total" />
            <Stat label="With player stats" value={sync.data.fixtures_with_player_stats} />
            <Stat label="Backfill pending" value={sync.data.backfill_pending} />
          </div>
        </Card>
      )}

      <Card title="Run history">
        <Table>
          <thead><tr>
            <th className={th}>Run</th><th className={th}>When</th><th className={th}>Status</th><th className={th}>Data through</th>
            <th className={`${th} text-right`}>Rating mean</th><th className={`${th} text-right`}>Valuation MAE</th><th className={th}>MLflow</th>
          </tr></thead>
          <tbody>
            {list.map((r) => (
              <tr key={r.id}>
                <td className={`${td} num`}>#{r.id}</td>
                <td className={td}>{new Date(r.created_at).toLocaleString()}</td>
                <td className={td}>
                  <span className={r.status === "success" ? "text-[var(--good-text)]" : r.status === "failed" ? "text-[var(--critical)]" : "text-ink-2"}>
                    {r.status === "success" ? "✓ " : r.status === "failed" ? "✕ " : "… "}{r.status}
                  </span>
                </td>
                <td className={td}>{r.data_cutoff ? new Date(r.data_cutoff).toLocaleDateString() : "—"}</td>
                <td className={`${td} num text-right`}>{n(get(r.metrics, "match_rating", "mean"), 2)}</td>
                <td className={`${td} num text-right`}>{n(get(r.metrics, "valuation", "mae_log_p50"))}</td>
                <td className={`${td} text-ink-3`}>{r.mlflow_run_id ? r.mlflow_run_id.slice(0, 8) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}
