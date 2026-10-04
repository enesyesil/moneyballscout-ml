import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { usePlayer, usePlayerRatings, useSimilar } from "../api/client";
import ContributionBars from "../components/charts/ContributionBars";
import PercentileRadar from "../components/charts/PercentileRadar";
import RatingTimeline from "../components/charts/RatingTimeline";
import ValueChart from "../components/charts/ValueChart";
import PlayerTable from "../components/PlayerTable";
import { Avatar, Card, Empty, ErrorBox, Loading, PosChip, RatingBadge, Select, Stat, Table, td, th } from "../components/ui";
import { COMPONENT_LABEL, eur, FEATURE_LABEL, METRIC_LABEL, num, POSITION_LABEL, RADAR_METRICS, shortDate } from "../lib/format";

export default function PlayerPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const detail = usePlayer(id);
  const ratings = usePlayerRatings(id);
  const [cheaper, setCheaper] = useState("cheaper");
  const value = detail.data?.player.market_value;
  const similar = useSimilar(id, { max_value: cheaper === "cheaper" && value ? value : undefined, limit: 8 });
  const [selected, setSelected] = useState<number | null>(null);

  if (detail.isLoading) return <Loading />;
  if (detail.error) return <ErrorBox error={detail.error} />;
  const d = detail.data!;
  const p = d.player;
  const v = d.valuation;
  const points = ratings.data ?? [];
  const match = points.find((r) => r.fixture_id === selected) ?? points[points.length - 1];
  const metrics = RADAR_METRICS[p.position_group] ?? RADAR_METRICS.MID;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-4">
        <Avatar src={p.photo} name={p.name} size={64} />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{p.name}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-2">
            <PosChip pos={p.position_group} /> {POSITION_LABEL[p.position_group]}
            {p.team && <>· <Link to={`/teams/${p.team.id}`} className="hover:text-accent">{p.team.name}</Link></>}
            {p.age != null && <>· {Math.floor(p.age)} yrs</>}
            {d.nationality && <>· {d.nationality}</>}
          </div>
        </div>
        <div className="flex items-center gap-2 text-sm text-ink-2">Average <RatingBadge value={p.avg_rating} size="lg" /></div>
      </div>

      <div className="card grid grid-cols-2 gap-4 p-4 sm:grid-cols-3 sm:p-5 lg:grid-cols-6">
        <Stat label="Performance Index" value={num(p.perf_index, 0)} hint="50 = position average" />
        <Stat label="Form" value={num(p.form, 2)} hint={d.form_sd != null ? `± ${(1.645 * d.form_sd).toFixed(2)} (90%)` : undefined} />
        <Stat label="Next match (exp.)" value={num(p.expected_next, 2)} hint="form + opponent" />
        <Stat label="Apps · minutes" value={`${p.apps} · ${p.minutes}`} hint={`${p.goals} G · ${p.assists} A`} />
        <Stat label="Market value" value={eur(p.market_value)} hint={d.contract_expiration ? `contract to ${d.contract_expiration.slice(0, 4)}` : undefined} />
        <Stat label="Model value" value={eur(v?.p50)} hint={v ? `${eur(v.p10)} – ${eur(v.p90)}` : "not enough data"} />
      </div>

      <Card title="Match ratings & form" subtitle="Click a match to see why it got its rating">
        {ratings.isLoading ? <Loading /> : points.length === 0 ? <Empty>No rated matches.</Empty> :
          <RatingTimeline points={points} onSelect={setSelected} />}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title={match ? `Why ${match.rating.toFixed(1)}? ${match.home ? "vs" : "@"} ${match.opponent.name}` : "Rating breakdown"}
          subtitle={match ? `${shortDate(match.date)} · ${match.score} · ${match.minutes}' · goal-difference value of each part` : undefined}
          action={match && <button className="text-[13px] font-medium text-accent" onClick={() => navigate(`/matches/${match.fixture_id}`)}>Match →</button>}>
          {match ? (
            <ContributionBars valueLabel="Goal-diff value" format={(x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(3)}`}
              items={Object.entries(match.components).filter(([k, x]) => k !== "opponent_factor" && Math.abs(x) > 1e-4)
                .map(([k, x]) => ({ label: COMPONENT_LABEL[k] ?? k, value: x }))} />
          ) : <Empty>No match selected.</Empty>}
        </Card>
        <Card title="Percentile profile" subtitle={`vs ${POSITION_LABEL[p.position_group].toLowerCase()}s with 450+ minutes`}>
          <PercentileRadar percentiles={d.percentiles} per90={d.shrunk_per90} metrics={metrics} />
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Market value vs model" subtitle="Transfermarkt history against the model's current range">
          {d.value_history.length === 0 ? <Empty>No market value linked for this player.</Empty> :
            <ValueChart history={d.value_history} valuation={v} />}
        </Card>
        <Card title="What drives the model value" subtitle="SHAP contributions to the P50 estimate (log scale: +0.10 ≈ +10%)">
          {v ? (
            <ContributionBars valueLabel="Effect on value" format={(x) => `${x >= 0 ? "+" : "−"}${Math.round(Math.abs(Math.expm1(x)) * 100)}%`}
              items={Object.entries(v.contributions).filter(([k, x]) => k !== "base" && Math.abs(x) > 0.005)
                .map(([k, x]) => ({ label: FEATURE_LABEL[k] ?? k, value: x })).sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, 8)} />
          ) : <Empty>Needs 270+ minutes and a linked market value.</Empty>}
        </Card>
      </div>

      <Card title="Similar players" subtitle="Nearest neighbours on the position percentile profile"
        action={<Select label="" value={cheaper} onChange={setCheaper}
          options={[{ value: "cheaper", label: "Cheaper only" }, { value: "all", label: "Any price" }]} />}>
        {similar.isLoading ? <Loading /> : (similar.data ?? []).length === 0 ? <Empty>No similar players under these filters.</Empty> :
          <PlayerTable rows={similar.data ?? []} cols={["similarity", "age", "rating", "pi", "value", "model"]} />}
      </Card>

      <Card title="Per 90" subtitle="Raw season numbers next to the shrunk estimates the model uses">
        <Table>
          <thead><tr>
            <th className={th}>Metric</th><th className={`${th} text-right`}>Raw</th><th className={`${th} text-right`}>Shrunk</th>
            <th className={`${th} text-right`}>Percentile</th>
          </tr></thead>
          <tbody>
            {Object.keys(METRIC_LABEL).filter((m) => d.per90[m] !== undefined || d.shrunk_per90[m] !== undefined).map((m) => {
              const rate = m.endsWith("_pct");
              const f = (x: number | null | undefined) => (x == null ? "—" : rate ? `${(x * 100).toFixed(1)}%` : x.toFixed(2));
              return (
                <tr key={m}>
                  <td className={td}>{METRIC_LABEL[m]}</td>
                  <td className={`${td} num text-right text-ink-2`}>{f(d.per90[m])}</td>
                  <td className={`${td} num text-right`}>{f(d.shrunk_per90[m])}</td>
                  <td className={`${td} num text-right`}>{d.percentiles[m] == null ? "—" : Math.round(d.percentiles[m] as number)}</td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}
