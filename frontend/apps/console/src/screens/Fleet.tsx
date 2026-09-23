/**
 * Fleet overview (F-FLT-07, F-FLT-08; DESIGN §10 FleetTiles). One tile per site with its local
 * time, machines active and the risk-band split; the fleet by machine type and sensor tier; the
 * patterns the fleet has learned from finished tasks; and the scale panel: what was measured
 * (live ingest, the simulated 10,000-machine run, the runtime benchmark) kept apart from the
 * clearly labelled projection to 1.6 million machines (golden rule 11: never pass a projection off
 * as a measurement).
 */
import type { FleetPattern, ScaleStats } from "@shiftmate/contracts";
import { FleetTile, formatClock, Sparkline, SystemState } from "@shiftmate/ui";
import { useQuery } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { fleet } from "../api";

const n0 = (v: number) => Math.round(v).toLocaleString("en-IN");

export function patternText(t: TFunction, p: FleetPattern): string {
  const pct = `${p.change_pct >= 0 ? "+" : "−"}${Math.abs(Math.round(p.change_pct))} %`;
  const condition = p.dimension === "ground_condition" ? t(`ground.${p.condition}`).toLocaleLowerCase() : p.condition;
  return t(`pattern.${p.dimension}`, { task: t(`task.${p.task_type}`), condition, pct });
}

/**
 * Scale stats every 5 s, with records per second kept for the last 10 minutes (this page only),
 * for the live ingest sparkline.
 */
function useScale(): { stats: ScaleStats | null; history: number[]; failed: boolean } {
  const [state, setState] = useState<{ stats: ScaleStats | null; history: number[]; failed: boolean }>({
    stats: null,
    history: [],
    failed: false,
  });
  useEffect(() => {
    let live = true;
    const poll = () =>
      fleet
        .scale()
        .then((stats) => {
          if (live) setState((s) => ({ stats, history: [...s.history, stats.live.records_per_s].slice(-120), failed: false }));
        })
        .catch(() => {
          if (live) setState((s) => ({ ...s, failed: true }));
        });
    void poll();
    const id = window.setInterval(() => void poll(), 5000);
    return () => {
      live = false;
      window.clearInterval(id);
    };
  }, []);
  return state;
}

function Scale({ s, history }: { s: ScaleStats; history: number[] }) {
  const { t } = useTranslation();
  const peak = Math.max(0, ...history);
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-con-heading">{t("ui.fl.scale")}</h2>
      <div className="sm-rule flex flex-col gap-3 bg-surface p-4 text-con-body">
        <div className="flex flex-wrap items-center gap-6">
          <p>{t("ui.fl.live", { rate: s.live.records_per_s.toFixed(1) })}</p>
          {history.length > 1 && (
            <Sparkline
              values={history}
              label={t("ui.fleet.spark_label")}
              lastLabel={t("ui.fleet.spark_last", { value: s.live.records_per_s.toFixed(1) })}
              peakLabel={t("ui.fleet.spark_peak", { value: peak.toFixed(1) })}
            />
          )}
        </div>
        <p className="sm-num">
          {t("ui.fl.totals", {
            intervals: n0(s.totals.intervals ?? 0),
            events: n0(s.totals.events ?? 0),
            tasks: n0(s.totals.tasks ?? 0),
            reports: n0(s.totals.reports ?? 0),
          })}
        </p>
        {s.run ? (
          <p className="sm-num">
            {t("ui.fl.run", {
              machines: n0(s.run.machines),
              records: n0(s.run.records),
              seconds: s.run.seconds.toFixed(1),
              rate: n0(s.run.records_per_s),
              p95: s.run.request_ms_p95.toFixed(0),
            })}
          </p>
        ) : (
          <p className="text-ink-2">{t("ui.fl.no_run")}</p>
        )}
        {s.bench && (
          <p className="sm-num">
            {t("ui.fl.bench", {
              cpu: s.bench.cpu_ms_per_tick_mean.toFixed(3),
              mem: s.bench.memory_mb_per_machine.toFixed(3),
              kb: (s.bench.upload_bytes_per_machine_per_hour / 1000).toFixed(1),
            })}
          </p>
        )}
      </div>
      {s.projection && (
        <div className="sm-dash flex flex-col gap-2 bg-surface p-4">
          <p className="sm-num text-con-heading">
            {t("ui.fl.projection", {
              machines: n0(s.projection.machines),
              gb: s.projection.uplink_gb_per_day.toFixed(0),
              rps: n0(s.projection.records_per_s),
              nodes: s.projection.ingest_nodes_at_measured_rate != null ? s.projection.ingest_nodes_at_measured_rate.toFixed(2) : "–",
            })}
          </p>
          <p className="text-con-meta text-ink-2">{t("ui.fl.projection_note", { basis: s.projection.basis })}</p>
        </div>
      )}
    </section>
  );
}

