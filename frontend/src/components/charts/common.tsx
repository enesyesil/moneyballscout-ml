import type { ReactNode } from "react";

export const C = {
  s1: "var(--series-1)",
  s2: "var(--series-2)",
  s3: "var(--series-3)",
  muted: "var(--muted-mark)",
  band: "var(--band)",
  grid: "var(--grid)",
  axis: "var(--text-3)",
  surface: "var(--surface)",
  pos: "var(--pos)",
  neg: "var(--neg)",
};

export const axisProps = {
  stroke: C.grid,
  tick: { fill: C.axis, fontSize: 11 },
  tickLine: false,
  axisLine: false,
} as const;

export function TooltipBox({ title, rows }: { title: ReactNode; rows: { label: string; value: ReactNode; color?: string }[] }) {
  return (
    <div className="card min-w-40 px-3 py-2 text-[12px] shadow-lg">
      <div className="mb-1 font-semibold text-ink">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-4 text-ink-2">
          <span className="flex items-center gap-1.5">
            {r.color && <span className="inline-block h-2 w-2 rounded-full" style={{ background: r.color }} />}
            {r.label}
          </span>
          <span className="num font-medium text-ink">{r.value}</span>
        </div>
      ))}
    </div>
  );
}

export function LegendRow({ items }: { items: { label: string; color: string; kind?: "dot" | "line" | "band" | "dash" }[] }) {
  return (
    <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-2">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          {i.kind === "line" ? <span className="inline-block h-0.5 w-4 rounded" style={{ background: i.color }} />
            : i.kind === "dash" ? <span className="inline-block w-4 border-t-2 border-dashed" style={{ borderColor: i.color }} />
            : i.kind === "band" ? <span className="inline-block h-2.5 w-4 rounded-sm" style={{ background: i.color }} />
            : <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: i.color }} />}
          {i.label}
        </span>
      ))}
    </div>
  );
}
