const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

type Tokens = { access: string; refresh: string };

function authHeaders(): HeadersInit {
  const access = localStorage.getItem("access");
  return access
    ? { Authorization: `Bearer ${access}`, "Content-Type": "application/json" }
    : { "Content-Type": "application/json" };
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${body}`);
  }
  return res.json();
}

export async function health(): Promise<{ status: string }> {
  return req("/api/health/");
}

export async function login(username: string, password: string): Promise<Tokens> {
  const tokens = await req<Tokens>("/api/auth/token/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  localStorage.setItem("access", tokens.access);
  localStorage.setItem("refresh", tokens.refresh);
  return tokens;
}

export type Driver = {
  hos_hours_remaining: number;
  home_base_lat: number;
  home_base_lon: number;
  preferred_markets: string[];
  no_go_markets: string[];
};

export type Truck = {
  id: number;
  equipment_type: string;
  current_lat: number;
  current_lon: number;
  mpg: number;
  driver: Driver | null;
};

export type RankResult = {
  rank: number;
  load_id: number;
  overall: number;
  rate_per_mile_score: number;
  deadhead_penalty: number;
  fuel_efficiency_score: number;
  hos_feasibility: number;
  market_preference_score: number;
  deadhead_miles: number;
  rate_per_mile: number;
  weather_risk?: boolean;
  weather_reason?: string;
  overall_adjusted?: number;
};

export type RankResponse = {
  score_run_id: number;
  truck_id: number;
  diesel_usd_per_gal: number;
  results: RankResult[];
  best_single: RankResult | null;
  best_pair: {
    outbound_id: number;
    return_id: number;
    combined_score: number;
    total_deadhead_miles: number;
    total_hours: number;
    total_rate_usd: number;
  } | null;
};

export type Assignment = {
  id: number;
  load: number;
  truck: number;
  status: "offered" | "accepted" | "dispatched" | "delivered";
  status_history: { status: string; at: string; by?: string }[];
};

export const api = {
  trucks: () => req<Truck[]>("/api/trucks/"),
  rank: (truckId: number) =>
    req<RankResponse>(`/api/rank/?truck_id=${truckId}`, { method: "POST" }),
  explain: (scoreRunId: number) =>
    req<{
      score_run_id: number;
      explanations: {
        rank: number;
        load_id: number;
        overall: number;
        explanation_text: string;
      }[];
    }>(`/api/rank/${scoreRunId}/explain/`, { method: "POST" }),
  copilot: (truckId: number, message: string) =>
    req<{
      filters: Record<string, unknown>;
      results: { load_id: number; overall: number; rate_per_mile: number }[];
      best_pair: { outbound_id: number; return_id: number; combined_score: number } | null;
      narration: string;
    }>("/api/copilot/", {
      method: "POST",
      body: JSON.stringify({ truck_id: truckId, message }),
    }),
  assignments: () => req<Assignment[]>("/api/assignments/"),
  createAssignment: (load: number, truck: number) =>
    req<Assignment>("/api/assignments/", {
      method: "POST",
      body: JSON.stringify({ load, truck }),
    }),
  patchAssignment: (id: number, status: string) =>
    req<Assignment>(`/api/assignments/${id}/`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
};

export { API_BASE };
