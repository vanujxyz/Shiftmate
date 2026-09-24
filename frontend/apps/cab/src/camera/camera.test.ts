import type { CameraSettings } from "@shiftmate/contracts";
import { afterEach, describe, expect, it } from "vitest";

import { bearingDeg, calibrateFocal, distanceM, ema, focalFromFov, nearestPerson, reading, tierOf } from "./geometry";
import { accumulate, startCamera, stopCamera, useCamera } from "./runtime";

const CFG: CameraSettings = {
  fps: 10,
  score_min: 0.5,
  person_height_m: 1.7,
  calibration_m: 3,
  ema_alpha: 0.4,
  post_hz: 5,
  fov_deg: 60,
  facing_deg: 180,
  protocol_distances_m: [2, 3, 4, 5, 6],
  protocol_readings: 20,
};
const box = (height: number, score = 0.9, x = 270) => ({ x, y: 50, width: 100, height, score });

afterEach(() => stopCamera());

describe("distance from one camera (TRD §11.2)", () => {
  it("d = f × 1.7 m / box height; calibration inverts it", () => {
    const f = calibrateFocal(340, 3, 1.7); // a person 340 px tall at 3 m
    expect(f).toBeCloseTo(600);
    expect(distanceM(f, 340, 1.7)).toBeCloseTo(3);
    expect(distanceM(f, 170, 1.7)).toBeCloseTo(6);
  });

  it("uncalibrated, the focal length comes from the field of view", () => {
    expect(focalFromFov(480, 60)).toBeCloseTo(415.7, 1);
  });

  it("smooths with α 0.4", () => {
    expect(ema(null, 5, 0.4)).toBe(5);
    expect(ema(5, 3, 0.4)).toBeCloseTo(4.2);
  });

  it("the rear camera sees the machine's left on the right of the image", () => {
    expect(bearingDeg(320, 640, 60, 180)).toBe(180);
    expect(bearingDeg(640, 640, 60, 180)).toBe(150);
    expect(bearingDeg(0, 640, 60, 180)).toBe(210);
  });

  it("the nearest person is the tallest box above the score bar", () => {
    expect(nearestPerson([box(100), box(300, 0.4), box(200)], 0.5)?.height).toBe(200);
    expect(nearestPerson([box(300, 0.2)], 0.5)).toBeNull();
  });

  it("tiers follow the gateway's current warning distances", () => {
    const th = { caution_m: 10, danger_m: 6, critical_m: 3.5 };
    expect([12, 8, 5, 2].map((d) => tierOf(d, th))).toEqual(["clear", "caution", "danger", "critical"]);
  });

  it("one frame's reading: smoothed distance and bearing of the nearest person", () => {
    const r1 = reading([box(340)], { width: 640, height: 480 }, CFG, 600, null)!;
    expect(r1.distanceM).toBeCloseTo(3);
    const r2 = reading([box(170)], { width: 640, height: 480 }, CFG, 600, r1.distanceM)!;
    expect(r2.distanceM).toBeCloseTo(0.4 * 6 + 0.6 * 3);
    expect(r2.bearingDeg).toBeCloseTo(180);
    expect(reading([], { width: 640, height: 480 }, CFG, 600, 3)).toBeNull();
  });
});

describe("calibration and the accuracy protocol", () => {
  const r = (h: number, d: number) => ({ distanceM: d, bearingDeg: 180, score: 0.9, box: box(h) });

  it("calibration averages 10 frames at 3 m", () => {
    let s = { calibrating: [] as number[] | null, protocol: null, results: [] };
    let patch = {};
    for (let i = 0; i < 10; i++) {
      patch = accumulate(s, r(340, 3), CFG);
      s = { ...s, ...patch };
    }
    expect((patch as { focalPx: number }).focalPx).toBeCloseTo(600);
    expect(s.calibrating).toBeNull();
  });

  it("a protocol run records the target number of readings at the true distance", () => {
    let s = { calibrating: null as number[] | null, protocol: { trueM: 4, target: 3, values: [] as number[] } as { trueM: number; target: number; values: number[] } | null, results: [] as { true_m: number; estimate_m: number }[] };
    for (const d of [3.8, 4.1, 4.4]) s = { ...s, ...accumulate(s, r(200, d), CFG) };
    expect(s.protocol).toBeNull();
    expect(s.results).toEqual([
      { true_m: 4, estimate_m: 3.8 },
      { true_m: 4, estimate_m: 4.1 },
      { true_m: 4, estimate_m: 4.4 },
    ]);
  });
});

describe("turning the camera on", () => {
  it("a blocked camera says so; a detector that cannot load says so", async () => {
    const fail = (name: string) => () => Promise.reject(Object.assign(new Error(name), { name }));
    await startCamera(CFG, "EXC001", { getUserMedia: fail("NotAllowedError"), makeDetector: () => Promise.reject(new Error()), post: async () => undefined, now: () => 0 });
    expect(useCamera.getState().status).toBe("no_permission");
    await startCamera(CFG, "EXC001", { getUserMedia: fail("NotFoundError"), makeDetector: () => Promise.reject(new Error()), post: async () => undefined, now: () => 0 });
    expect(useCamera.getState().status).toBe("no_camera");
    let stopped = 0;
    const stream = { getTracks: () => [{ stop: () => void stopped++ }] } as unknown as MediaStream;
    await startCamera(CFG, "EXC001", { getUserMedia: async () => stream, makeDetector: () => Promise.reject(new Error("wasm")), post: async () => undefined, now: () => 0 });
    expect(useCamera.getState().status).toBe("failed");
    expect(stopped).toBe(1); // the camera light goes off again
  });
});
