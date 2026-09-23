import type { HealthResponse } from "@shiftmate/contracts";

const BASE_URL: string = import.meta.env.VITE_FLEET_URL ?? "http://localhost:8200";

/** GET /health on the fleet service. Throws if it is not reachable. */
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${BASE_URL}/health`);
  if (!response.ok) throw new Error(`health ${response.status}`);
  return (await response.json()) as HealthResponse;
}
