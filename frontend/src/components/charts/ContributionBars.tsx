import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { C, TooltipBox } from "./common";

/** Diverging horizontal bars: what pushed a value up (blue) or down (red). Used for SHAP and rating breakdowns. */
export default function ContributionBars({ items, format, valueLabel }: {
  items: { label: string; value: number }[]; format: (v: number) => string; valueLabel: string;
}) {
  const data = [...items].sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  const max = Math.max(...data.map((d) => Math.abs(d.value)), 1e-6);
  return (
    <div style={{ height: Math.max(120, data.length * 28 + 16) }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 0 }} barCategoryGap={6}>
          <XAxis type="number" domain={[-max * 1.05, max * 1.05]} hide />
          <YAxis type="category" dataKey="label" width={150} tickLine={false} axisLine={false}
            tick={{ fill: "var(--text-2)", fontSize: 12 }} />
          <ReferenceLine x={0} stroke="var(--text-3)" />
          <Tooltip cursor={{ fill: "var(--surface-2)" }} content={({ active, payload }) => {
            const p = active && payload?.[0]?.payload as (typeof data)[number] | undefined;
            if (!p) return null;
            return <TooltipBox title={p.label} rows={[{ label: valueLabel, value: format(p.value), color: p.value >= 0 ? C.pos : C.neg }]} />;
          }} />
          <Bar dataKey="value" radius={4} isAnimationActive={false} maxBarSize={18}>
            {data.map((d) => <Cell key={d.label} fill={d.value >= 0 ? C.pos : C.neg} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
