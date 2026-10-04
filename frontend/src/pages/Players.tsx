import { useState } from "react";
import { useMeta, usePlayers } from "../api/client";
import PlayerTable from "../components/PlayerTable";
import { Card, Empty, ErrorBox, Loading, Segmented, Select } from "../components/ui";

const SORTS = [
  { value: "perf_index", label: "Performance Index" },
  { value: "form", label: "Form" },
  { value: "avg_rating", label: "Average rating" },
  { value: "market_value", label: "Market value" },
  { value: "undervalue", label: "Undervaluation" },
  { value: "goals", label: "Goals" },
  { value: "minutes", label: "Minutes" },
];

export default function Players() {
  const meta = useMeta();
  const [position, setPosition] = useState("");
  const [team, setTeam] = useState("");
  const [sort, setSort] = useState("perf_index");
  const [minMinutes, setMinMinutes] = useState("450");
  const [q, setQ] = useState("");
  const players = usePlayers({ position, team_id: team, sort, min_minutes: minMinutes, q, limit: 100 });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Players</h1>
        <p className="text-sm text-ink-3">Season leaderboards. Per-90 stats are shrunk toward the position average, so small samples don't top the table.</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search player…" aria-label="Search player"
          className="w-full rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] sm:w-56" />
        <Segmented label="Position" value={position} onChange={setPosition}
          options={[{ value: "", label: "All" }, ...["GK", "DEF", "MID", "FWD"].map((p) => ({ value: p, label: p }))]} />
        <Select label="Team" value={team} onChange={setTeam}
          options={[{ value: "", label: "All teams" }, ...(meta.data?.teams ?? []).map((t) => ({ value: String(t.id), label: t.name }))]} />
        <Select label="Sort" value={sort} onChange={setSort} options={SORTS} />
        <Select label="Min minutes" value={minMinutes} onChange={setMinMinutes}
          options={["0", "270", "450", "900", "1500"].map((v) => ({ value: v, label: v }))} />
      </div>
      <Card>
        {players.isLoading ? <Loading /> : players.error ? <ErrorBox error={players.error} /> :
          (players.data ?? []).length === 0 ? <Empty>No players found.</Empty> : <PlayerTable rows={players.data ?? []} rank />}
      </Card>
    </div>
  );
}