export function Fleet() {
  const { t } = useTranslation();
  const overview = useQuery({ queryKey: ["overview"], queryFn: fleet.overview, retry: false, refetchInterval: 30_000 });
  const patterns = useQuery({ queryKey: ["patterns"], queryFn: fleet.patterns, retry: false });
  const scale = useScale();

  if (overview.isError) return <SystemState kind="error" heading={t("ui.con.fleet_down")} text={t("ui.con.down_text")} />;
  if (!overview.data) return <p className="text-con-body">{t("ui.con.loading")}</p>;
  const o = overview.data;
  const now = new Date();

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-con-title">{t("ui.fl.title")}</h1>
        <p className="text-con-body text-ink-2">{t("ui.fl.machines", { total: o.machines_total, sites: o.sites.length })}</p>
      </header>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {o.sites.map((s) => {
          const bands = { green: s.risk_bands.green ?? 0, amber: s.risk_bands.amber ?? 0, red: s.risk_bands.red ?? 0 };
          return (
            <FleetTile
              key={s.site_id}
              country={s.country}
              localTime={formatClock(now, s.timezone)}
              name={s.name}
              active={t("ui.fleet.active", { active: s.machines_active, total: s.machines_total })}
              bands={bands}
              bandsLabel={t("ui.fleet.bands", bands)}
              condition={
                s.heat_index_c != null && s.ground_condition
                  ? t("ui.fl.condition", { heat: Math.round(s.heat_index_c), ground: t(`ground.${s.ground_condition}`) })
                  : t("ui.fl.no_data")
              }
            />
          );
        })}
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        {(["by_type", "by_tier"] as const).map((k) => (
          <section key={k} className="flex flex-col gap-2">
            <h2 className="text-con-heading">{t(`ui.fl.${k}`)}</h2>
            <ul className="flex flex-col">
              {Object.entries(o[k]).map(([name, count]) => (
                <li key={name} className="sm-rule-soft-b flex items-center gap-4 py-1.5 text-con-body">
                  <span className="w-44">{t(k === "by_type" ? `machine.${name}` : `tier.${name}`)}</span>
                  <span className="h-3 flex-1 bg-surface-sunk">
                    <span className="block h-full bg-ink" style={{ width: `${Math.round((count / Math.max(1, o.machines_total)) * 100)}%` }} />
                  </span>
                  <span className="sm-num w-10 text-right font-bold">{count}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
      {patterns.data && (
        <section className="flex flex-col gap-2">
          <h2 className="text-con-heading">{t("ui.fl.patterns")}</h2>
          <p className="text-con-meta text-ink-2">{t("ui.fl.patterns_note")}</p>
          <ul className="flex flex-col">
            {patterns.data.slice(0, 12).map((p) => (
              <li key={`${p.dimension}-${p.task_type}-${p.condition}`} className="sm-rule-soft-b flex flex-wrap justify-between gap-x-6 py-1.5 text-con-body">
                <span>{patternText(t, p)}</span>
                <span className="sm-num text-con-meta text-ink-2">{t("pattern.basis", { tasks: p.tasks, machines: p.machines })}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {scale.stats && <Scale s={scale.stats} history={scale.history} />}
    </div>
  );
}
