/**
 * What the tablet keeps for itself (TRD §11.2 Offline, F-CAB-04, F-REP-04): the last copy of each
 * screen's data (shift, config, insights, reports), the report draft being written, and reports
 * that could not reach the machine gateway yet. IndexedDB through Dexie; where IndexedDB is not
 * available (private window, blocked storage, tests) the same calls work on memory, so the app
 * never breaks, it only forgets on reload.
 *
 * The edge keeps its own outbox to the fleet; this is only the cab → edge hop.
 */
import type { ReportContextModel, ReportDraft } from "@shiftmate/contracts";
import Dexie, { type Table } from "dexie";

export type CacheRow = { key: string; value: unknown; at: number };
export type DraftRow = {
  id: string;
  draft: ReportDraft;
  text: string;
  context: ReportContextModel | null;
  at: number;
};
export type PendingReport = {
  id: string;
  operatorId: string;
  draft: ReportDraft;
  transcript: string | null;
  at: number;
};

class CabDb extends Dexie {
  cache!: Table<CacheRow, string>;
  drafts!: Table<DraftRow, string>;
  pending!: Table<PendingReport, string>;
  constructor() {
    super("shiftmate-cab");
    this.version(1).stores({ cache: "key", drafts: "id", pending: "id, at" });
  }
}

type Store<T> = {
  get: (key: string) => Promise<T | undefined>;
  put: (row: T) => Promise<void>;
  delete: (key: string) => Promise<void>;
  all: () => Promise<T[]>;
};

function memoryStore<T>(keyOf: (row: T) => string): Store<T> {
  const rows = new Map<string, T>();
  return {
    get: async (key) => rows.get(key),
    put: async (row) => void rows.set(keyOf(row), row),
    delete: async (key) => void rows.delete(key),
    all: async () => [...rows.values()],
  };
}

function dexieStore<T>(table: Table<T, string>, fallback: Store<T>): Store<T> {
  // any IndexedDB failure (quota, blocked, closed) falls back to memory for that call
  const guard = async <R>(fn: () => Promise<R>, alt: () => Promise<R>) => {
    try {
      return await fn();
    } catch {
      return alt();
    }
  };
  return {
    get: (key) => guard(() => table.get(key), () => fallback.get(key)),
    put: (row) => guard(async () => void (await table.put(row)), () => fallback.put(row)),
    delete: (key) => guard(() => table.delete(key), () => fallback.delete(key)),
    all: () => guard(() => table.toArray(), () => fallback.all()),
  };
}

function open() {
  const mem = {
    cache: memoryStore<CacheRow>((r) => r.key),
    drafts: memoryStore<DraftRow>((r) => r.id),
    pending: memoryStore<PendingReport>((r) => r.id),
  };
  if (typeof indexedDB === "undefined") return mem;
  try {
    const db = new CabDb();
    return {
      cache: dexieStore(db.cache, mem.cache),
      drafts: dexieStore(db.drafts, mem.drafts),
      pending: dexieStore(db.pending, mem.pending),
    };
  } catch {
    return mem;
  }
}

export const store = open();

/** The last good copy of an edge response, for when the gateway cannot be reached. */
export async function remember(key: string, value: unknown): Promise<void> {
  await store.cache.put({ key, value, at: Date.now() });
}

export async function recall<T>(key: string): Promise<{ value: T; at: number } | null> {
  const row = await store.cache.get(key);
  return row ? { value: row.value as T, at: row.at } : null;
}

/** Drop every kept copy whose key starts with `prefix` (e.g. an operator's private My Day). */
export async function forget(prefix: string): Promise<void> {
  for (const row of await store.cache.all()) {
    if (row.key.startsWith(prefix)) await store.cache.delete(row.key);
  }
}
