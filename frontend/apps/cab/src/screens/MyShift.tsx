/**
 * My Shift (F-SHIFT-01…06). Paused mode: today's tasks in order, each with an honest range, the
 * reasons that move it and live progress; the conditions panel with the likely finish; suggested
 * breaks; and the P4 "Updates" feed. Working mode shows only `WorkingLine`: the active task,
 * how far along it is and about how long is left.
 */
import type { ShiftResponse, ShiftTask, TaskEstimate } from "@shiftmate/contracts";
import {
  AlertFeedP4,
  ConditionGlyph,
  ConditionsSummary,
  formatDuration,
  formatRange,
  LoadBlocks,
  RangeBar,
  ReasonChip,
  SystemState,
  TaskRow,
} from "@shiftmate/ui";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { type LiveState, useLive } from "../live/store";
import { useShift } from "../queries";
import { useSession } from "../session";
import { addClock, clockOf, factorWord, formatQty, newestFirst, quantity, RISK_WORD } from "../text";

type Row = {
  pt: ShiftTask;
  status: "active" | "next" | "done";
  done: number;
  estimate: TaskEstimate | null;
};

/** Merge the plan with the live socket: progress, status and the newest estimate win. */
export function taskRows(shift: ShiftResponse, live: LiveState): Row[] {
  return shift.tasks.map((pt) => {
    const id = pt.task.task_id;
    const lp = live.progress[id];
    const status = lp?.status ?? pt.task.status ?? "scheduled";
    const done =
      lp?.done_qty ??
      (live.telemetry?.task_id === id ? live.telemetry.task_progress_qty : (pt.progress_qty ?? 0));
    const liveEst = live.estimate?.task_id === id ? live.estimate.estimate : null;
    return {
      pt,
      status: status === "scheduled" ? "next" : status,
      done,
      estimate: liveEst ?? pt.estimate,
    };
  });
}

function effect(minutes: number): string {
  return `${minutes >= 0 ? "+" : "−"}${formatDuration(Math.abs(minutes))}`;
}

function progressText(t: TFunction, row: Row): string {
  const { task } = row.pt;
  return t("ui.shift.progress", {
    done: formatQty(Math.round(row.done * 10) / 10),
    total: quantity(t, task.quantity_unit, task.planned_quantity),
  });
}

function whereText(t: TFunction, row: Row): string {
  const { task } = row.pt;
  if (row.status === "next") {
    const start = clockOf(task.scheduled_start);
    const qty = quantity(t, task.quantity_unit, task.planned_quantity);
    return start ? `${qty} · ${t("ui.shift.starts", { time: start })}` : qty;
  }
  return progressText(t, row);
}

function estimateLabel(t: TFunction, e: TaskEstimate): string {
  return t("ui.shift.estimate_sr", {
    likely: formatDuration(e.p50),
    low: formatDuration(e.p10),
    high: formatDuration(e.p90),
  });
}

