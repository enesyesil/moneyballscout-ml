import { useState } from "react";
import { useScatter, useUndervalued } from "../api/client";
import MoneyballScatter from "../components/charts/MoneyballScatter";
import PlayerTable from "../components/PlayerTable";
import { Card, Empty, ErrorBox, Loading, Segmented, Select } from "../components/ui";

const POS = [
  { value: "", label: "All" },
  { value: "GK", label: "GK" },
  { value: "DEF", label: "DEF" },
  { value: "MID", label: "MID" },
  { value: "FWD", label: "FWD" },
];
const AGES = [
  { value: "", label: "Any age" },
  { value: "23", label: "U23" },
  { value: "27", label: "U27" },
  { value: "30", label: "U30" },
];
const BUDGETS = [
  { value: "", label: "Any budget" },
  { value: "5000000", label: "≤ €5m" },
  { value: "15000000", label: "≤ €15m" },
  { value: "30000000", label: "≤ €30m" },
  { value: "60000000", label: "≤ €60m" },
];

export default function Moneyball() {
  const [position, setPosition] = useState("");
  const [age, setAge] = useState("");
  const [budget, setBudget] = useState("");
  const scatter = useScatter({ position });
  const under = useUndervalued({ position, age_max: age, value_max: budget, limit: 30 });

  const points = (scatter.data ?? []).filter(
    (p) => (!age || (p.age ?? 99) <= Number(age)) && (!budget || p.market_value <= Number(budget)),
  );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Moneyball explorer</h1>
        <p className="max-w-3xl text-sm text-ink-3">
          Each dot is a player. Further right means better performance for the position; higher means more expensive.
          The valuation model (LightGBM quantiles, out-of-fold) estimates what each player <em>should</em> cost from how they play,
          their age, role, contract and team. Highlighted players cost much less than that estimate.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Segmented label="Position" value={position} onChange={setPosition} options={POS} />
        <Select label="Age" value={age} onChange={setAge} options={AGES} />
        <Select label="Budget" value={budget} onChange={setBudget} options={BUDGETS} />
      </div>

      <Card title="Performance vs market value" subtitle="Click a dot to open the player. Log scale on value.">
        {scatter.isLoading ? <Loading /> : scatter.error ? <ErrorBox error={scatter.error} /> :
          points.length === 0 ? <Empty>No players match these filters.</Empty> : <MoneyballScatter points={points} />}
      </Card>

      <Card title="Undervalued shortlist" subtitle="450+ minutes, sorted by gap between model value and market value">
        {under.isLoading ? <Loading /> : under.error ? <ErrorBox error={under.error} /> :
          (under.data ?? []).length === 0 ? <Empty>No undervalued players for these filters.</Empty> :
            <PlayerTable rows={under.data ?? []} rank />}
      </Card>
    </div>
  );
}
