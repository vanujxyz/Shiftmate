/**
 * What the status rail shows (DESIGN §10 StatusRail, F-CAB-03), as a pure function of the live
 * state and the wall clock:
 * - proximity from the latest telemetry; a machine without people sensing shows "No sensing",
 *   never a clear-looking gauge;
 * - a stale mark once the newest telemetry is older than 30 s (or the socket is down);
 * - risk from the latest risk_update, else the telemetry band;
 * - sync words only when something needs attention (offline, items waiting).
 */
import type { MachineState as EdgeMachineState } from "@shiftmate/contracts";
import { formatMetres, type MachineState, type StatusRailProps } from "@shiftmate/ui";
import type { TFunction } from "i18next";

import type { LiveState } from "../live/store";
import { clockOf, factorWord, RISK_WORD, sideOf } from "../text";

export const STALE_AFTER_MS = 30_000;

const MACHINE_STATE: Record<EdgeMachineState, MachineState> = {
  ENGINE_OFF: "off",
  IDLE: "idle",
  WORKING: "working",
  TRAVELLING: "travel",
};

/** Seconds since the newest telemetry, when that is old enough to say so; else null. */
export function staleSeconds(live: LiveState, now: number): number | null {
  if (live.lastTelemetryAt == null) return null;
  const age = now - live.lastTelemetryAt;
  if (age < STALE_AFTER_MS && live.connected) return null;
  return Math.round(age / 1000);
}

/** "No update 40 s" / "40 s"; past two minutes in minutes, shorter and easier to take in. */
export function staleWords(
  t: TFunction,
  stale: number | null,
): { text: string | undefined; short: string | undefined } {
  if (stale == null) return { text: undefined, short: undefined };
  if (stale >= 120) {
    const minutes = Math.floor(stale / 60);
    return { text: t("ui.stale_min", { minutes }), short: `${minutes} min` };
  }
  return { text: t("ui.stale", { seconds: stale }), short: `${stale} s` };
}

export function railProps(
  live: LiveState,
  t: TFunction,
  now: number,
  machineId: string,
): StatusRailProps {
  const tel = live.telemetry;
  const { text: staleText, short: staleShort } = staleWords(t, staleSeconds(live, now));

  let proximity: StatusRailProps["proximity"];
  if (!tel || tel.proximity_tier == null) {
    const word = t("ui.rail.no_sensing");
    proximity = { tier: "clear", word, label: word, noSensing: true, stale: staleText, staleShort };
  } else if (tel.proximity_tier === "clear" || tel.proximity_m == null) {
    proximity = {
      tier: "clear",
      word: t("ui.rail.clear"),
      label: t("ui.rail.prox_clear_label"),
      stale: staleText,
      staleShort,
    };
  } else {
    const word = t(`ui.prox.${tel.proximity_tier}`);
    proximity = {
      tier: tel.proximity_tier,
      bearing: tel.proximity_bearing_deg,
      word,
      label: t("ui.prox.sr", {
        word,
        distance: formatMetres(tel.proximity_m),
        side: t(`ui.side.${sideOf(tel.proximity_bearing_deg)}`),
      }),
      stale: staleText,
      staleShort,
    };
  }

  const band = live.risk?.band ?? tel?.risk_band ?? "green";
  const top = band !== "green" ? (live.risk?.top[0]?.component as string | undefined) : undefined;
  const riskWord = t(RISK_WORD[band]);
  const reason = top ? t("ui.risk.mainly", { factor: factorWord(t, top) }) : undefined;

  const sync = live.sync;
  const waiting = sync?.outbox_size ?? 0;
  const syncProps: StatusRailProps["sync"] = !live.online
    ? {
        state: "offline",
        words: waiting > 0 ? t("ui.sync.waiting", { count: waiting }) : t("ui.sync.offline"),
        label: t("ui.sync.offline"),
      }
    : waiting > 0
      ? {
          state: "waiting",
          words: t("ui.sync.waiting", { count: waiting }),
          short: String(waiting),
          label: t("ui.sync.waiting", { count: waiting }),
        }
      : { state: "synced", label: t("ui.sync.synced") };

  const machineState = tel ? MACHINE_STATE[tel.state] : "off";
  return {
    mode: live.mode,
    proximity,
    risk: { band, word: riskWord, reason, label: reason ? `${riskWord}, ${reason}` : riskWord },
    belt: tel
      ? {
          fastened: tel.seatbelt_fastened,
          word: t(tel.seatbelt_fastened ? "ui.rail.belt_on" : "ui.rail.belt_off"),
        }
      : null,
    machine: { id: machineId, state: machineState, word: t(`ui.machine.${machineState}`) },
    queue:
      live.alerts.queuedCount > 0 && live.alerts.queueTop
        ? {
            priority: live.alerts.queueTop,
            count: live.alerts.queuedCount,
            label: t("ui.queue.sr", { count: live.alerts.queuedCount }),
          }
        : null,
    sync: syncProps,
    clock: clockOf(tel?.ts) ?? "--:--",
  };
}
