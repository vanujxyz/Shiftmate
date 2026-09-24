/**
 * The webcam person detector (TRD §11.2 Camera proximity; F-SAFE-03). MediaPipe's ObjectDetector
 * (EfficientDet-Lite0, vendored in public/models, WASM bundled by Vite so it works offline) runs on
 * the tablet at about `fps` frames a second. The nearest person's smoothed distance and bearing go
 * to the gateway (`/proximity/camera`, at most `post_hz`), where they feed the same proximity
 * warnings as the machine's sensors. It keeps running in Working mode, which is when a person
 * walks up; the Safety screen only shows it. Nothing leaves the tablet but distance, bearing and
 * confidence: no images.
 */
import type { CameraSettings } from "@shiftmate/contracts";
import { create } from "zustand";

import { EDGE_URL } from "../api";
import { type Box, calibrateFocal, type Reading, reading, saveFocal, savedFocal } from "./geometry";

export type Detector = { detect: (video: HTMLVideoElement, tsMs: number) => Box[]; close: () => void };

/** MediaPipe, loaded only when the camera is turned on (the WASM is ~12 MB). */
export async function mediapipeDetector(): Promise<Detector> {
  const [{ ObjectDetector }, loader, binary] = await Promise.all([
    import("@mediapipe/tasks-vision"),
    import("@mediapipe/tasks-vision/vision_wasm_internal.js?url"),
    import("@mediapipe/tasks-vision/vision_wasm_internal.wasm?url"),
  ]);
  const d = await ObjectDetector.createFromOptions(
    { wasmLoaderPath: loader.default, wasmBinaryPath: binary.default },
    {
      baseOptions: { modelAssetPath: "/models/efficientdet_lite0.tflite", delegate: "CPU" },
      runningMode: "VIDEO",
      scoreThreshold: 0.3,
      categoryAllowlist: ["person"],
      maxResults: 5,
    },
  );
  return {
    detect: (video, ts) =>
      d.detectForVideo(video, ts).detections.flatMap((det) =>
        det.boundingBox
          ? [
              {
                x: det.boundingBox.originX,
                y: det.boundingBox.originY,
                width: det.boundingBox.width,
                height: det.boundingBox.height,
                score: det.categories[0]?.score ?? 0,
              },
            ]
          : [],
      ),
    close: () => d.close(),
  };
}

export type CameraStatus = "off" | "starting" | "running" | "no_permission" | "no_camera" | "failed";

type Protocol = { trueM: number; target: number; values: number[] } | null;

type CameraState = {
  status: CameraStatus;
  stream: MediaStream | null;
  frame: { width: number; height: number };
  reading: Reading | null;
  focalPx: number | null;
  calibrating: number[] | null; // box heights collected at the calibration distance
  protocol: Protocol;
  results: { true_m: number; estimate_m: number }[];
};

export const useCamera = create<CameraState>(() => ({
  status: "off",
  stream: null,
  frame: { width: 0, height: 0 },
  reading: null,
  focalPx: savedFocal(),
  calibrating: null,
  protocol: null,
  results: [],
}));

const CALIBRATION_FRAMES = 10;

type Deps = {
  getUserMedia: (c: MediaStreamConstraints) => Promise<MediaStream>;
  makeDetector: () => Promise<Detector>;
  post: (body: unknown) => Promise<unknown>;
  now: () => number;
};

const defaultDeps = (): Deps => ({
  getUserMedia: (c) => navigator.mediaDevices.getUserMedia(c),
  makeDetector: mediapipeDetector,
  post: (body) =>
    fetch(`${EDGE_URL}/proximity/camera`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => undefined),
  now: () => performance.now(),
});

/**
 * What one reading adds to a calibration (box heights at the calibration distance, averaged over
 * `CALIBRATION_FRAMES`) or to an accuracy protocol run (distances at a known true distance).
 */
