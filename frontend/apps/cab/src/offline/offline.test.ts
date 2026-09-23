import type { ReportDraft } from "@shiftmate/contracts";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { withCache } from "../queries";
import { recall, remember, store } from "./db";
import { clearDraft, flushPending, loadDraft, pendingReports, saveDraft, sendReport } from "./reports";

const DRAFT: ReportDraft = {
  type: "equipment_problem",
  severity: "low",
  summary_en: "Left mirror cracked",
  summary_local: "Left mirror cracked",
  people_involved: false,
  injury: false,
  parser: "tap",
};

async function clearAll() {
  for (const r of await store.pending.all()) await store.pending.delete(r.id);
  for (const r of await store.cache.all()) await store.cache.delete(r.key);
  await clearDraft();
}

beforeEach(clearAll);
afterEach(() => vi.unstubAllGlobals());

const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });

describe("the tablet's own copy (jsdom has no IndexedDB: the memory store is used)", () => {
  it("keeps the last good answer and serves it when the gateway cannot be reached", async () => {
    expect(await withCache("k", async () => ({ n: 1 }))).toEqual({ n: 1 });
    await new Promise((r) => setTimeout(r, 0));
    expect(await withCache("k", () => Promise.reject(new TypeError("Failed to fetch")))).toEqual({ n: 1 });
  });

  it("a real answer from the gateway (an error) is never replaced by an old copy", async () => {
    await remember("k2", { old: true });
    const { EdgeError } = await import("../api");
    await expect(withCache("k2", () => Promise.reject(new EdgeError(403, "private")))).rejects.toThrow("private");
  });

  it("with nothing kept, the network error surfaces", async () => {
    await expect(withCache("none", () => Promise.reject(new TypeError("offline")))).rejects.toThrow("offline");
    expect(await recall("none")).toBeNull();
  });
});

describe("reports that cannot reach the gateway", () => {
  it("wait on the tablet, then go in order once it answers", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const first = await sendReport("OP1001", DRAFT, null, null);
    const second = await sendReport("OP1001", { ...DRAFT, summary_local: "Horn weak" }, null, "horn weak");
    expect(first.queued && second.queued).toBe(true);
    expect((await pendingReports("OP1001")).map((p) => p.draft.summary_local)).toEqual(["Left mirror cracked", "Horn weak"]);
    expect(await pendingReports("OP1002")).toEqual([]);

    // still unreachable: nothing is lost
    expect(await flushPending()).toBe(0);
    expect(await pendingReports()).toHaveLength(2);

    const bodies: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        bodies.push(JSON.parse(String(init?.body)));
        return ok({ report_id: "r1", ts: "2026-09-24T12:00:00+05:30", draft: DRAFT, context: {}, synced: false });
      }),
    );
    expect(await flushPending()).toBe(2);
    expect(await pendingReports()).toEqual([]);
    // the gateway fills in time and place on arrival
    expect(bodies[0]).toMatchObject({ context: null, draft: { summary_local: "Left mirror cracked" } });
    expect(bodies[1]).toMatchObject({ transcript: "horn weak" });
  });

  it("a report the gateway accepts is not queued", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok({ report_id: "r9", ts: "", draft: DRAFT, context: {}, synced: false })));
    expect(await sendReport("OP1001", DRAFT, null, null)).toEqual({ queued: false, reportId: "r9" });
    expect(await pendingReports()).toEqual([]);
  });

  it("the draft survives until it is sent or deleted", async () => {
    await saveDraft({ draft: DRAFT, text: "Left mirror cracked", context: null });
    expect((await loadDraft())?.text).toBe("Left mirror cracked");
    await clearDraft();
    expect(await loadDraft()).toBeNull();
  });
});
