/**
 * The alert layer (DESIGN §10 AlertQueue; F-SAFE-08, F-SAFE-09). It draws what the edge's alert
 * policy engine decided and plays its sounds; it never re-decides priorities.
 * - P1 current → full-screen takeover, one action ("I've stopped"), no dismiss.
 * - P2 current → orange banner anchored under the rail; the content below stays usable.
 * - P3 strip → yellow strip anchored above the nav (screen bottom in Working mode).
 * - reduced P1 (acknowledged, still true) → the red frame stays and the tone repeats (effects.ts).
 * P4 lives in the My Shift "Updates" feed, never here.
 */
import type { AlertTimings, AlertView } from "@shiftmate/contracts";
import {
  AlertBannerP2,
  AlertStripP3,
  AlertTakeoverP1,
  BeltGlyph,
  PriorityGlyph,
  Reach,
} from "@shiftmate/ui";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { api } from "../api";
import { playTone, speak } from "../live/audio";
import { AlertEffects } from "../live/effects";
import { useLive } from "../live/store";
import { useSession } from "../session";
import { alertWords, sideOf } from "../text";

function send(alert: AlertView, action: "ack" | "later" | "done") {
  // The edge also clears the alert when its condition ends; a lost ack is retried by the operator.
  void api.ack(alert.alert_id, action).catch(() => undefined);
}

/** Sound and speech for the current alerts, for as long as the layer is mounted. */
function useAlertSound(timings: AlertTimings | undefined) {
  const { t, i18n } = useTranslation();
  const alerts = useLive((s) => s.alerts);
  const readAloud = useSession((s) => s.readAloud);
  const effects = useRef<AlertEffects | null>(null);
  const speech = useRef({ readAloud, t, i18n });
  useEffect(() => {
    speech.current = { readAloud, t, i18n };
  }, [readAloud, t, i18n]);

  useEffect(() => {
    if (!timings) return;
    const fx = new AlertEffects(timings, {
      play: playTone,
      speak: (a) => {
        const { readAloud: on, t: tr, i18n: inst } = speech.current;
        if (!on) return;
        speak(tr(`${a.message_key}.speak`), inst.language, inst.getFixedT("en")(`${a.message_key}.speak`));
      },
      setTimer: (fn, ms) => window.setTimeout(fn, ms),
      setRepeat: (fn, ms) => window.setInterval(fn, ms),
      clearTimer: (id) => {
        window.clearTimeout(id);
        window.clearInterval(id);
      },
    });
    effects.current = fx;
    return () => {
      fx.dispose();
      effects.current = null;
    };
  }, [timings]);

  useEffect(() => {
    effects.current?.update(alerts);
  }, [alerts, timings]);

  return effects;
}

function P1Cause({ alert }: { alert: AlertView }) {
  const { t } = useTranslation();
  if (alert.rule_id.startsWith("SEATBELT")) return <BeltGlyph fastened={false} size={300} />;
  if (alert.rule_id.startsWith("PROXIMITY") || alert.rule_id.startsWith("SPEED")) {
    const bearing = typeof alert.context?.bearing_deg === "number" ? alert.context.bearing_deg : null;
    return <Reach tier="critical" bearing={bearing} size={460} label={t(`ui.side.${sideOf(bearing)}`)} />;
  }
  return <PriorityGlyph priority="P1" size={300} />;
}

/** The interrupting alert, anchored under the rail (P2) or over everything (P1). */
export function AlertTop({ timings }: { timings: AlertTimings | undefined }) {
  const { t } = useTranslation();
  const alerts = useLive((s) => s.alerts);
  const effects = useAlertSound(timings);
  const cur = alerts.current;
  const reduced = Object.values(alerts.reduced);

  const ack = (a: AlertView) => {
    effects.current?.acknowledge(a);
    send(a, "ack");
  };

  return (
    <>
      {reduced.length > 0 && cur?.priority !== "P1" && (
        <div aria-hidden data-testid="reduced-p1" className="sm-alert-frame pointer-events-none fixed inset-0 z-(--sm-layer-p2)" />
      )}
      {cur?.priority === "P1" && (() => {
        const w = alertWords(t, cur);
        const more = alerts.queuedCount;
        return (
          <AlertTakeoverP1
            command={t("ui.p1.command")}
            situation={w.title}
            instruction={w.action}
            where={w.where}
            cause={<P1Cause alert={cur} />}
            ackLabel={t("ui.btn.stopped")}
            onAck={() => ack(cur)}
            queueLine={
              more === 1 ? t("ui.p1.queue_one") : more > 1 ? t("ui.p1.queue_many", { count: more }) : undefined
            }
            queuePriority={alerts.queueTop ?? undefined}
          />
        );
      })()}
      {cur?.priority === "P2" && (() => {
        const w = alertWords(t, cur);
        return (
          <div className="absolute inset-x-0 top-0 z-(--sm-layer-p2)">
            <AlertBannerP2
              inline
              situation={w.title}
              detail={w.where ? `${w.action} ${w.where}` : w.action}
              seenLabel={t("ui.btn.seen")}
              onSeen={() => ack(cur)}
            />
          </div>
        );
      })()}
    </>
  );
}

/** The P3 advisory strip, anchored at the bottom of the content area. */
export function AlertBottom() {
  const { t } = useTranslation();
  const strip = useLive((s) => s.alerts.strip);
  if (!strip) return null;
  const w = alertWords(t, strip);
  // Advice with time to act (a break) can wait ("Later" snoozes it); a notice is just "Done".
  const action = strip.category === "risk" ? "done" : "later";
  return (
    <div className="absolute inset-x-0 bottom-0 z-(--sm-layer-p3)">
      <AlertStripP3
        inline
        text={`${w.title}. ${w.action}`}
        actionLabel={t(`ui.btn.${action}`)}
        onAction={() => send(strip, action)}
      />
    </div>
  );
}
