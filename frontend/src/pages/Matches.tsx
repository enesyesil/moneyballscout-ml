import { useState } from "react";
import { Link } from "react-router";
import { useFixtures } from "../api/client";
import ProbBar from "../components/charts/ProbBar";
import { Card, Empty, ErrorBox, Loading, Segmented, TeamLogo } from "../components/ui";
import { dateTime } from "../lib/format";

export default function Matches() {
  const [status, setStatus] = useState<"played" | "upcoming">("played");
  const fixtures = useFixtures({ status, limit: 60 });
  const rows = fixtures.data ?? [];
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Matches</h1>
          <p className="text-sm text-ink-3">Results with our player ratings, and Dixon–Coles predictions for what's next.</p>
        </div>
        <Segmented label="Matches" value={status} onChange={setStatus}
          options={[{ value: "played", label: "Results" }, { value: "upcoming", label: "Upcoming" }]} />
      </div>
      <Card>
        {fixtures.isLoading ? <Loading /> : fixtures.error ? <ErrorBox error={fixtures.error} /> :
          rows.length === 0 ? <Empty>No matches.</Empty> : (
            <ul className="divide-y divide-[var(--border)]">
              {rows.map((f) => (
                <li key={f.id}>
                  <Link to={`/matches/${f.id}`}
                    className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 rounded-lg px-1 py-2.5 hover:bg-surface-2/60 sm:grid-cols-[110px_1fr_auto_1fr_200px]">
                    <span className="col-span-3 text-[12px] text-ink-3 sm:col-span-1">{f.round?.replace("Regular Season - ", "Round ")} · {dateTime(f.date)}</span>
                    <span className="flex min-w-0 items-center justify-end gap-2 text-right font-medium">
                      <span className="truncate">{f.home.name}</span><TeamLogo src={f.home.logo} />
                    </span>
                    <span className="num min-w-14 rounded-md bg-surface-2 px-2 py-1 text-center font-semibold">
                      {f.home_goals != null ? `${f.home_goals} – ${f.away_goals}` : "vs"}
                    </span>
                    <span className="flex min-w-0 items-center gap-2 font-medium">
                      <TeamLogo src={f.away.logo} /><span className="truncate">{f.away.name}</span>
                    </span>
                    <span className="col-span-3 sm:col-span-1"><ProbBar fixture={f} /></span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
      </Card>
    </div>
  );
}
