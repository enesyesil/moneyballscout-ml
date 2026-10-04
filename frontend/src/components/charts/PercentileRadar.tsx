import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Tooltip } from "recharts";
import { METRIC_LABEL } from "../../lib/format";
import { C, TooltipBox } from "./common";

/** Single-series percentile profile vs same-position players (shrunk per-90s). */
export default function PercentileRadar({ percentiles, metrics, per90 }: {
  percentiles: Record<string, number | null>; metrics: string[]; per90: Record<string, number | null>;
}) {
  const data = metrics
    .filter((m) => percentiles[m] !== undefined)
    .map((m) => ({ metric: METRIC_LABEL[m] ?? m, key: m, pct: percentiles[m] ?? 0, value: per90[m] }));
  return (
    <div className="h-72">
      <ResponsiveContainer>
        <RadarChart data={data} outerRadius="72%" margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
          <PolarGrid stroke={C.grid} />
          <PolarAngleAxis dataKey="metric" tick={{ fill: "var(--text-2)", fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} tickCount={5} />
          <Tooltip content={({ active, payload }) => {
            const p = active && payload?.[0]?.payload as (typeof data)[number] | undefined;
            if (!p) return null;
            const isRate = p.key.endsWith("_pct");
            return <TooltipBox title={p.metric} rows={[
              { label: "Percentile", value: `${Math.round(p.pct)}` , color: C.s1 },
              { label: isRate ? "Rate (shrunk)" : "Per 90 (shrunk)", value: p.value == null ? "—" : isRate ? `${(p.value * 100).toFixed(1)}%` : p.value.toFixed(2) },
            ]} />;
          }} />
          <Radar dataKey="pct" stroke={C.s1} strokeWidth={2} fill={C.s1} fillOpacity={0.18} isAnimationActive={false}
            dot={{ r: 3, fill: C.s1, stroke: "var(--surface)", strokeWidth: 1.5 }} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
