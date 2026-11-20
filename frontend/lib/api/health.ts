const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type HealthResponse = { status: string; service: string };

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_URL}/api/v1/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}
