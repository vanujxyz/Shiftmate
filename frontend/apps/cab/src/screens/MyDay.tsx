/**
 * My Day (F-INS-06, 07, 08; TRD §11.2 /insights). Private to the signed-in operator (P-01): the
 * edge refuses anyone else and the page says so. Today: how the time went (time-split bar), the
 * stops grouped by cause with the evidence behind each cause, fuel per load against the operator's
 * usual and fuel used while stopped, what went well and one or two ideas. This week: one row per
 * earlier day. Truck waits are named as a site delay, never as the operator's idle time.
 */
import type { IdleReason, InsightsResponse, TimeSplitSegment } from "@shiftmate/contracts";
import {
  Button,
  CoachingNote,
  formatDuration,
  IdleSegmentRow,
  SegmentedControl,
  type SplitKind,
  SystemState,
  TimeSplit,
} from "@shiftmate/ui";
import type { TFunction } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { useInsights } from "../queries";
import { addClock, clockOf, formatQty, noteText } from "../text";

const IDLE: IdleReason[] = [
  "SCHEDULED_BREAK",
  "WARM_UP",
  "UNATTENDED_RUNNING",
  "WAITING_FOR_TRUCK",
  "HABIT",
  "UNKNOWN",
];

/** The edge's time-split kinds onto the bar's: moving counts as working, the rest are stops. */
export function splitKind(kind: string): SplitKind {
  if (kind === "working" || kind === "travel") return "WORKING";
  if (kind === "engine_off") return "OFF";
  return (IDLE as string[]).includes(kind) ? (kind as IdleReason) : "UNKNOWN";
}

/** Neighbouring pieces of the same kind drawn as one. */
export function mergeSplit(segments: TimeSplitSegment[]): { kind: SplitKind; minutes: number }[] {
  const out: { kind: SplitKind; minutes: number }[] = [];
  for (const s of segments) {
    const kind = splitKind(s.kind);
    const last = out.at(-1);
    if (last && last.kind === kind) last.minutes += s.minutes;
    else out.push({ kind, minutes: s.minutes });
  }
  return out;
}

/** Axis labels: shift start, every 2 h, and the latest time. */
function axisOf(segments: TimeSplitSegment[]): string[] {
  const start = clockOf(segments[0]?.start);
  const end = clockOf(segments.at(-1)?.end);
  if (!start || !end) return [];
  const total = segments.reduce((s, x) => s + x.minutes, 0);
  const marks = [start];
  for (let m = 120; m < total - 30; m += 120) marks.push(addClock(start, m));
  return [...marks, end];
}

type StopGroup = { reason: IdleReason; minutes: number; count: number; fuel: number; evidence: string[] };

export function stopGroups(data: InsightsResponse): StopGroup[] {
  const groups = new Map<IdleReason, StopGroup & { longest: number }>();
  for (const s of data.idle_segments) {
    const g = groups.get(s.reason) ?? { reason: s.reason, minutes: 0, count: 0, fuel: 0, evidence: [], longest: -1 };
    g.minutes += s.minutes;
    g.count += 1;
    g.fuel += s.fuel_l;
    if (s.minutes > g.longest) {
      g.longest = s.minutes;
      g.evidence = s.evidence;
    }
    groups.set(s.reason, g);
  }
  return [...groups.values()].sort((a, b) => b.minutes - a.minutes);
}

function evidenceText(t: TFunction, codes: string[]): string {
  return codes.map((c) => t(`evidence.${c}`)).join(", ");
}

