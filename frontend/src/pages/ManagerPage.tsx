import { Link, useParams } from "react-router";
import { useManager } from "../api/client";
import PointsVsExpected from "../components/charts/PointsVsExpected";
import { Avatar, Card, ErrorBox, Loading, Stat, TeamLogo } from "../components/ui";
import { num, signed } from "../lib/format";

export default function ManagerPage() {
  const id = Number(useParams().id);
  const { data, isLoading, error } = useManager(id);
  if (isLoading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  const m = data.manager;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-4">
        <Avatar src={m.photo} name={m.name} size={64} />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-tight">{m.name}</h1>
          <Link to={`/teams/${m.team.id}`} className="mt-1 flex items-center gap-2 text-sm text-ink-2 hover:text-accent">
            <TeamLogo src={m.team.logo} />{m.team.name}{m.tenure_start && <> · since {new Date(m.tenure_start).getFullYear()}</>}
            {data.nationality && <> · {data.nationality}</>}
          </Link>
        </div>
        <div className="text-right">
          <div className="text-[12px] uppercase tracking-wide text-ink-3">Manager score</div>
          <div className="num text-4xl font-semibold">{Math.round(m.score)}</div>
        </div>
      </div>
      <div className="card grid grid-cols-2 gap-4 p-4 sm:grid-cols-5 sm:p-5">
        <Stat label="Matches (this season)" value={m.matches} />
        <Stat label="Points per game" value={num(m.ppg, 2)} hint={`expected ${num(m.xppg, 2)}`} />
        <Stat label="Over expectation" value={signed(m.pts_over_exp, 2)} hint="pts/match, shrunk" />
        <Stat label="Squad efficiency" value={signed(m.squad_efficiency, 2)} hint="PPG vs squad value" />
        <Stat label="Player development" value={signed(m.development, 2)} hint="rating change" />
      </div>
      <Card title="Points vs expected" subtitle="Cumulative over the tenure this season">
        <PointsVsExpected series={data.series} />
      </Card>
    </div>
  );
}
