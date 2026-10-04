import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import type { RatingPoint } from "../../api/client";
import { num, shortDate } from "../../lib/format";
import { axisProps, C, LegendRow, TooltipBox } from "./common";

/** Match ratings as dots, Kalman-filtered form as a line with its 90% band. */
export default function RatingTimeline({ points, onSelect }: { points: RatingPoint[]; onSelect?: (fixtureId: number) => void }) {
  const data = points.map((p) => ({
    ...p,
    t: new Date(p.date).getTime(),
    band: p.form_lo != null && p.form_hi != null ? [p.form_lo, p.form_hi] : null,
  }));
  const ys = points.flatMap((p) => [p.rating, p.form_lo ?? p.rating, p.form_hi ?? p.rating]);
  const lo = Math.max(3, Math.floor(Math.min(...ys, 6)));
  const hi = Math.min(10, Math.ceil(Math.max(...ys, 8)));
  const ticks = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);

  return (
    <div>
      <LegendRow items={[
        { label: "Match rating", color: C.s2, kind: "dot" },
        { label: "Form", color: C.s1, kind: "line" },
        { label: "Form 90% band", color: C.band, kind: "band" },
      ]} />
      <div className="h-64">
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}
            onClick={(e) => {
              const idx = typeof e?.activeTooltipIndex === "number" ? e.activeTooltipIndex : Number(e?.activeTooltipIndex);
              if (onSelect && Number.isFinite(idx) && data[idx]) onSelect(data[idx].fixture_id);
            }}>
            <CartesianGrid vertical={false} stroke={C.grid} />
            <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} {...axisProps}
              tickFormatter={(t) => shortDate(new Date(t).toISOString())} minTickGap={40} />
            <YAxis domain={[lo, hi]} ticks={ticks} {...axisProps} />
            <Tooltip cursor={{ stroke: C.axis, strokeDasharray: "3 3" }}
              content={({ active, payload }) => {
                const p = active && payload?.[0]?.payload as (typeof data)[number] | undefined;
                if (!p) return null;
                return <TooltipBox title={`${p.home ? "vs" : "@"} ${p.opponent.name} · ${shortDate(p.date)}`} rows={[
                  { label: "Rating", value: num(p.rating, 2), color: C.s2 },
                  { label: "Form", value: num(p.form, 2), color: C.s1 },
                  { label: "API-Football", value: num(p.api_rating, 1) },
                  { label: "Score", value: p.score },
                  { label: "Minutes", value: p.minutes },
                ]} />;
              }} />
            <Area dataKey="band" stroke="none" fill={C.band} isAnimationActive={false} connectNulls />
            <Line dataKey="form" stroke={C.s1} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
            <Scatter dataKey="rating" fill={C.s2} stroke={C.surface} strokeWidth={2} isAnimationActive={false}
              shape={(props: { cx?: number; cy?: number }) => <circle cx={props.cx} cy={props.cy} r={4.5} fill={C.s2} stroke="var(--surface)" strokeWidth={2} />} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