function Today({ data }: { data: InsightsResponse }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const totals = data.totals_min;
  const sum = (keys: string[]) => keys.reduce((s, k) => s + (totals[k] ?? 0), 0);
  const working = sum(["working", "travel"]);
  const off = sum(["engine_off"]);
  const stopped = sum(IDLE);
  if (working + off + stopped < 1) {
    return <SystemState kind="empty" heading={t("ui.day.title")} text={t("ui.day.nothing_yet")} />;
  }
  const names = {
    WORKING: t("ui.day.kind.working"),
    OFF: t("ui.day.kind.engine_off"),
    ...Object.fromEntries(IDLE.map((r) => [r, t(`idle.${r}`)])),
  } as Record<SplitKind, string>;
  const groups = stopGroups(data);
  const f = data.fuel;
  const litres = (v: number) => t("ui.day.litres", { value: formatQty(Math.round(v * 10) / 10) });

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
      <div className="flex min-w-0 flex-col gap-6">
        <section className="flex flex-col gap-3">
          <h2 className="text-cab-label">{t("ui.day.split")}</h2>
          <TimeSplit
            segments={mergeSplit(data.time_split)}
            axis={axisOf(data.time_split)}
            names={names}
            summary={t("ui.day.split_summary", {
              working: formatDuration(working),
              stopped: formatDuration(stopped),
              off: formatDuration(off),
            })}
          />
          {/* the same sentence is the chart's caption for screen readers: read once */}
          <p aria-hidden className="sm-num text-cab-meta">
            {t("ui.day.split_summary", {
              working: formatDuration(working),
              stopped: formatDuration(stopped),
              off: formatDuration(off),
            })}
          </p>
        </section>
        <section className="flex flex-col">
          <h2 className="text-cab-label">{t("ui.day.stops")}</h2>
          {groups.length === 0 ? (
            <p className="text-cab-meta text-ink-2">{t("ui.day.no_stops")}</p>
          ) : (
            groups.map((g) => (
              <IdleSegmentRow
                key={g.reason}
                reason={g.reason}
                name={t(`idle.${g.reason}`)}
                why={`${evidenceText(t, g.evidence)} · ${t("ui.day.stop_meta", {
                  count: g.count,
                  fuel: formatQty(Math.round(g.fuel * 10) / 10),
                })}`}
                minutes={g.minutes}
              />
            ))
          )}
          {groups.some((g) => g.reason === "WAITING_FOR_TRUCK") && (
            <p className="pt-2 text-cab-meta text-ink-2">{t("ui.day.truck_note")}</p>
          )}
        </section>
      </div>
      <aside className="flex min-w-0 flex-col gap-5 pb-24">
        <section className="sm-rule flex flex-col gap-3 bg-surface p-5">
          <h2 className="text-cab-label">{t("ui.day.fuel")}</h2>
          <p className="flex flex-col">
            <span className="text-cab-meta text-ink-2">{t("ui.day.fuel_per_load")}</span>
            {f.fuel_per_load_l != null ? (
              <span className="sm-num text-cab-title">
                {litres(f.fuel_per_load_l)}
                {f.usual_fuel_per_load_l != null && (
                  <span className="block text-cab-meta text-ink-2">
                    {t("ui.day.fuel_usual", { value: formatQty(Math.round(f.usual_fuel_per_load_l * 10) / 10) })}
                  </span>
                )}
              </span>
            ) : (
              <span className="text-cab-body">{t("ui.day.no_loads")}</span>
            )}
          </p>
          <p className="flex flex-wrap justify-between gap-x-4 text-cab-label">
            <span>{t("ui.day.fuel_idle")}</span>
            <span className="sm-num font-bold">{litres(f.idle_fuel_l)}</span>
          </p>
          <p className="flex flex-wrap justify-between gap-x-4 text-cab-label">
            <span>{t("ui.day.fuel_total")}</span>
            <span className="sm-num font-bold">{litres(f.fuel_l)}</span>
          </p>
        </section>
        {data.positives.slice(0, 2).map((n) => (
          <CoachingNote key={n.key} kind="went-well" heading={t("ui.coach.went_well")} text={noteText(t, n)} />
        ))}
        {data.coaching.slice(0, 2).map((n) => (
          <CoachingNote
            key={n.key}
            kind="idea"
            heading={t("ui.coach.idea")}
            text={noteText(t, n)}
            action={
              n.lesson_id ? (
                <div>
                  <Button variant="secondary" onClick={() => void navigate(`/learn/${n.lesson_id}`)}>
                    {t("ui.learn.open_lesson")}
                  </Button>
                </div>
              ) : undefined
            }
          />
        ))}
      </aside>
    </div>
  );
}

type Day = {
  day: string;
  working_min: number;
  truck_wait_min: number;
  short_stops_min: number;
  loads: number;
  fuel_per_load_l: number | null;
};

function Week({ data }: { data: InsightsResponse }) {
  const { t, i18n } = useTranslation();
  const days = (data.days ?? []) as Day[];
  if (days.length === 0) return <SystemState kind="empty" heading={t("ui.day.week_title")} text={t("ui.day.no_week")} />;
  const label = new Intl.DateTimeFormat(i18n.language, { weekday: "short", day: "numeric", month: "short" });
  const cols = ["ui.day.col_day", "ui.day.col_working", "ui.day.col_trucks", "ui.day.col_stops", "ui.day.col_loads", "ui.day.col_fuel"];
  return (
    <section className="flex flex-col gap-3 pb-24">
      <h2 className="text-cab-label">{t("ui.day.week_title")}</h2>
      <table className="sm-heavy w-full bg-surface text-left">
        <thead>
          <tr className="sm-rule-b">
            {cols.map((c) => (
              <th key={c} scope="col" className="px-3 py-2 align-bottom text-cab-meta text-ink-2">{t(c)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {days.map((d) => (
            <tr key={d.day} className="sm-rule-soft-b">
              <th scope="row" className="px-3 py-2 text-cab-label">{label.format(new Date(`${d.day}T12:00:00`))}</th>
              <td className="sm-num px-3 py-2 text-cab-label">{formatDuration(d.working_min)}</td>
              <td className="sm-num px-3 py-2 text-cab-label">{formatDuration(d.truck_wait_min)}</td>
              <td className="sm-num px-3 py-2 text-cab-label">{formatDuration(d.short_stops_min)}</td>
              <td className="sm-num px-3 py-2 text-cab-label">{d.loads}</td>
              <td className="sm-num px-3 py-2 text-cab-label">
                {d.fuel_per_load_l != null ? t("ui.day.litres", { value: formatQty(d.fuel_per_load_l) }) : "–"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function MyDay() {
  const { t } = useTranslation();
  const [range, setRange] = useState<"shift" | "week">("shift");
  const insights = useInsights(range);
  return (
    <div className="flex flex-col gap-5 p-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-cab-heading">{t("ui.day.title")}</h1>
          <p className="text-cab-meta text-ink-2">{t("ui.day.private")}</p>
        </div>
        <SegmentedControl<"shift" | "week">
          label={t("ui.day.range")}
          value={range}
          onChange={setRange}
          options={[
            { value: "shift", label: t("ui.day.today") },
            { value: "week", label: t("ui.day.week") },
          ]}
        />
      </header>
      {insights.isPending ? (
        <p className="text-cab-body">{t("ui.shift.loading")}</p>
      ) : insights.isError || !insights.data ? (
        <SystemState kind="error" heading={t("ui.state.error_title")} text={t("ui.state.error_text")} />
      ) : range === "shift" ? (
        <Today data={insights.data} />
      ) : (
        <Week data={insights.data} />
      )}
    </div>
  );
}
