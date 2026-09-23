/**
 * The Edge Gateway REST API, as the cab uses it (TRD §9.1). Types come from @shiftmate/contracts;
 * nothing here is hand-written API shape. The edge runs on the machine, so it is always reachable
 * even when the site has no internet (TRD §1.1 "offline definition").
 */
import type {
  CabConfig,
  ChecklistResult,
  ChecklistSubmit,
  DemoState,
  HealthResponse,
  Language,
  MachineInfo,
  SessionResponse,
  ShiftResponse,
} from "@shiftmate/contracts";

export const EDGE_URL: string = import.meta.env.VITE_EDGE_URL ?? "http://localhost:8100";

/** An edge error with the status and the message the edge wrote (`{error: {code, message}}`). */
export class EdgeError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${EDGE_URL}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { error?: { message?: string } };
      message = body.error?.message ?? message;
    } catch {
      /* not JSON */
    }
    throw new EdgeError(response.status, message);
  }
  return (await response.json()) as T;
}

const post = <T>(path: string, body: unknown) =>
  call<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => call<HealthResponse>("/health"),
  config: () => call<CabConfig>("/cab/config"),
  machines: () => call<MachineInfo[]>("/machines"),
  demoState: () => call<DemoState>("/demo/state"),
  signIn: (body: {
    operator_id: string;
    machine_id: string;
    language: Language;
    pin?: string;
    badge?: string;
  }) => post<SessionResponse>("/session/sign-in", body),
  signOut: () => post<{ ok: boolean }>("/session/sign-out", {}),
  shift: (operatorId: string) => call<ShiftResponse>(`/operators/${operatorId}/shift`),
  checklist: (body: ChecklistSubmit) => post<ChecklistResult>("/checklist", body),
  ack: (alertId: string, action: "ack" | "later" | "done" = "ack") =>
    post<{ ok: boolean }>(`/alerts/${encodeURIComponent(alertId)}/ack`, { action }),
};

/** ws://…/ws/cab/{machine} on the same host as the REST API. */
export function cabSocketUrl(machineId: string): string {
  return `${EDGE_URL.replace(/^http/, "ws")}/ws/cab/${encodeURIComponent(machineId)}`;
}
