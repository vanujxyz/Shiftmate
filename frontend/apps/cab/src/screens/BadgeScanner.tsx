/**
 * Badge sign-in with the tablet camera (F-START-01): reads the badge QR code with jsQR, all on the
 * tablet. A badge reads "SHIFTMATE:<operator id>". No camera, or no permission, falls back to the
 * PIN pad; the camera stream stops as soon as a code is read or the scanner closes.
 */
import jsQR from "jsqr";
import { useEffect, useRef } from "react";

export const BADGE_PREFIX = "SHIFTMATE:";

/** "SHIFTMATE:OP1001" → "OP1001"; anything else → null. */
export function operatorFromBadge(text: string): string | null {
  if (!text.startsWith(BADGE_PREFIX)) return null;
  const id = text.slice(BADGE_PREFIX.length).trim();
  return /^OP\d{4}$/.test(id) ? id : null;
}

export function cameraAvailable(): boolean {
  return typeof navigator !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
}

export function BadgeScanner({
  onRead,
  onNoCamera,
  label,
}: {
  onRead: (text: string) => void;
  onNoCamera: () => void;
  label: string;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const handlers = useRef({ onRead, onNoCamera });
  useEffect(() => {
    handlers.current = { onRead, onNoCamera };
  }, [onRead, onNoCamera]);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let frame = 0;
    let stopped = false;
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });

    const scan = () => {
      const v = video.current;
      if (stopped || !v || !ctx) return;
      if (v.readyState >= 2 && v.videoWidth > 0) {
        canvas.width = v.videoWidth;
        canvas.height = v.videoHeight;
        ctx.drawImage(v, 0, 0);
        const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const code = jsQR(img.data, img.width, img.height, { inversionAttempts: "dontInvert" });
        if (code?.data) {
          handlers.current.onRead(code.data);
          return;
        }
      }
      frame = requestAnimationFrame(scan);
    };

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user" }, audio: false })
      .then((s) => {
        if (stopped) {
          s.getTracks().forEach((tr) => tr.stop());
          return;
        }
        stream = s;
        if (video.current) {
          video.current.srcObject = s;
          void video.current.play().catch(() => undefined);
        }
        frame = requestAnimationFrame(scan);
      })
      .catch(() => {
        // a refusal that arrives after the scanner has gone (PIN chosen, signed in) changes nothing
        if (!stopped) handlers.current.onNoCamera();
      });

    return () => {
      stopped = true;
      cancelAnimationFrame(frame);
      stream?.getTracks().forEach((tr) => tr.stop());
    };
  }, []);

  return (
    <video
      ref={video}
      aria-label={label}
      muted
      playsInline
      className="h-40 w-64 rounded-control border-4 border-ink bg-surface-sunk object-cover"
    />
  );
}
