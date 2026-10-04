import { Link, useParams } from "react-router";
import { useFixtures, useTeam } from "../api/client";
import PointsVsExpected from "../components/charts/PointsVsExpected";
import ProbBar from "../components/charts/ProbBar";
import PlayerTable from "../components/PlayerTable";
import { Avatar, Card, Empty, ErrorBox, Loading, Stat, TeamLogo } from "../components/ui";
import { dateTime, eur, num, signed } from "../lib/format";

export default function TeamPage() {
  const id = Number(useParams().id);
  const { data, isLoading, error } = useTeam(id);
  const upcoming = useFixtures({ status: "upcoming", team_id: id, limit: 5 });
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  const t = data.team;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <TeamLogo src={t.team.logo} size={48} />
        <h1 className="text-2xl font-semibold tracking-tight">{t.team.name}</h1>
      </div>
      <div className="card grid grid-cols-2 gap-4 p-4 sm:grid-cols-3 sm:p-5 lg:grid-cols-6">
        <Stat label="Points" value={t.points ?? "—"} hint={`${t.played ?? 0} played`} />
        <Stat label="Expected points" value={num(t.xpts, 1)} hint={`${signed((t.points ?? 0) - (t.xpts ?? 0), 1)} vs expected`} />
        <Stat label="Goals" value={`${t.goals_for ?? 0}–${t.goals_against ?? 0}`} />
        <Stat label="Attack" value={num(t.attack, 2)} hint="higher scores more" />
        <Stat label="Defence" value={num(t.defence, 2)} hint="lower concedes less" />
        <Stat label="Squad value" value={eur(t.squad_value)} hint={`avg rating ${num(t.avg_player_rating, 2)}`} />
      </div>
      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Points vs expected points" subtitle="Cumulative, from the Dixon–Coles match probabilities">
          {data.series.length === 0 ? <Empty>No matches yet.</Empty> : <PointsVsExpected series={data.series} />}
        </Card>
        <div className="space-y-5">
          <Card title="Manager">
            {data.managers.length === 0 ? <Empty>No manager data.</Empty> : data.managers.map((m) => (
              <Link key={m.coach_id} to={`/managers/${m.coach_id}`} className="flex items-center gap-3 py-1 hover:text-accent">
                <Avatar src={m.photo} name={m.name} size={36} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{m.name}</span>
                  <span className="text-[12px] text-ink-3">{m.matches} matches · {signed(m.ppg - m.xppg, 2)} pts/game vs expected</span>
                </span>
                <span className="num text-xl font-semibold">{Math.round(m.score)}</span>
              </Link>
            ))}
          </Card>
          <Card title="Next matches">
            {(upcoming.data ?? []).length === 0 ? <Empty>None scheduled.</Empty> : (
              <ul className="space-y-3">
                {(upcoming.data ?? []).map((f) => (
                  <li key={f.id}>
                    <div className="mb-1 flex justify-between text-[12px]">
                      <span className="font-medium">{f.home.name} – {f.away.name}</span>
                      <span className="text-ink-3">{dateTime(f.date)}</span>
                    </div>
                    <ProbBar fixture={f} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
      <Card title="Squad" subtitle="This season, by minutes">
        {data.squad.length === 0 ? <Empty>No players.</Empty> : <PlayerTable rows={data.squad} />}
      </Card>
    </div>
  );
}
