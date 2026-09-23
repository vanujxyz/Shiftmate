import { act, fireEvent, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useDisplayedMode } from "./CabShell";

describe("mode transition", () => {
  it("goes to Working at once when no finger is down", () => {
    const { result, rerender } = renderHook(({ m }) => useDisplayedMode(m), { initialProps: { m: "paused" as "paused" | "working" } });
    rerender({ m: "working" });
    expect(result.current).toBe("working");
  });

  it("a press already under way finishes first, then Working takes over", () => {
    const { result, rerender } = renderHook(({ m }) => useDisplayedMode(m), { initialProps: { m: "paused" as "paused" | "working" } });
    act(() => void fireEvent.pointerDown(window));
    rerender({ m: "working" });
    expect(result.current).toBe("paused");
    act(() => void fireEvent.pointerUp(window));
    expect(result.current).toBe("working");
  });

  it("back to Paused is never held", () => {
    const { result, rerender } = renderHook(({ m }) => useDisplayedMode(m), { initialProps: { m: "working" as "paused" | "working" } });
    act(() => void fireEvent.pointerDown(window));
    rerender({ m: "paused" });
    expect(result.current).toBe("paused");
  });
});
