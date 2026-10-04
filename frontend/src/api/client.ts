import { useQuery } from "@tanstack/react-query";
import type { components } from "./schema";

type S = components["schemas"];
export type PlayerRow = S["PlayerRow"];
export type SimilarRow = S["SimilarRow"];
export type PlayerDetail = S["PlayerDetail"];
export type RatingPoint = S["RatingPoint"];
export type ScatterPoint = S["ScatterPoint"];
export type FixtureRow = S["FixtureRow"];
export type FixtureDetail = S["FixtureDetail"];
export type LineupPlayer = S["LineupPlayer"];
export type TeamRow = S["TeamRow"];
export type TeamDetail = S["TeamDetail"];
export type ManagerRow = S["ManagerRow"];
export type ManagerDetail = S["ManagerDetail"];
export type ModelRun = S["ModelRunOut"];
export type Dashboard = S["Dashboard"];
export type Meta = S["Meta"];
export type Position = "GK" | "DEF" | "MID" | "FWD";

export interface SyncStatus {
  leagues: number[];
  season: number;
  daily_quota: number;
  used_today: number;
  remaining_today: number;
  usage_last_7_days: { day: string; requests: number }[];
  fixtures_total: number;
  fixtures_finished: number;
  fixtures_with_player_stats: number;
  backfill_pending: number;
}

type Params = Record<string, string | number | boolean | null | undefined>;

export async function api<T>(path: string, params?: Params): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const url = `/api${path}${qs.size ? `?${qs}` : ""}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${url}`);
  return res.json() as Promise<T>;
}

function useApi<T>(path: string | null, params?: Params) {
  return useQuery({
    queryKey: [path, params],
    queryFn: () => api<T>(path as string, params),
    enabled: path !== null,
  });
}

export const useMeta = () => useApi<Meta>("/meta");
export const useDashboard = () => useApi<Dashboard>("/dashboard");
export const usePlayers = (p: Params) => useApi<PlayerRow[]>("/players", p);
export const usePlayer = (id: number) => useApi<PlayerDetail>(`/players/${id}`);
export const usePlayerRatings = (id: number) => useApi<RatingPoint[]>(`/players/${id}/ratings`);
export const useSimilar = (id: number, p: Params) => useApi<SimilarRow[]>(`/players/${id}/similar`, p);
export const useScatter = (p: Params) => useApi<ScatterPoint[]>("/moneyball/scatter", p);
export const useUndervalued = (p: Params) => useApi<PlayerRow[]>("/moneyball/undervalued", p);
export const useFixtures = (p: Params) => useApi<FixtureRow[]>("/fixtures", p);
export const useFixture = (id: number) => useApi<FixtureDetail>(`/fixtures/${id}`);
export const useTeams = () => useApi<TeamRow[]>("/teams");
export const useTeam = (id: number) => useApi<TeamDetail>(`/teams/${id}`);
export const useManagers = () => useApi<ManagerRow[]>("/managers");
export const useManager = (id: number) => useApi<ManagerDetail>(`/managers/${id}`);
export const useModelRuns = () => useApi<ModelRun[]>("/models/runs");
export const useSyncStatus = () => useApi<SyncStatus>("/admin/sync-status");
