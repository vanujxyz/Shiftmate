/**
 * The Edge Gateway REST API, as the cab uses it (TRD §9.1). Types come from @shiftmate/contracts;
 * nothing here is hand-written API shape. The edge runs on the machine, so it is always reachable
 * even when the site has no internet (TRD §1.1 "offline definition").
 */
import type {
  AskResponse,
  CabConfig,
  ChecklistResult,
  ChecklistSubmit,
  DemoState,
  HealthResponse,
  InsightsResponse,
  IntentResponse,
  Language,
  Lesson,
  LessonSummary,
  MachineInfo,
  Recommendation,
  ReportParseResponse,
  ReportSaveRequest,
  SavedReport,
  SessionResponse,
  ShiftResponse,
  TrainingProgress,
  TrainingSlot,
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
  parseReport: (transcript: string, language: Language) =>
    post<ReportParseResponse>("/reports/parse", { transcript, language }),
  saveReport: (body: ReportSaveRequest) => post<SavedReport>("/reports", body),
  reports: (operatorId: string) =>
    call<SavedReport[]>(`/reports?operator_id=${encodeURIComponent(operatorId)}`),
  intent: (utterance: string, language: Language) =>
    post<IntentResponse>("/assistant/intent", { utterance, language }),
  ask: (question: string, language: Language) =>
    post<AskResponse>("/assistant/ask", { question, language }),
  insights: (operatorId: string, range: "shift" | "week") =>
    call<InsightsResponse>(`/insights/${encodeURIComponent(operatorId)}?range=${range}`),
  lessons: (operatorId: string) => call<LessonSummary[]>(`/lessons?operator_id=${encodeURIComponent(operatorId)}`),
  recommended: (operatorId: string) =>
    call<Recommendation[]>(`/lessons/recommended?operator_id=${encodeURIComponent(operatorId)}`),
  lesson: (lessonId: string) => call<Lesson>(`/lessons/${encodeURIComponent(lessonId)}`),
  completeLesson: (lessonId: string, body: { operator_id: string; score: number; duration_s: number; language: Language }) =>
    post<{ ok: boolean }>(`/lessons/${encodeURIComponent(lessonId)}/complete`, body),
  drillResult: (body: { operator_id: string; drill_id: string; hazards: { hazard_id: string; reaction_ms: number | null; correct: boolean }[] }) =>
    post<{ ok: boolean; correct: number; total: number; mean_reaction_ms: number | null }>("/drills/results", body),
  slots: () => call<TrainingSlot[]>("/training/slots"),
  book: (operatorId: string, slotId: string) =>
    post<{ ok: boolean; booking_id: string }>("/training/bookings", { operator_id: operatorId, slot_id: slotId }),
  progress: (operatorId: string) =>
    call<TrainingProgress>(`/training/progress?operator_id=${encodeURIComponent(operatorId)}`),
};

/** ws://…/ws/cab/{machine} on the same host as the REST API. */
export function cabSocketUrl(machineId: string): string {
  return `${EDGE_URL.replace(/^http/, "ws")}/ws/cab/${encodeURIComponent(machineId)}`;
}
