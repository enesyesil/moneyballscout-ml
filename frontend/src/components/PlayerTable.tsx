import type { PlayerRow, SimilarRow } from "../api/client";
import { eur, num } from "../lib/format";
import { PlayerCell, RatingBadge, Table, td, th } from "./ui";

type Col = "age" | "minutes" | "ga" | "rating" | "form" | "pi" | "value" | "model" | "under" | "similarity";

const DEFAULT: Col[] = ["age", "minutes", "ga", "rating", "form", "pi", "value", "model", "under"];

export default function PlayerTable({ rows, cols = DEFAULT, rank = false }: { rows: (PlayerRow | SimilarRow)[]; cols?: Col[]; rank?: boolean }) {
  const has = (c: Col) => cols.includes(c);
  const right = `${th} text-right`;
  return (
    <Table>
      <thead>
        <tr>
          {rank && <th className={`${th} w-8`}>#</th>}
          <th className={th}>Player</th>
          {has("similarity") && <th className={right}>Similarity</th>}
          {has("age") && <th className={right}>Age</th>}
          {has("minutes") && <th className={right}>Min</th>}
          {has("ga") && <th className={right}>G+A</th>}
          {has("rating") && <th className={right} title="Minutes-weighted average match rating">Avg</th>}
          {has("form") && <th className={right} title="Current form (Kalman filter)">Form</th>}
          {has("pi") && <th className={right} title="Performance Index: 50 = position average">PI</th>}
          {has("value") && <th className={right}>Value</th>}
          {has("model") && <th className={right} title="Model value (P50)">Model</th>}
          {has("under") && <th className={right} title="(model − actual) / model">Gap</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((p, i) => (
          <tr key={p.id} className="hover:bg-surface-2/60">
            {rank && <td className={`${td} num text-ink-3`}>{i + 1}</td>}
            <td className={`${td} max-w-60`}><PlayerCell p={p} /></td>
            {has("similarity") && <td className={`${td} num text-right`}>{"similarity" in p ? `${Math.round(p.similarity * 100)}%` : "—"}</td>}
            {has("age") && <td className={`${td} num text-right`}>{num(p.age, 0)}</td>}
            {has("minutes") && <td className={`${td} num text-right text-ink-2`}>{p.minutes}</td>}
            {has("ga") && <td className={`${td} num text-right`}>{p.goals + p.assists}</td>}
            {has("rating") && <td className={`${td} text-right`}><RatingBadge value={p.avg_rating} size="sm" /></td>}
            {has("form") && <td className={`${td} num text-right`}>{num(p.form, 2)}</td>}
            {has("pi") && <td className={`${td} num text-right font-medium`}>{num(p.perf_index, 0)}</td>}
            {has("value") && <td className={`${td} num text-right`}>{eur(p.market_value)}</td>}
            {has("model") && <td className={`${td} num text-right text-ink-2`}>{eur(p.p50)}</td>}
            {has("under") && (
              <td className={`${td} num text-right font-medium`}>
                {p.undervalue_score == null ? "—" : (
                  <span className={p.undervalue_score > 0 ? "text-[var(--good-text)]" : "text-ink-3"}>
                    {p.undervalue_score > 0 ? "▲ " : "▼ "}{Math.abs(Math.round(p.undervalue_score * 100))}%
                  </span>
                )}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
