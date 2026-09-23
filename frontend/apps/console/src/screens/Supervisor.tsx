/**
 * Supervisor day summary (F-SUP-02…05; TRD §11.3 /supervisor/:siteId; DESIGN §10
 * IdleCausesBreakdown, SafetyOverview). Tasks by machine with on-track / behind; where time was
 * lost, led by one sentence that names the cause (never the operators), with one suggestion and
 * its basis; the day's safety events (operator names only on safety-critical events); team
 * trends as groups, with small groups hidden (privacy.yaml).
 */
import type { IdleCausesResponse, SafetyResponse, SiteSummary, Suggestion, TrendsResponse } from "@shiftmate/contracts";
import { formatClock, formatDuration, PriorityGlyph, StackLight, SystemState } from "@shiftmate/ui";
import { useQuery } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";

import { fleet } from "../api";

const IDLE_KINDS = ["SCHEDULED_BREAK", "WARM_UP", "UNATTENDED_RUNNING", "WAITING_FOR_TRUCK", "HABIT", "UNKNOWN"];

/** Days the fleet has for this site, newest first (at most 14). */
export function dayOptions(first: string | null, last: string | null, limit = 14): string[] {
  if (!first || !last) return [];
  const out: string[] = [];
  const d = new Date(`${last}T12:00:00Z`);
  const stop = new Date(`${first}T12:00:00Z`).getTime();
  while (d.getTime() >= stop && out.length < limit) {
    out.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() - 1);
  }
  return out;
}

export function suggestionText(t: TFunction, s: Suggestion): string {
  const main = t(s.key, { zone: s.zone_id ?? "", start: s.window_start ?? "", end: s.window_end ?? "" });
  const parts = [main];
  if (s.save_min_low != null && s.save_min_high != null) {
    parts.push(t("ui.idle.saves", { low: formatDuration(s.save_min_low), high: formatDuration(s.save_min_high) }));
  }
  if (s.basis_days != null) parts.push(t("ui.idle.basis", { days: s.basis_days }));
  return parts.join(" · ");
}

