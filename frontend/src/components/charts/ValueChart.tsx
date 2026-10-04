import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PlayerDetail } from "../../api/client";
import { eur, shortDate } from "../../lib/format";
import { axisProps, C, LegendRow, TooltipBox } from "./common";

/** Market value history against the model's current P10-P90 range and P50. */
export default function ValueChart({ history, valuation }: { history: PlayerDetail["value_history"]; valuation: PlayerDetail["valuation"] }) {
  const data = history.map((h) => ({ t: new Date(h.date).getTime(), value: h.value, date: h.date }));
  const values = [...data.map((d) => d.value), ...(valuation ? [valuation.p10, valuation.p90] : [])];
  const max = Math.max(...values, 1) * 1.08;

  return (
    <div>
      <LegendRow items={[
        { label: "Market value", color: C.s1, kind: "line" },
        ...(valuation ? [
          { label: "Model value (P50)", color: C.s2, kind: "dash" as const },
          { label: "Model range P10–P90", color: C.band, kind: "band" as const },
        ] : []),
      ]} />
      <div className="h-56">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
            <CartesianGrid vertical={false} stroke={C.grid} />
            <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} {...axisProps}
              tickFormatter={(t) => new Date(t).toLocaleDateString(undefined, { month: "short", year: "2-digit" })} minTickGap={40} />
            <YAxis domain={[0, max]} {...axisProps} tickFormatter={(v) => eur(v)} width={56} />
            {valuation && <ReferenceArea y1={valuation.p10} y2={valuation.p90} fill={C.band} fillOpacity={1} stroke="none" />}
            {valuation && <ReferenceLine y={valuation.p50} stroke={C.s2} strokeDasharray="5 4" strokeWidth={2} />}
            <Tooltip cursor={{ stroke: C.axis, strokeDasharray: "3 3" }}
              content={({ active, payload }) => {
                const p = active && payload?.[0]?.payload as (typeof data)[number] | undefined;
                if (!p) return null;
                return <TooltipBox title={shortDate(p.date)} rows={[
                  { label: "Market value", value: eur(p.value), color: C.s1 },
                  ...(valuation ? [{ label: "Model P50 (now)", value: eur(valuation.p50), color: C.s2 }] : []),
                ]} />;
              }} />
            <Line dataKey="value" stroke={C.s1} strokeWidth={2} isAnimationActive={false}
              dot={{ r: 3, fill: C.s1, stroke: "var(--surface)", strokeWidth: 2 }} activeDot={{ r: 5 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
