import type { FixtureRow } from "../../api/client";

/** Home / draw / away probabilities as one segmented bar with 2px surface gaps and labels. */
export default function ProbBar({ fixture }: { fixture: FixtureRow }) {
  const p = fixture.prediction;
  if (!p) return <div className="text-[12px] text-ink-3">No prediction yet</div>;
  const segs = [
    { k: "home", v: p.home_win, color: "var(--series-1)", label: fixture.home.name },
    { k: "draw", v: p.draw, color: "var(--muted-mark)", label: "Draw" },
    { k: "away", v: p.away_win, color: "var(--series-2)", label: fixture.away.name },
  ];
  return (
    <div>
      <div className="flex h-2 gap-[2px] overflow-hidden rounded-full" role="img"
        aria-label={segs.map((s) => `${s.label} ${Math.round(s.v * 100)}%`).join(", ")}>
        {segs.map((s) => <div key={s.k} style={{ width: `${s.v * 100}%`, background: s.color }} title={`${s.label} ${Math.round(s.v * 100)}%`} />)}
      </div>
      <div className="num mt-1 flex justify-between text-[11px] text-ink-2">
        <span>{Math.round(p.home_win * 100)}%</span>
        <span>Draw {Math.round(p.draw * 100)}%</span>
        <span>{Math.round(p.away_win * 100)}%</span>
      </div>
    </div>
  );
}
