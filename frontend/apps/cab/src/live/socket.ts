/**
 * The cab's WebSocket to the edge (/ws/cab/{machine}). Reconnects on its own with back-off
 * (1, 2, 4, 8, 10, 10 … s); the edge sends a full `snapshot` first on every connection, so a
 * reconnect never leaves stale state on screen. Staleness itself is judged from message ages in
 * the store (useStale), not here.
 */
import type { WsEnvelope } from "@shiftmate/contracts";
import { useEffect } from "react";

import { cabSocketUrl } from "../api";
import { useLive } from "./store";

export const RECONNECT_MAX_MS = 10_000;

type Timers = { set: (fn: () => void, ms: number) => number; clear: (id: number) => void };

export class CabSocket {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private timer: number | null = null;
  private stopped = false;

  constructor(
    private readonly url: string,
    private readonly onMessage: (env: WsEnvelope) => void,
    private readonly onState: (connected: boolean) => void,
    private readonly Impl: typeof WebSocket = WebSocket,
    private readonly timers: Timers = {
      set: (fn, ms) => window.setTimeout(fn, ms),
      clear: (id) => window.clearTimeout(id),
    },
  ) {}

  start(): void {
    this.stopped = false;
    this.open();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer !== null) this.timers.clear(this.timer);
    this.ws?.close();
    this.ws = null;
  }

  /** Delay before the next attempt: 1 s, doubling, at most 10 s. */
  static backoff(attempt: number): number {
    return Math.min(1000 * 2 ** attempt, RECONNECT_MAX_MS);
  }

  private open(): void {
    const ws = new this.Impl(this.url);
    this.ws = ws;
    ws.onopen = () => {
      this.attempt = 0;
      this.onState(true);
    };
    ws.onmessage = (ev: MessageEvent) => {
      try {
        this.onMessage(JSON.parse(String(ev.data)) as WsEnvelope);
      } catch {
        /* a malformed message is dropped; the next snapshot or telemetry corrects the screen */
      }
    };
    ws.onclose = () => {
      this.onState(false);
      if (this.stopped) return;
      const delay = CabSocket.backoff(this.attempt++);
      this.timer = this.timers.set(() => this.open(), delay);
    };
    ws.onerror = () => ws.close();
  }
}

/** Keep the store fed from the machine's socket while the component is mounted. */
export function useCabSocket(machineId: string | null): void {
  const apply = useLive((s) => s.apply);
  const setConnected = useLive((s) => s.setConnected);
  useEffect(() => {
    if (!machineId) return;
    const socket = new CabSocket(cabSocketUrl(machineId), apply, setConnected);
    socket.start();
    return () => socket.stop();
  }, [machineId, apply, setConnected]);
}
