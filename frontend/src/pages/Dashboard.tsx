import { Link } from "react-router";
import { type SyncStatus, useDashboard, useSyncStatus } from "../api/client";
import ProbBar from "../components/charts/ProbBar";
import PlayerTable from "../components/PlayerTable";
import { Avatar, Card, Empty, ErrorBox, Loading, PosChip, RatingBadge, Stat, TeamLogo } from "../components/ui";
import { dateTime } from "../lib/format";

/** Explains empty or thin numbers while the quota-limited first load and backfill are still running. */
function DataStatus({ hasRun, sync }: { hasRun: boolean; sync?: SyncStatus }) {
  const progress = sync ? `${sync.fixtures_with_player_stats} of ${sync.fixtures_finished} finished matches` : null;
  let message: string;
  if (!hasRun) {
    message = `The first data load is running${progress ? ` (${progress} synced so far)` : ""}. Ratings, form and valuations appear after the first model run.`;
  } else if (sync && sync.backfill_pending > 0) {
    message = `Backfill in progress: ${sync.backfill_pending} finished matches still to sync (the API allows ${sync.daily_quota} requests a day). Numbers firm up as they arrive.`;
  } else {
    return null;
  }
  return (
    <div role="status" className="flex items-start gap-2.5 rounded-lg border border-line bg-surface-2 p-3 text-sm text-ink-2">
      <span aria-hidden className="mt-1.5 size-2 shrink-0 animate-pulse rounded-full bg-accent" />
      <p>{message}</p>
    </div>
  );
}

export default function Dashboard() {
  const { data, isLoading, error } = useDashboard();
  const sync = useSyncStatus();
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  const rm = data.latest_run?.metrics as Record<string, Record<string, number>> | undefined;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Scouting dashboard</h1>
          <p className="text-sm text-ink-3">Who is playing well, who is cheap for how they play, and what's coming up.</p>
        </div>
      </div>

      <DataStatus hasRun={!!data.latest_run} sync={sync.data} />

      <div className="card grid grid-cols-2 gap-4 p-4 sm:grid-cols-4 sm:p-5">
        <Stat label="Matches with player stats" value={sync.data ? `${sync.data.fixtures_with_player_stats}/${sync.data.fixtures_finished}` : "—"}
          hint={sync.data?.backfill_pending ? `${sync.data.backfill_pending} still to backfill` : "fully synced"} />
        <Stat label="Ratings this season" value={rm?.match_rating?.n_ratings?.toLocaleString() ?? "—"}
          hint={rm?.match_rating ? `mean ${rm.match_rating.mean} · sd ${rm.match_rating.sd}` : undefined} />
        <Stat label="Valuation error" value={rm?.valuation?.median_abs_pct_error_p50 != null ? `${Math.round(rm.valuation.median_abs_pct_error_p50 * 100)}%` : "—"}
          hint="median, out-of-fold" />
        <Stat label="API quota today" value={sync.data ? `${sync.data.used_today}/${sync.data.daily_quota}` : "—"} hint="requests used" />
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-2" title="Team of the week" subtitle={data.round ?? undefined}>
          {data.team_of_the_week.length === 0 ? <Empty>No rated matches yet.</Empty> : (
            <ul className="divide-y divide-[var(--border)]">
              {data.team_of_the_week.map((p) => (
                <li key={p.player_id} className="flex items-center gap-3 py-2">
                  <PosChip pos={p.position_group} />
                  <Avatar src={p.photo} name={p.name} size={28} />
                  <Link to={`/players/${p.player_id}`} className="min-w-0 flex-1 truncate font-medium hover:text-accent">{p.name}</Link>
                  <span className="hidden truncate text-[12px] text-ink-3 sm:inline">{p.team.name}</span>
                  <RatingBadge value={p.rating} />
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card className="lg:col-span-3" title="Upcoming matches" subtitle="Win/draw/loss from the Dixon–Coles team model">
          {data.upcoming.length === 0 ? <Empty>No upcoming fixtures.</Empty> : (
            <ul className="divide-y divide-[var(--border)]">
              {data.upcoming.map((f) => (
                <li key={f.id} className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 py-2.5 sm:grid-cols-[1fr_auto_1fr_minmax(160px,220px)]">
                  <span className="flex min-w-0 items-center justify-end gap-2 text-right font-medium">
                    <span className="truncate">{f.home.name}</span><TeamLogo src={f.home.logo} />
                  </span>
                  <span className="text-[11px] text-ink-3">{dateTime(f.date)}</span>
                  <span className="flex min-w-0 items-center gap-2 font-medium">
                    <TeamLogo src={f.away.logo} /><span className="truncate">{f.away.name}</span>
                  </span>
                  <div className="col-span-3 sm:col-span-1"><ProbBar fixture={f} /></div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="In form" subtitle="Highest current form (Kalman-filtered match ratings), 450+ minutes">
          <PlayerTable rows={data.in_form} cols={["age", "rating", "form", "pi"]} />
        </Card>
        <Card title="Most undervalued" subtitle="Market value furthest below the model's estimate"
          action={<Link to="/moneyball" className="text-[13px] font-medium text-accent">Explore →</Link>}>
          <PlayerTable rows={data.undervalued} cols={["age", "pi", "value", "model", "under"]} />
        </Card>
      </div>
    </div>
  );
}
