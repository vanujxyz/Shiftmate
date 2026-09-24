/**
 * Distance to a person from one webcam (TRD §11.2 Camera proximity; the monocular estimate
 * approach): a standing person is about `person_height_m` tall, so with the camera's focal length
 * in pixels `f_px`, distance d = f_px × height_m / box_height_px. Calibration: the helper stands
 * at `calibration_m`, and f_px = box_height_px × calibration_m / height_m, stored per device.
 * Without calibration, f_px comes from the camera's field of view, and the panel says the distance
 * is approximate. Readings are smoothed with an exponential moving average. Pure functions.
 */
import type { CameraSettings } from "@shiftmate/contracts";

export type Box = { x: number; y: number; width: number; height: number; score: number };

export function distanceM(fPx: number, boxHeightPx: number, personHeightM: number): number {
  return (fPx * personHeightM) / Math.max(1, boxHeightPx);
}

export function calibrateFocal(boxHeightPx: number, atM: number, personHeightM: number): number {
  return (boxHeightPx * atM) / personHeightM;
}

/** Focal length in pixels from the vertical field of view (used until the camera is calibrated). */
export function focalFromFov(frameHeightPx: number, fovDeg: number): number {
  return frameHeightPx / 2 / Math.tan(((fovDeg / 2) * Math.PI) / 180);
}

export function ema(previous: number | null, value: number, alpha: number): number {
  return previous == null ? value : alpha * value + (1 - alpha) * previous;
}

/**
 * Bearing on the machine (degrees clockwise from forward) of a box seen by a camera that faces
 * `facingDeg` (180 = the rear camera). A rear camera sees the machine's left on the right of its
 * image, so the offset is subtracted.
 */
export function bearingDeg(boxCenterX: number, frameWidthPx: number, fovDeg: number, facingDeg: number): number {
  const offset = (boxCenterX / Math.max(1, frameWidthPx) - 0.5) * fovDeg;
  const b = facingDeg === 180 ? facingDeg - offset : facingDeg + offset;
  return ((b % 360) + 360) % 360;
}

/** The nearest person is the tallest box that clears the score bar. */
export function nearestPerson(boxes: Box[], scoreMin: number): Box | null {
  return boxes.filter((b) => b.score >= scoreMin).reduce<Box | null>((a, b) => (!a || b.height > a.height ? b : a), null);
}

/** Proximity tier of a distance against the gateway's current warning distances. */
export function tierOf(d: number, thresholds: Record<string, number> | undefined): "clear" | "caution" | "danger" | "critical" {
  if (!thresholds) return "clear";
  if (d <= (thresholds.critical_m ?? 0)) return "critical";
  if (d <= (thresholds.danger_m ?? 0)) return "danger";
  if (d <= (thresholds.caution_m ?? 0)) return "caution";
  return "clear";
}

const FOCAL_KEY = "shiftmate.cab.camera.fpx";

export function savedFocal(): number | null {
  try {
    const v = Number(window.localStorage.getItem(FOCAL_KEY));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

export function saveFocal(fPx: number): void {
  try {
    window.localStorage.setItem(FOCAL_KEY, String(fPx));
  } catch {
    /* calibration lasts for this page only */
  }
}

export type Reading = { distanceM: number; bearingDeg: number; score: number; box: Box };

/** One frame's reading: the nearest person, their smoothed distance and bearing. */
export function reading(
  boxes: Box[],
  frame: { width: number; height: number },
  cfg: CameraSettings,
  fPx: number | null,
  previousM: number | null,
): Reading | null {
  const p = nearestPerson(boxes, cfg.score_min);
  if (!p) return null;
  const focal = fPx ?? focalFromFov(frame.height, cfg.fov_deg);
  const raw = distanceM(focal, p.height, cfg.person_height_m);
  return {
    distanceM: ema(previousM, raw, cfg.ema_alpha),
    bearingDeg: bearingDeg(p.x + p.width / 2, frame.width, cfg.fov_deg, cfg.facing_deg),
    score: p.score,
    box: p,
  };
}
