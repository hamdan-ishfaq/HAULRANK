const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export async function health(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/health/`);
  if (!res.ok) throw new Error(`health ${res.status}`);
  return res.json();
}

export { API_BASE };
