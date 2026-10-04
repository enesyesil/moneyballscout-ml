import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { num, shortDate } from "../../lib/format";
import { axisProps, C, LegendRow, TooltipBox } from "./common";

/** Cumulative points vs Dixon-Coles expected points, match by match. */
export default function PointsVsExpected({ series }: { series: { date: string; pts: number; xpts: number }[] }) {
  let pts = 0;
  let xpts = 0;
  const data = series.map((s, i) => {
    pts += s.pts;
    xpts += s.xpts;
    return { n: i + 1, date: s.date, pts, xpts: Math.round(xpts * 100) / 100, diff: pts - xpts };
  });
  const last = data[data.length - 1];
  return (
    <div>
      <LegendRow items={[
        { label: `Points${last ? ` · ${last.pts}` : ""}`, color: C.s1, kind: "line" },
        { label: `Expected points${last ? ` · ${last.xpts.toFixed(1)}` : ""}`, color: C.s2, kind: "dash" },
      ]} />
      <div className="h-56">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid vertical={false} stroke={C.grid} />
            <XAxis dataKey="n" {...axisProps} minTickGap={24} />
            <YAxis {...axisProps} />
            <Tooltip cursor={{ stroke: C.axis, strokeDasharray: "3 3" }} content={({ active, payload }) => {
              const p = active && payload?.[0]?.payload as (typeof data)[number] | undefined;
              if (!p) return null;
              return <TooltipBox title={`Match ${p.n} · ${shortDate(p.date)}`} rows={[
                { label: "Points", value: p.pts, color: C.s1 },
                { label: "Expected", value: num(p.xpts, 1), color: C.s2 },
                { label: "Over expectation", value: `${p.diff >= 0 ? "+" : "−"}${Math.abs(p.diff).toFixed(1)}` },
              ]} />;
            }} />
            <Line dataKey="xpts" stroke={C.s2} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
            <Line dataKey="pts" stroke={C.s1} strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
