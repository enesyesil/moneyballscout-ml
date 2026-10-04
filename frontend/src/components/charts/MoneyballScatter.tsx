import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { useNavigate } from "react-router";
import type { ScatterPoint } from "../../api/client";
import { eur, num } from "../../lib/format";
import { axisProps, C, LegendRow, TooltipBox } from "./common";

const UNDERVALUED = 0.25; // actual value at least 25% below the model's P50

/** Performance Index vs market value (log). Three groups max - the palette's all-pairs-safe slots. */
export default function MoneyballScatter({ points }: { points: ScatterPoint[] }) {
  const navigate = useNavigate();
  const below = points.filter((p) => p.p10 != null && p.market_value < p.p10);
  const under = points.filter((p) => !(p.p10 != null && p.market_value < p.p10) && (p.undervalue_score ?? 0) >= UNDERVALUED);
  const rest = points.filter((p) => !below.includes(p) && !under.includes(p));
  const minV = Math.min(...points.map((p) => p.market_value));
  const maxV = Math.max(...points.map((p) => p.market_value));

  const dot = (fill: string, r: number) => (props: { cx?: number; cy?: number; payload?: ScatterPoint }) => (
    <circle cx={props.cx} cy={props.cy} r={r} fill={fill} stroke="var(--surface)" strokeWidth={1.5} style={{ cursor: "pointer" }}
      onClick={() => props.payload && navigate(`/players/${props.payload.id}`)} />
  );

  return (
    <div>
      <LegendRow items={[
        { label: `Below model range (P10) · ${below.length}`, color: C.s2 },
        { label: `Undervalued ≥25% · ${under.length}`, color: C.s1 },
        { label: `Fairly priced or over · ${rest.length}`, color: C.muted },
      ]} />
      <div className="h-[420px]">
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 8, right: 8, bottom: 16, left: 4 }}>
            <CartesianGrid stroke={C.grid} />
            <XAxis type="number" dataKey="perf_index" name="Performance Index" domain={["dataMin - 3", "dataMax + 3"]} {...axisProps}
              tickFormatter={(v) => Math.round(v).toString()}
              label={{ value: "Performance Index (position-relative, 50 = average)", position: "insideBottom", offset: -10, fill: C.axis, fontSize: 11 }} />
            <YAxis type="number" dataKey="market_value" name="Market value" scale="log" domain={[minV * 0.8, maxV * 1.2]} {...axisProps}
              tickFormatter={(v) => eur(v)} width={60} allowDataOverflow />
            <ZAxis range={[60, 60]} />
            <Tooltip cursor={{ strokeDasharray: "3 3", stroke: C.axis }} content={({ active, payload }) => {
              const p = active && payload?.[0]?.payload as ScatterPoint | undefined;
              if (!p) return null;
              return <TooltipBox title={`${p.name} · ${p.team ?? ""}`} rows={[
                { label: "Performance Index", value: num(p.perf_index, 1) },
                { label: "Market value", value: eur(p.market_value) },
                { label: "Model value (P50)", value: eur(p.p50) },
                { label: "Model range", value: p.p10 ? `${eur(p.p10)} – ${eur(p.p90)}` : "—" },
                { label: "Age", value: num(p.age, 0) },
              ]} />;
            }} />
            <Scatter data={rest} shape={dot(C.muted, 4)} isAnimationActive={false} />
            <Scatter data={under} shape={dot(C.s1, 5)} isAnimationActive={false} />
            <Scatter data={below} shape={dot(C.s2, 5.5)} isAnimationActive={false} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