export function MyShift() {
  const { t } = useTranslation();
  const shift = useShift();
  const live = useLive();
  const signedIn = useSession((s) => s.signedIn);

  if (shift.isPending) {
    return <p className="p-8 text-cab-body">{t("ui.shift.loading")}</p>;
  }
  if (shift.isError || !shift.data) {
    return (
      <div className="p-8">
        <SystemState kind="error" heading={t("ui.state.error_title")} text={t("ui.state.error_text")} />
      </div>
    );
  }
  const data = shift.data;
  const rows = taskRows(data, live);
  const scaleMax = Math.max(180, ...rows.map((r) => r.estimate?.p90 ?? 0));
  const now = clockOf(live.telemetry?.ts);
  const finish = live.estimate?.likely_finish ?? data.likely_finish;
  const active = rows.find((r) => r.status === "active");
  const topReason = active?.estimate?.reasons.find((r) => r.minutes > 0);

  const cond = data.conditions;
  const heat = live.telemetry?.heat_index_c ?? cond.heat_index_c;
  const condRows = [
    { glyph: <ConditionGlyph condition="heat" size={44} />, label: t("ui.cond.heat"), value: `${Math.round(heat)} °C` },
    { glyph: <ConditionGlyph condition="wet-ground" size={44} />, label: t("ui.cond.wet"), value: t(`ground.${cond.ground_condition}`) },
    cond.precipitation_mm_h > 0
      ? { glyph: <ConditionGlyph condition="rain" size={44} />, label: t("ui.cond.rain"), value: `${cond.precipitation_mm_h} mm/h` }
      : { glyph: <ConditionGlyph condition="dark" size={44} />, label: t("ui.cond.light"), value: t(cond.is_night ? "ui.cond.night_value" : "ui.cond.day_value") },
  ];
  const band = live.risk?.band ?? live.telemetry?.risk_band ?? "green";
  const riskTop = live.risk?.top[0]?.component as string | undefined;
  const riskWord = t(RISK_WORD[band]);

  const feed = [
    ...newestFirst(live.alerts.feed).map((a) => ({
      id: a.alert_id,
      title: t(`${a.message_key}.title`),
      meta: clockOf(a.raised_at) ?? "",
    })),
    ...[...live.notes].reverse().map((n, i) => ({
      id: `note-${live.notes.length - i}`,
      title: t(n.key, { ...(n.values ?? {}) }),
      meta: "",
    })),
  ].slice(0, 6);

  return (
    <div className="grid gap-6 p-6 xl:grid-cols-[minmax(0,1fr)_400px]">
      <section className="flex min-w-0 flex-col gap-4">
        <header className="flex flex-wrap items-baseline justify-between gap-x-6">
          <h1 className="text-cab-heading">{t("ui.shift.title")}</h1>
          <p className="sm-decal text-cab-label text-ink-2">
            {t("ui.shift.header", { id: data.machine_id, name: signedIn?.name ?? data.operator_id })}
          </p>
        </header>
        {rows.length === 0 ? (
          <SystemState kind="empty" heading={t("ui.state.empty_title")} text={t("ui.state.empty_text")} />
        ) : (
          <div className="flex flex-col">
            {rows.map((row, i) => {
              const e = row.estimate;
              const reasons = e?.reasons.filter((r) => Math.abs(r.minutes) >= 1).slice(0, 2) ?? [];
              return (
                <TaskRow
                  key={row.pt.task.task_id}
                  number={i + 1}
                  title={t(`task.${row.pt.task.task_type}`)}
                  where={whereText(t, row)}
                  zone={row.pt.zone_decal}
                  nowLabel={t("ui.task.now")}
                  status={row.status}
                  actual={
                    row.pt.task.actual_duration_min != null
                      ? formatDuration(row.pt.task.actual_duration_min)
                      : undefined
                  }
                  reasons={
                    reasons.length > 0 ? (
                      <>
                        {reasons.map((r) => (
                          <ReasonChip key={r.key} text={t(r.key)} effect={effect(r.minutes)} />
                        ))}
                      </>
                    ) : undefined
                  }
                  range={
                    <RangeBar
                      likely={e?.p50}
                      low={e?.p10}
                      high={e?.p90}
                      scaleMax={scaleMax}
                      confidence={!e ? "unknown" : e.low_confidence ? "low" : "normal"}
                      lowNote={t("ui.task.low_confidence")}
                      unknownText={t("ui.task.unknown")}
                      label={e ? estimateLabel(t, e) : t("ui.task.unknown")}
                      width={260}
                    />
                  }
                />
              );
            })}
          </div>
        )}
        {data.breaks.length > 0 && (
          <section className="flex flex-col gap-2">
            <h2 className="text-cab-label">{t("ui.shift.breaks")}</h2>
            <ul className="flex flex-col gap-1">
              {data.breaks.map((b) => (
                <li key={`${b.at}-${b.reason_key}`} className="flex flex-wrap gap-x-4 text-cab-meta">
                  <span className="sm-num font-bold">{t("ui.shift.break_at", { time: b.at, minutes: b.minutes })}</span>
                  <span className="text-ink-2">{t(b.reason_key)}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </section>
      <aside className="flex min-w-0 flex-col gap-6 pb-24">
        <ConditionsSummary
          heading={t("ui.task.likely_finish")}
          finish={
            finish
              ? now
                ? `${addClock(now, finish.p10)} – ${addClock(now, finish.p90)}`
                : formatRange(finish.p10, finish.p90)
              : t("ui.task.unknown")
          }
          note={topReason ? t("ui.shift.finish_note", { reason: t(topReason.key) }) : undefined}
          rows={condRows}
          risk={
            band !== "green" && riskTop
              ? {
                  band,
                  sentence: t("ui.risk.sentence", { word: riskWord, factor: factorWord(t, riskTop) }),
                  label: riskWord,
                }
              : undefined
          }
        />
        <section className="flex flex-col gap-2">
          <h2 className="text-cab-label">{t("ui.shift.updates")}</h2>
          {feed.length === 0 ? (
            <p className="text-cab-meta text-ink-2">{t("ui.shift.no_updates")}</p>
          ) : (
            <AlertFeedP4 items={feed} label={t("ui.shift.updates")} />
          )}
        </section>
      </aside>
    </div>
  );
}

/** Working mode: one glanceable line for the active task (F-CAB-01). */
export function WorkingLine() {
  const { t } = useTranslation();
  const shift = useShift();
  const live = useLive();
  if (!shift.data) return null;
  const active = taskRows(shift.data, live).find((r) => r.status === "active");
  if (!active) {
    return <p className="px-12 py-8 text-cab-title text-ink-2">{t("ui.shift.no_active")}</p>;
  }
  const { task } = active.pt;
  const e = active.estimate;
  const loads = task.quantity_unit === "loads" && task.planned_quantity <= 40;
  return (
    <section className="flex flex-col gap-5 px-12 py-8" aria-live="polite">
      <p className="flex flex-wrap items-baseline gap-x-6">
        <span className="text-cab-display">{t(`task.${task.task_type}`)}</span>
        <span className="sm-decal text-cab-title">{active.pt.zone_decal}</span>
      </p>
      <p className="sm-num text-cab-title">{progressText(t, active)}</p>
      {loads && (
        <LoadBlocks
          done={Math.floor(active.done)}
          total={task.planned_quantity}
          label={progressText(t, active)}
        />
      )}
      {e?.remaining && (
        <p className="sm-num text-cab-title">
          {t("ui.shift.left", { time: formatDuration(e.p50) })}
        </p>
      )}
    </section>
  );
}
