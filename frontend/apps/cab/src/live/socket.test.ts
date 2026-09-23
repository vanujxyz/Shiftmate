import { describe, expect, it, vi } from "vitest";

import { CabSocket } from "./socket";

class FakeSocket {
  static made: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(readonly url: string) {
    FakeSocket.made.push(this);
  }
  close() {
    if (this.closed) return;
    this.closed = true;
    this.onclose?.();
  }
}

function setup() {
  FakeSocket.made = [];
  const pending: { fn: () => void; ms: number }[] = [];
  const onMessage = vi.fn();
  const onState = vi.fn();
  const socket = new CabSocket("ws://edge/ws/cab/EXC001", onMessage, onState, FakeSocket as never, {
    set: (fn, ms) => pending.push({ fn, ms }),
    clear: () => undefined,
  });
  return { socket, pending, onMessage, onState };
}

describe("cab socket", () => {
  it("backs off 1, 2, 4, 8 then 10 s", () => {
    expect([0, 1, 2, 3, 4, 5].map(CabSocket.backoff)).toEqual([1000, 2000, 4000, 8000, 10000, 10000]);
  });

  it("reconnects after a drop, and the delay resets once connected", () => {
    const { socket, pending, onState } = setup();
    socket.start();
    FakeSocket.made[0]!.close();
    expect(onState).toHaveBeenLastCalledWith(false);
    expect(pending[0]?.ms).toBe(1000);
    pending[0]!.fn();
    FakeSocket.made[1]!.close();
    expect(pending[1]?.ms).toBe(2000);
    pending[1]!.fn();
    FakeSocket.made[2]!.onopen?.();
    expect(onState).toHaveBeenLastCalledWith(true);
    FakeSocket.made[2]!.close();
    expect(pending[2]?.ms).toBe(1000);
  });

  it("passes parsed messages on and drops malformed ones", () => {
    const { socket, onMessage } = setup();
    socket.start();
    FakeSocket.made[0]!.onmessage?.({ data: JSON.stringify({ type: "telemetry", seq: 1 }) });
    FakeSocket.made[0]!.onmessage?.({ data: "{not json" });
    expect(onMessage).toHaveBeenCalledTimes(1);
    expect(onMessage.mock.calls[0]![0].type).toBe("telemetry");
  });

  it("does not reconnect after stop", () => {
    const { socket, pending } = setup();
    socket.start();
    socket.stop();
    expect(pending).toHaveLength(0);
  });
});