export function accumulate(
  s: Pick<CameraState, "calibrating" | "protocol" | "results">,
  r: Reading | null,
  cfg: CameraSettings,
): Partial<CameraState> {
  const patch: Partial<CameraState> = {};
  if (!r) return patch;
  if (s.calibrating) {
    const heights = [...s.calibrating, r.box.height];
    if (heights.length >= CALIBRATION_FRAMES) {
      const avg = heights.reduce((a, b) => a + b, 0) / heights.length;
      patch.focalPx = calibrateFocal(avg, cfg.calibration_m, cfg.person_height_m);
      patch.calibrating = null;
    } else patch.calibrating = heights;
  }
  if (s.protocol) {
    const values = [...s.protocol.values, r.distanceM];
    const trueM = s.protocol.trueM;
    if (values.length >= s.protocol.target) {
      patch.results = [...s.results, ...values.map((v) => ({ true_m: trueM, estimate_m: v }))];
      patch.protocol = null;
    } else patch.protocol = { ...s.protocol, values };
  }
  return patch;
}

let running: { stop: () => void } | null = null;

/** Turn the camera on for `machineId`; `thresholds` is not needed here (tiers are drawn by the UI). */
export async function startCamera(cfg: CameraSettings, machineId: string, deps: Deps = defaultDeps()): Promise<void> {
  if (running) return;
  useCamera.setState({ status: "starting", reading: null });
  let stream: MediaStream;
  try {
    stream = await deps.getUserMedia({ video: { facingMode: "environment", width: 640, height: 480 }, audio: false });
  } catch (e) {
    const name = (e as { name?: string }).name;
    useCamera.setState({ status: name === "NotAllowedError" ? "no_permission" : "no_camera" });
    return;
  }
  let detector: Detector;
  try {
    detector = await deps.makeDetector();
  } catch {
    stream.getTracks().forEach((t) => t.stop());
    useCamera.setState({ status: "failed" });
    return;
  }
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.srcObject = stream;
  await video.play().catch(() => undefined);

  let stopped = false;
  let timer = 0;
  let lastPost = -Infinity;
  const period = 1000 / cfg.fps;
  const step = () => {
    if (stopped) return;
    const width = video.videoWidth || 640;
    const height = video.videoHeight || 480;
    let boxes: Box[] = [];
    try {
      if (video.readyState >= 2) boxes = detector.detect(video, deps.now());
    } catch {
      boxes = [];
    }
    const s = useCamera.getState();
    const r = reading(boxes, { width, height }, cfg, s.focalPx, s.reading?.distanceM ?? null);
    const patch: Partial<CameraState> = { reading: r, frame: { width, height }, ...accumulate(s, r, cfg) };
    if (patch.focalPx != null && patch.focalPx !== s.focalPx) saveFocal(patch.focalPx);
    useCamera.setState(patch);
    const t = deps.now();
    if (r && t - lastPost >= 1000 / cfg.post_hz) {
      lastPost = t;
      void deps.post({
        machine_id: machineId,
        distance_m: Math.round(r.distanceM * 100) / 100,
        confidence: Math.round(r.score * 100) / 100,
        bearing_deg: Math.round(r.bearingDeg),
      });
    }
    timer = window.setTimeout(step, period);
  };
  running = {
    stop: () => {
      stopped = true;
      window.clearTimeout(timer);
      detector.close();
      stream.getTracks().forEach((t) => t.stop());
    },
  };
  useCamera.setState({ status: "running", stream });
  step();
}

export function stopCamera(): void {
  running?.stop();
  running = null;
  useCamera.setState({ status: "off", stream: null, reading: null, calibrating: null, protocol: null });
}

export function startCalibration(): void {
  useCamera.setState({ calibrating: [] });
}

export function recordProtocol(trueM: number, readings: number): void {
  useCamera.setState({ protocol: { trueM, target: readings, values: [] } });
}

export function clearResults(): void {
  useCamera.setState({ results: [] });
}