function Tasks({ data }: { data: SiteSummary }) {
  const { t } = useTranslation();
  const rows = data.machines.filter((m) => m.tasks.length > 0 || m.engine_on_min > 0);
  const cols = ["ui.sum.col_machine", "ui.sum.col_operator", "ui.sum.col_tasks", "ui.sum.col_engine", "ui.sum.col_working", "ui.sum.col_idle", "ui.sum.col_status"];
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-con-heading">{t("ui.sum.tasks")}</h2>
      <p className="text-con-body">
        {t("ui.sum.tasks_line", { done: data.tasks_done, total: data.tasks_total, behind: data.tasks_behind })}
      </p>
      {rows.length === 0 ? (
        <p className="text-con-meta text-ink-2">{t("ui.fl.no_data")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="sm-rule w-full bg-surface text-left text-con-body">
            <thead>
              <tr className="sm-rule-b">
                {cols.map((c) => (
                  <th key={c} scope="col" className="px-3 py-2 text-con-label text-ink-2">{t(c)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => {
                const done = m.tasks.filter((x) => x.status === "done").length;
                return (
                  <tr key={m.machine_id} className="sm-rule-soft-b">
                    <th scope="row" className="sm-decal px-3 py-1.5 text-con-label">{m.machine_id}</th>
                    <td className="px-3 py-1.5">{m.operator_name ?? "–"}</td>
                    <td className="sm-num px-3 py-1.5">{t("ui.sum.task_cell", { done, total: m.tasks.length })}</td>
                    <td className="sm-num px-3 py-1.5">{formatDuration(m.engine_on_min)}</td>
                    <td className="sm-num px-3 py-1.5">{formatDuration(m.working_min)}</td>
                    <td className="sm-num px-3 py-1.5">{formatDuration(m.idle_min)}</td>
                    <td className="px-3 py-1.5">
                      <span className={m.track === "behind" ? "font-bold underline decoration-2 underline-offset-4" : ""}>
                        {t(`track.${m.track}`)}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function IdleCauses({ data }: { data: IdleCausesResponse }) {
  const { t } = useTranslation();
  const peak = data.truck_wait_by_hour.reduce((a, b) => (b.minutes > a.minutes ? b : a), { hour: 0, minutes: 0 });
  const maxHour = Math.max(1, ...data.truck_wait_by_hour.map((h) => h.minutes));
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-con-heading">{t("ui.idle.title")}</h2>
      {data.lead && (
        <p className="sm-num text-con-display">
          {t(`idle_lead.${data.lead.reason}`, { time: formatDuration(data.lead.minutes) })}
        </p>
      )}
      <p className="text-con-body text-ink-2">
        {t("ui.idle.total", { time: formatDuration(data.total_idle_min), machines: data.machines })}
      </p>
      <table className="sm-rule w-full bg-surface text-left text-con-body">
        <thead>
          <tr className="sm-rule-b">
            {["ui.idle.col_cause", "ui.idle.col_time", "ui.idle.col_share"].map((c) => (
              <th key={c} scope="col" className="px-3 py-2 text-con-label text-ink-2">{t(c)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.causes.map((c) => (
            <tr key={c.reason} className="sm-rule-soft-b">
              <th scope="row" className="px-3 py-1.5 text-left font-normal">
                <span className="flex items-center gap-3">
                  <span aria-hidden className={`sm-idle-${IDLE_KINDS.includes(c.reason) ? c.reason : "UNKNOWN"} h-5 w-5 border-2 border-ink`} />
                  {t(`idle.${c.reason}`)}
                  {c.site_issue && <span className="text-con-meta text-ink-2">({t("ui.idle.site_issue")})</span>}
                </span>
              </th>
              <td className="sm-num px-3 py-1.5">{formatDuration(c.minutes)}</td>
              <td className="px-3 py-1.5">
                <span className="flex items-center gap-2">
                  <span className="h-3 w-40 bg-surface-sunk">
                    <span className="block h-full bg-ink" style={{ width: `${Math.round(c.share * 100)}%` }} />
                  </span>
                  <span className="sm-num">{Math.round(c.share * 100)} %</span>
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex flex-col gap-2">
        <h3 className="text-con-label">{t("ui.idle.by_hour")}</h3>
        {peak.minutes > 0 ? (
          <>
            <p className="text-con-meta text-ink-2">
              {t("ui.idle.by_hour_sentence", { hour: String(peak.hour).padStart(2, "0"), time: formatDuration(peak.minutes) })}
            </p>
            <div aria-hidden className="flex h-24 items-end gap-1">
              {data.truck_wait_by_hour.map((h) => (
                <span key={h.hour} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
                  <span className="w-full bg-ink" style={{ height: `${Math.round((h.minutes / maxHour) * 75)}%` }} />
                  <span className="sm-num text-con-meta text-ink-2">{h.hour}</span>
                </span>
              ))}
            </div>
            <table className="sr-only">
              <tbody>
                {data.truck_wait_by_hour.map((h) => (
                  <tr key={h.hour}>
                    <td>{h.hour}:00</td>
                    <td>{formatDuration(h.minutes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="text-con-meta text-ink-2">{t("ui.idle.no_wait")}</p>
        )}
      </div>
      {data.suggestion && (
        <div className="sm-heavy flex flex-col gap-1 bg-surface p-4">
          <h3 className="text-con-label">{t("ui.idle.suggestion")}</h3>
          <p className="text-con-heading">{suggestionText(t, data.suggestion)}</p>
        </div>
      )}
    </section>
  );
}

function Safety({ data, timeZone }: { data: SafetyResponse; timeZone?: string }) {
  const { t } = useTranslation();
  const p1 = data.p1.filter((e) => (e.detail as { phase?: string } | undefined)?.phase !== "escalated");
  return (
    <section className="sm-rule flex flex-col gap-4 bg-surface p-4">
      <h2 className="text-con-heading">{t("ui.safe.title")}</h2>
      <p className="text-con-body">
        {t("ui.safe.counts", { p1: p1.length, p2: data.p2.length, near: data.near_misses.length, incidents: data.incidents.length })}
      </p>
      <div className="flex flex-col gap-2">
        <h3 className="text-con-label">{t("ui.safe.p1")}</h3>
        {p1.length === 0 ? (
          <p className="text-con-meta text-ink-2">{t("ui.con.none")}</p>
        ) : (
          <ul className="flex flex-col">
            {p1.slice(0, 8).map((e) => (
              <li key={e.event_id} className="sm-rule-soft-b flex items-start gap-3 py-1.5 text-con-body">
                <PriorityGlyph priority="P1" size={20} />
                <span className="flex-1">
                  {e.code ? t(`alert.${e.code.toLowerCase()}.title`) : e.type}
                  <span className="block text-con-meta text-ink-2">
                    <span className="sm-decal">{e.machine_id}</span>
                    {e.operator_name ? ` · ${e.operator_name}` : ""}
                  </span>
                </span>
                <span className="sm-num text-con-meta text-ink-2">{formatClock(e.ts, timeZone)}</span>
              </li>
            ))}
            {p1.length > 8 && <li className="py-1.5 text-con-meta text-ink-2">{t("ui.safe.more", { count: p1.length - 8 })}</li>}
          </ul>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="text-con-label">{t("ui.safe.p2")}</h3>
        {Object.keys(data.p2_counts).length === 0 ? (
          <p className="text-con-meta text-ink-2">{t("ui.con.none")}</p>
        ) : (
          <ul className="flex flex-col">
            {Object.entries(data.p2_counts)
              .sort((a, b) => b[1] - a[1])
              .map(([code, n]) => (
                <li key={code} className="flex items-center gap-3 py-1 text-con-body">
                  <PriorityGlyph priority="P2" size={20} />
                  <span className="flex-1">{t(`alert.${code.toLowerCase()}.title`)}</span>
                  <span className="sm-num font-bold">{n}</span>
                </li>
              ))}
          </ul>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="text-con-label">{t("ui.safe.reports")}</h3>
        {data.reports.length === 0 ? (
          <p className="text-con-meta text-ink-2">{t("ui.con.none")}</p>
        ) : (
          <ul className="flex flex-col">
            {data.reports.map((r) => (
              <li key={r.report_id} className="sm-rule-soft-b py-1.5 text-con-body">
                {t(`report.type.${r.type}`)}
                {r.severity ? ` · ${t(`report.severity.${r.severity}`)}` : ""}
                <span className="block text-con-meta text-ink-2">
                  <span className="sm-decal">{r.machine_id}</span>
                  {r.summary_en ? ` · ${r.summary_en}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="text-con-label">{t("ui.safe.risk")}</h3>
        <ul className="flex max-h-72 flex-col overflow-y-auto">
          {[...data.risk]
            .sort((a, b) => b.red_min - a.red_min || b.amber_min - a.amber_min)
            .map((r) => {
              const band = (r.band ?? "green") as "green" | "amber" | "red";
              const word = t(band === "red" ? "ui.rail.risk_high" : band === "amber" ? "ui.rail.risk_raised" : "ui.rail.risk_low");
              return (
                <li key={r.machine_id} className="flex items-center gap-3 py-1 text-con-body">
                  <StackLight band={band} label={word} size="surface" />
                  <span className="sm-decal w-20 font-bold">{r.machine_id}</span>
                  <span className="sm-num flex-1 text-con-meta text-ink-2">
                    {t("ui.safe.risk_hours", { amber: formatDuration(r.amber_min), red: formatDuration(r.red_min) })}
                  </span>
                </li>
              );
            })}
        </ul>
      </div>
      <p className="sm-rule-t pt-3 text-con-meta text-ink-2">{t("ui.safe.footer")}</p>
    </section>
  );
}

function Trends({ data }: { data: TrendsResponse }) {
  const { t } = useTranslation();
  const waits = data.daily.filter((d) => !d.suppressed && d.truck_wait_min != null).map((d) => d.truck_wait_min!);
  const n = data.min_group_size;
  const fmt = (v: number | null | undefined, unit: "min" | "s" | "L" | "x") =>
    v == null
      ? "–"
      : unit === "min"
        ? t("ui.unit.minutes", { value: v.toFixed(1) })
        : unit === "s"
          ? t("ui.unit.seconds", { value: Math.round(v) })
          : unit === "L"
            ? t("ui.day.litres", { value: v.toFixed(2) })
            : v.toFixed(1);
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-con-heading">{t("ui.trend.title", { days: data.days })}</h2>
      <p className="text-con-meta text-ink-2">{t("ui.trend.note", { n })}</p>
      {waits.length > 0 && (
        <p className="text-con-body">
          {t("ui.trend.daily_sentence", {
            low: formatDuration(Math.min(...waits)),
            high: formatDuration(Math.max(...waits)),
            days: data.days,
          })}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="sm-rule w-full bg-surface text-left text-con-body">
          <thead>
            <tr className="sm-rule-b">
              {["ui.trend.col_group", "ui.trend.col_ops", "ui.trend.col_idle", "ui.trend.col_belt", "ui.trend.col_fuel", "ui.trend.col_p1"].map((c) => (
                <th key={c} scope="col" className="px-3 py-2 text-con-label text-ink-2">{t(c)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.by_experience.map((g) => (
              <tr key={g.group} className="sm-rule-soft-b">
                <th scope="row" className="px-3 py-1.5 text-con-label">{t("ui.trend.years", { group: g.group.replace(/ years$/, "") })}</th>
                {g.suppressed ? (
                  <td colSpan={5} className="px-3 py-1.5 text-ink-2">{t("ui.trend.hidden", { n })}</td>
                ) : (
                  <>
                    <td className="sm-num px-3 py-1.5">{g.operators}</td>
                    <td className="sm-num px-3 py-1.5">{fmt(g.habit_idle_min_per_h, "min")}</td>
                    <td className="sm-num px-3 py-1.5">{fmt(g.seatbelt_unfastened_s_per_h, "s")}</td>
                    <td className="sm-num px-3 py-1.5">{fmt(g.fuel_per_load_cycle_l, "L")}</td>
                    <td className="sm-num px-3 py-1.5">{fmt(g.p1_per_100h, "x")}</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function Supervisor() {
  const { t } = useTranslation();
  const { siteId = "" } = useParams();
  const [date, setDate] = useState<string | null>(null);
  const sites = useQuery({ queryKey: ["sites"], queryFn: fleet.sites, retry: false });
  const site = sites.data?.find((s) => s.site_id === siteId);
  const days = dayOptions(site?.first_date ?? null, site?.last_date ?? null);
  const summary = useQuery({ queryKey: ["summary", siteId, date], queryFn: () => fleet.summary(siteId, date), retry: false });
  const idle = useQuery({ queryKey: ["idle", siteId, date], queryFn: () => fleet.idle(siteId, date), retry: false });
  const safety = useQuery({ queryKey: ["safety", siteId, date], queryFn: () => fleet.safety(siteId, date), retry: false });
  const trends = useQuery({ queryKey: ["trends", siteId], queryFn: () => fleet.trends(siteId), retry: false });

  if (sites.isError) return <SystemState kind="error" heading={t("ui.con.fleet_down")} text={t("ui.con.down_text")} />;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-con-title">{t("ui.sum.title")}</h1>
          <p className="text-con-body text-ink-2">{site?.name ?? siteId}</p>
        </div>
        <label className="flex items-center gap-3 text-con-label">
          {t("ui.con.day")}
          <select
            value={date ?? summary.data?.date ?? ""}
            onChange={(e) => setDate(e.target.value)}
            className="sm-rule sm-focus sm-num min-h-(--sm-size-console-target) bg-surface px-2 text-con-body"
          >
            {summary.data && !days.includes(summary.data.date) && <option value={summary.data.date}>{summary.data.date}</option>}
            {days.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </label>
      </header>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-8">
          {summary.data ? <Tasks data={summary.data} /> : <p className="text-con-body">{t("ui.con.loading")}</p>}
          {idle.data && <IdleCauses data={idle.data} />}
          {trends.data && <Trends data={trends.data} />}
        </div>
        <div className="min-w-0">{safety.data && <Safety data={safety.data} timeZone={site?.timezone} />}</div>
      </div>
    </div>
  );
}

