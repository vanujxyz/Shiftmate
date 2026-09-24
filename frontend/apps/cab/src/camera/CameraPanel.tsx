/**
 * Rear camera panel on Safety (DESIGN §10 ProximityPanel; TRD §11.2 "enable camera, calibrate,
 * live distance"). Shows who the camera sees, with a box and a tag in the tier colour, the
 * distance, and whether it is calibrated. Calibration: the helper stands at 3 m and the panel
 * measures. "Test accuracy" records readings at known distances for the TRD §12 protocol and
 * sends them to the gateway (`shiftmate eval camera` writes the results).
 */
import type { CabConfig } from "@shiftmate/contracts";
import { Button, formatMetres, SegmentedControl, SystemState } from "@shiftmate/ui";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { EDGE_URL } from "../api";
import { useLive } from "../live/store";
import { useSession } from "../session";
import { tierOf } from "./geometry";
import { clearResults, recordProtocol, startCalibration, startCamera, stopCamera, useCamera } from "./runtime";

const TAG_FILL: Record<string, string> = {
  caution: "bg-safety-prox-caution text-safety-on-caution",
  danger: "bg-safety-prox-danger text-safety-on-warning",
  critical: "bg-safety-danger text-safety-on-danger",
  clear: "bg-surface text-ink",
};

export function CameraPanel({ config }: { config: CabConfig | undefined }) {
  const { t } = useTranslation();
  const cam = useCamera();
  const machineId = useSession((s) => s.signedIn?.machineId ?? null);
  const thresholds = useLive((s) => s.risk?.thresholds ?? s.telemetry?.thresholds);
  const video = useRef<HTMLVideoElement>(null);
  const [distance, setDistance] = useState<string>("3");
  const [sent, setSent] = useState<string | null>(null);

  useEffect(() => {
    if (video.current && cam.stream && video.current.srcObject !== cam.stream) {
      video.current.srcObject = cam.stream;
      void video.current.play().catch(() => undefined);
    }
  }, [cam.stream]);

  const cc = config?.camera;
  if (!cc || !machineId) return null;

  const r = cam.reading;
  const tier = r ? tierOf(r.distanceM, thresholds) : "clear";
  const pct = (v: number, of: number) => `${(v / Math.max(1, of)) * 100}%`;

  const send = async () => {
    const body = { calibrated: cam.focalPx != null, readings: cam.results };
    try {
      const res = await fetch(`${EDGE_URL}/eval/camera-protocol`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(String(res.status));
      setSent(t("ui.cam.sent", { count: cam.results.length }));
      clearResults();
    } catch {
      setSent(t("ui.cam.send_failed"));
    }
  };

  if (cam.status !== "running") {
    const trouble = cam.status === "no_permission" || cam.status === "no_camera" || cam.status === "failed";
    return (
      <section className="flex flex-col gap-3">
        {trouble ? (
          <SystemState kind="error" heading={t("ui.cam.title")} text={t(`ui.cam.${cam.status}`)} />
        ) : (
          <>
            <h2 className="text-cab-label">{t("ui.cam.title")}</h2>
            <p className="text-cab-meta text-ink-2">{t("ui.cam.intro")}</p>
          </>
        )}
        <div>
          <Button variant="secondary" loading={cam.status === "starting"} onClick={() => void startCamera(cc, machineId)}>
            {cam.status === "starting" ? t("ui.cam.starting") : t("ui.cam.turn_on")}
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-cab-label">{t("ui.cam.title")}</h2>
      <div
        className="relative w-full overflow-hidden rounded-control border-4 border-ink bg-surface-sunk"
        style={{ aspectRatio: `${cam.frame.width || 4} / ${cam.frame.height || 3}` }}
      >
        <video ref={video} muted playsInline aria-label={t("ui.cam.title")} className="absolute inset-0 h-full w-full" />
        {r && (
          <div
            className="absolute border-4 border-ink"
            style={{
              left: pct(r.box.x, cam.frame.width),
              top: pct(r.box.y, cam.frame.height),
              width: pct(r.box.width, cam.frame.width),
              height: pct(r.box.height, cam.frame.height),
            }}
          >
            <span className={`sm-num absolute -top-9 left-0 rounded-chip px-2 text-cab-meta whitespace-nowrap ${TAG_FILL[tier]}`}>
              {t(`ui.tier.${tier}`)} · {formatMetres(Math.round(r.distanceM * 10) / 10)}
            </span>
          </div>
        )}
      </div>
      <p className="text-cab-body">
        {r
          ? t("ui.cam.person", { distance: formatMetres(Math.round(r.distanceM * 10) / 10) })
          : t("ui.cam.nobody")}
      </p>
      <p className="text-cab-meta text-ink-2">
        {cam.calibrating
          ? t("ui.cam.measuring", { distance: cc.calibration_m })
          : cam.focalPx
            ? t("ui.cam.calibrated")
            : t("ui.cam.not_calibrated")}
      </p>
      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" disabled={cam.calibrating != null} onClick={startCalibration}>
          {t("ui.cam.calibrate", { distance: cc.calibration_m })}
        </Button>
        <Button variant="quiet" onClick={stopCamera}>{t("ui.cam.turn_off")}</Button>
      </div>
      <details className="sm-rule-t pt-3">
        <summary className="sm-focus cursor-pointer text-cab-label">{t("ui.cam.test")}</summary>
        <div className="flex flex-col gap-3 pt-3">
          <p className="text-cab-meta text-ink-2">{t("ui.cam.test_hint", { count: cc.protocol_readings })}</p>
          <SegmentedControl<string>
            label={t("ui.cam.true_distance")}
            value={distance}
            onChange={setDistance}
            options={cc.protocol_distances_m.map((d) => ({ value: String(d), label: formatMetres(d) }))}
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="secondary"
              disabled={cam.protocol != null}
              onClick={() => recordProtocol(Number(distance), cc.protocol_readings)}
            >
              {cam.protocol
                ? t("ui.cam.recording", { done: cam.protocol.values.length, total: cam.protocol.target })
                : t("ui.cam.record", { count: cc.protocol_readings })}
            </Button>
            {cam.results.length > 0 && (
              <Button onClick={() => void send()}>{t("ui.cam.send", { count: cam.results.length })}</Button>
            )}
          </div>
          {sent && <p className="text-cab-meta">{sent}</p>}
        </div>
      </details>
    </section>
  );
}
