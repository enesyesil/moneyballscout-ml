export const POSITION_LABEL: Record<string, string> = {
  GK: "Goalkeeper",
  DEF: "Defender",
  MID: "Midfielder",
  FWD: "Forward",
};

export function eur(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (v >= 1e9) return `€${(v / 1e9).toFixed(2)}bn`;
  if (v >= 1e6) return `€${(v / 1e6).toFixed(v >= 1e8 ? 0 : 1)}m`;
  if (v >= 1e3) return `€${Math.round(v / 1e3)}k`;
  return `€${Math.round(v)}`;
}

export function num(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function signed(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}`;
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Match-rating colour band, the way football apps shade ratings. Text tokens only for the number. */
export function ratingTone(r: number | null | undefined): string {
  if (r === null || r === undefined) return "bg-surface-2 text-ink-3";
  if (r >= 8) return "bg-[var(--series-1)] text-white";
  if (r >= 7) return "bg-[color-mix(in_oklab,var(--series-1)_65%,var(--surface))] text-white";
  if (r >= 6.5) return "bg-[color-mix(in_oklab,var(--series-1)_22%,var(--surface))] text-ink";
  if (r >= 6) return "bg-surface-2 text-ink";
  return "bg-[color-mix(in_oklab,var(--neg)_22%,var(--surface))] text-ink";
}

export const METRIC_LABEL: Record<string, string> = {
  npg: "Non-penalty goals",
  goals: "Goals",
  assists: "Assists",
  shots_total: "Shots",
  shots_on: "Shots on target",
  key_passes: "Key passes",
  dribbles_success: "Successful dribbles",
  duels_won: "Duels won",
  fouls_drawn: "Fouls drawn",
  passes_accurate: "Accurate passes",
  tackles: "Tackles",
  interceptions: "Interceptions",
  blocks: "Blocks",
  dribbled_past: "Dribbled past",
  saves: "Saves",
  conceded: "Goals conceded",
  pen_saved: "Penalties saved",
  pass_pct: "Pass accuracy",
  duel_pct: "Duel success",
  dribble_pct: "Dribble success",
  save_pct: "Save %",
};

export const RADAR_METRICS: Record<string, string[]> = {
  FWD: ["npg", "shots_on", "assists", "key_passes", "dribbles_success", "duels_won", "fouls_drawn", "pass_pct"],
  MID: ["passes_accurate", "pass_pct", "key_passes", "assists", "npg", "tackles", "interceptions", "dribbles_success"],
  DEF: ["tackles", "interceptions", "blocks", "duels_won", "duel_pct", "passes_accurate", "pass_pct", "key_passes"],
  GK: ["saves", "save_pct", "conceded", "pass_pct", "pen_saved"],
};

export const FEATURE_LABEL: Record<string, string> = {
  perf_index: "Performance Index",
  form: "Form",
  avg_rating: "Average rating",
  age: "Age",
  age_sq: "Age (curve)",
  minutes_share: "Share of minutes",
  apps: "Appearances",
  contract_years_left: "Contract length",
  team_rating: "Team strength",
  league_coef: "League",
  pos_GK: "Role: GK",
  pos_DEF: "Role: DEF",
  pos_MID: "Role: MID",
  pos_FWD: "Role: FWD",
};

export const COMPONENT_LABEL: Record<string, string> = {
  shooting: "Shooting",
  creativity: "Creativity",
  passing: "Passing",
  defending: "Defending",
  discipline: "Discipline",
  goalkeeping: "Goalkeeping",
  goals: "Goals",
  assists: "Assists",
  defensive_outcome: "Clean sheet / conceded",
};
