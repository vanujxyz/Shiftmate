/**
 * Sending reports (F-REP-03, F-REP-04). A confirmed report goes to the machine gateway, which
 * files it and forwards it to the fleet when the site has internet. If the gateway itself cannot
 * be reached, the report waits on the tablet and is sent as soon as the cab reconnects; nothing
 * the operator confirmed is ever lost. The draft being written is kept too, so a reload or a
 * switch to Working mode does not throw it away.
 */
import type { ReportContextModel, ReportDraft } from "@shiftmate/contracts";

import { api, EdgeError } from "../api";
import { type PendingReport, store } from "./db";

const DRAFT_ID = "current";

export type Sent = { queued: false; reportId: string } | { queued: true; id: string };

let counter = 0;
function localId(): string {
  counter += 1;
  return `local-${Date.now().toString(36)}-${counter}`;
}

export async function sendReport(
  operatorId: string,
  draft: ReportDraft,
  context: ReportContextModel | null,
  transcript: string | null,
): Promise<Sent> {
  try {
    const saved = await api.saveReport({ draft, context, transcript });
    return { queued: false, reportId: saved.report_id };
  } catch (e) {
    if (e instanceof EdgeError) throw e; // the gateway answered: a real error, not "unreachable"
    const row: PendingReport = { id: localId(), operatorId, draft, transcript, at: Date.now() };
    await store.pending.put(row);
    return { queued: true, id: row.id };
  }
}

export async function pendingReports(operatorId?: string): Promise<PendingReport[]> {
  const rows = await store.pending.all();
  return rows
    .filter((r) => operatorId == null || r.operatorId === operatorId)
    .sort((a, b) => a.at - b.at);
}

/**
 * Send whatever waits on the tablet, oldest first; stop at the first network failure. The edge
 * fills in time, place and weather when each one arrives (their context is null).
 */
export async function flushPending(): Promise<number> {
  let sent = 0;
  for (const row of await pendingReports()) {
    try {
      await api.saveReport({ draft: row.draft, context: null, transcript: row.transcript });
    } catch (e) {
      if (!(e instanceof EdgeError)) break; // still unreachable: try again later
      // the gateway refused it (e.g. nobody signed in): keep it rather than lose it
      continue;
    }
    await store.pending.delete(row.id);
    sent += 1;
  }
  return sent;
}

export type Draft = { draft: ReportDraft; text: string; context: ReportContextModel | null };

export async function saveDraft(d: Draft): Promise<void> {
  await store.drafts.put({ id: DRAFT_ID, ...d, at: Date.now() });
}

export async function loadDraft(): Promise<Draft | null> {
  const row = await store.drafts.get(DRAFT_ID);
  return row ? { draft: row.draft, text: row.text, context: row.context } : null;
}

export async function clearDraft(): Promise<void> {
  await store.drafts.delete(DRAFT_ID);
}
