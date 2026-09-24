/**
 * The two services the console reads (TRD §9): the Edge Gateway (the live site and the demo
 * player) and the Fleet Service (site days, fleet, scale). Types come from @shiftmate/contracts.
 */
import type {
  DemoState,
  FleetOverview,
  FleetPattern,
  IdleCausesResponse,
  MachineInfo,
  SafetyResponse,
  ScaleStats,
  ScenarioInfo,
  SiteInfo,
  SiteLayout,
  SiteSummary,
  TrendsResponse,
} from "@shiftmate/contracts";

export const EDGE_URL: string = import.meta.env.VITE_EDGE_URL ?? "http://localhost:8100";
export const FLEET_URL: string = import.meta.env.VITE_FLEET_URL ?? "http://localhost:8200";

export class ServiceError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      message = ((await response.json()) as { error?: { message?: string } }).error?.message ?? message;
    } catch {
      /* not JSON */
    }
    throw new ServiceError(response.status, message);
  }
  return (await response.json()) as T;
}

const edgePost = <T>(path: string, body: unknown = {}) =>
  call<T>(EDGE_URL, path, { method: "POST", body: JSON.stringify(body) });
const q = (date?: string | null) => (date ? `?date=${encodeURIComponent(date)}` : "");

export const edge = {
  layout: () => call<SiteLayout>(EDGE_URL, "/site/layout"),
  machines: () => call<MachineInfo[]>(EDGE_URL, "/machines"),
  demoState: () => call<DemoState>(EDGE_URL, "/demo/state"),
  scenarios: () => call<ScenarioInfo[]>(EDGE_URL, "/demo/scenarios"),
  load: (name: string) => edgePost<DemoState>("/demo/scenario/load", { name }),
  play: () => edgePost<DemoState>("/demo/play"),
  pause: () => edgePost<DemoState>("/demo/pause"),
  speed: (x: number) => edgePost<DemoState>("/demo/speed", { x }),
  seek: (beatId: string) => edgePost<DemoState>("/demo/seek", { beat_id: beatId }),
  network: (online: boolean) => edgePost<DemoState>("/demo/network", { online }),
  captions: (on: boolean) => edgePost<DemoState>("/demo/captions", { on }),
  reset: () => edgePost<DemoState>("/demo/reset"),
};

export const fleet = {
  sites: () => call<SiteInfo[]>(FLEET_URL, "/sites"),
  summary: (site: string, date?: string | null) =>
    call<SiteSummary>(FLEET_URL, `/sites/${encodeURIComponent(site)}/summary${q(date)}`),
  idle: (site: string, date?: string | null) =>
    call<IdleCausesResponse>(FLEET_URL, `/sites/${encodeURIComponent(site)}/idle-causes${q(date)}`),
  safety: (site: string, date?: string | null) =>
    call<SafetyResponse>(FLEET_URL, `/sites/${encodeURIComponent(site)}/safety${q(date)}`),
  trends: (site: string) => call<TrendsResponse>(FLEET_URL, `/sites/${encodeURIComponent(site)}/trends`),
  overview: () => call<FleetOverview>(FLEET_URL, "/fleet/overview"),
  patterns: () => call<FleetPattern[]>(FLEET_URL, "/fleet/patterns"),
  scale: () => call<ScaleStats>(FLEET_URL, "/scale/stats"),
};

/** ws://…/ws/site/{site} on the edge. */
export function siteSocketUrl(siteId: string): string {
  return `${EDGE_URL.replace(/^http/, "ws")}/ws/site/${encodeURIComponent(siteId)}`;
}
