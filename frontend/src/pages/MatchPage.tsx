import { useState } from "react";
import { Link, useParams } from "react-router";
import { type LineupPlayer, useFixture } from "../api/client";
import ContributionBars from "../components/charts/ContributionBars";
import ProbBar from "../components/charts/ProbBar";
import { Avatar, Card, Empty, ErrorBox, Loading, RatingBadge, TeamLogo } from "../components/ui";
import { COMPONENT_LABEL, dateTime, num } from "../lib/format";

function Lineup({ players, onPick, picked }: { players: LineupPlayer[]; onPick: (p: LineupPlayer) => void; picked?: number }) {
  return (
    <ul className="divide-y divide-[var(--border)]">
      {players.map((p) => (
        <li key={p.player_id}>
          <button onClick={() => onPick(p)}
            className={`flex w-full items-center gap-2.5 rounded-md px-1 py-1.5 text-left hover:bg-surface-2/60 ${picked === p.player_id ? "bg-surface-2" : ""}`}>
            <span className="w-5 text-center text-[11px] text-ink-3">{p.position}</span>
            <Avatar src={p.photo} name={p.name} size={26} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium">{p.name}</span>
              <span className="text-[11px] text-ink-3">
                {p.minutes}'{p.substitute ? " · sub" : ""}{p.goals ? ` · ${p.goals} G` : ""}{p.assists ? ` · ${p.assists} A` : ""}
              </span>
            </span>
            <span className="num w-8 text-right text-[12px] text-ink-3" title="API-Football rating">{num(p.api_rating, 1)}</span>
            <RatingBadge value={p.rating} size="sm" />
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function MatchPage() {
  const id = Number(useParams().id);
  const { data, isLoading, error } = useFixture(id);
  const [picked, setPicked] = useState<LineupPlayer | null>(null);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  const f = data.fixture;
  const all = [...data.lineups.home, ...data.lineups.away].filter((p) => p.rating != null);
  const motm = all.sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0))[0];
  const sel = picked ?? motm;

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <div className="text-center text-[12px] text-ink-3">{f.round} · {dateTime(f.date)}</div>
        <div className="mt-3 grid grid-cols-[1fr_auto_1fr] items-center gap-4">
          <Link to={`/teams/${f.home.id}`} className="flex flex-col items-center gap-1 text-center font-semibold hover:text-accent sm:flex-row sm:justify-end">
            <span className="order-2 sm:order-1">{f.home.name}</span><TeamLogo src={f.home.logo} size={36} />
          </Link>
          <div className="num text-3xl font-semibold">{f.home_goals != null ? `${f.home_goals} – ${f.away_goals}` : "vs"}</div>
          <Link to={`/teams/${f.away.id}`} className="flex flex-col items-center gap-1 text-center font-semibold hover:text-accent sm:flex-row">
            <TeamLogo src={f.away.logo} size={36} /><span>{f.away.name}</span>
          </Link>
        </div>
        {f.prediction && (
          <div className="mx-auto mt-4 max-w-md">
            <div className="mb-1 text-center text-[11px] uppercase tracking-wide text-ink-3">Model pre-match probabilities</div>
            <ProbBar fixture={f} />
          </div>
        )}
      </div>

      {all.length === 0 ? <Card><Empty>Player stats for this match aren't synced yet.</Empty></Card> : (
        <div className="grid gap-5 lg:grid-cols-3">
          <Card title={f.home.name} subtitle="Our rating (badge) · API-Football (grey)">
            <Lineup players={data.lineups.home} onPick={setPicked} picked={sel?.player_id} />
          </Card>
          <Card title={f.away.name} subtitle="Our rating (badge) · API-Football (grey)">
            <Lineup players={data.lineups.away} onPick={setPicked} picked={sel?.player_id} />
          </Card>
          <Card title={sel ? sel.name : "Breakdown"}
            subtitle={sel ? <>Rating {num(sel.rating, 2)}{sel === motm ? " · player of the match" : ""} · click any player</> : undefined}
            action={sel && <Link to={`/players/${sel.player_id}`} className="text-[13px] font-medium text-accent">Profile →</Link>}>
            {sel ? (
              <ContributionBars valueLabel="Goal-diff value" format={(x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(3)}`}
                items={Object.entries(sel.components).filter(([k, x]) => k !== "opponent_factor" && Math.abs(x) > 1e-4)
                  .map(([k, x]) => ({ label: COMPONENT_LABEL[k] ?? k, value: x }))} />
            ) : <Empty>Pick a player.</Empty>}
          </Card>
        </div>
      )}
    </div>
  );
}
