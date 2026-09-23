/**
 * Live site map (F-SUP-01; TRD §11.3 /site/:siteId): the site's plan from the gateway, machines,
 * trucks and people from /ws/site, drawn smoothly between 5 Hz updates. The side panel lists the
 * machines; selecting one shows how its day is going (from the Fleet Service) and what is near it.
 * No action buttons: the console does not send trucks or messages to operators (owner decision).
 */
import type { MachineDaySummary, SiteLayout } from "@shiftmate/contracts";
import {
  Button,
  ConsoleSiteMap,
  formatDuration,
  formatMetres,
  MachineGlyph,
  MapLegend,
  MapSymbol,
  PriorityGlyph,
  StaleMark,
  SystemState,
} from "@shiftmate/ui";
import { useQuery } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";

import { edge, fleet } from "../api";
import { type Entities, type EntityMachine, interpolate, nearestPersonBearing, type SiteEvent, useSite, useSiteSocket } from "../live/site";

const STALE_MS = 5000;

/** Re-render every animation frame while mounted (the map glides between updates). */
function useFrame(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    let id = 0;
    const tick = () => {
      setNow(Date.now());
      id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, []);
  return now;
}

export function eventText(t: TFunction, e: SiteEvent): string {
  if (e.type === "alert" && e.code) return t(`alert.${e.code.toLowerCase()}.title`);
  if (e.type === "site_issue") {
    return t(e.status === "cleared" ? "ui.map.site_issue_cleared" : "ui.map.site_issue_open", {
      machine: e.machine_id ?? "",
      zone: e.zone_id ?? "",
    });
  }
  if (["near_miss", "incident", "equipment_problem"].includes(e.type)) return t(`report.type.${e.type}`);
  return e.type;
}

function Detail({
  m,
  day,
  onClose,
}: {
  m: EntityMachine;
  day: MachineDaySummary | undefined;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const tier = m.proximity_tier;
  return (
    <section aria-label={m.id} className="sm-rule flex flex-col gap-4 bg-surface p-4">
      <header className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="flex items-center gap-3">
            <span className="sm-decal text-con-title">{m.id}</span>
            <span className="flex items-center gap-2 text-con-label">
              <MachineGlyph state={m.state} size={24} />
              {t(`ui.machine.${m.state}`)}
            </span>
          </p>
          <p className="text-con-meta text-ink-2">
            {t(`machine.${m.type}`)} · {day?.model ?? ""} · {t(`tier.${m.tier}`)}
          </p>
          {day?.operator_name && (
            <p className="text-con-body">
              {t("ui.detail.operator")}: {day.operator_name}
            </p>
          )}
        </div>
        <Button size="console" variant="secondary" onClick={onClose}>{t("ui.detail.close")}</Button>
      </header>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-con-body">
        <dt className="text-con-label text-ink-2">{t("ui.detail.nearby")}</dt>
        <dd>{tier == null ? t("ui.detail.no_sensing") : t(`ui.tier.${tier}`)}</dd>
        <dt className="text-con-label text-ink-2">{t("ui.legend.rings")}</dt>
        <dd className="sm-num">
          {t("ui.detail.rings", {
            caution: formatMetres(m.rings.caution_m),
            danger: formatMetres(m.rings.danger_m),
            critical: formatMetres(m.rings.critical_m),
          })}
        </dd>
      </dl>
      <h3 className="text-con-label">{t("ui.detail.today")}</h3>
      {day ? (
        <>
          <dl className="grid grid-cols-3 gap-2 text-con-body">
            {[
              ["ui.detail.engine_on", day.engine_on_min],
              ["ui.detail.working", day.working_min],
              ["ui.detail.idle", day.idle_min],
            ].map(([k, v]) => (
              <div key={k as string} className="flex flex-col">
                <dt className="text-con-meta text-ink-2">{t(k as string)}</dt>
                <dd className="sm-num text-con-heading">{formatDuration(v as number)}</dd>
              </div>
            ))}
          </dl>
          <ul className="flex flex-col gap-2">
            {day.tasks.map((task) => (
              <li key={task.task_id} className="sm-rule-soft-b flex flex-col pb-2">
                <span className="flex justify-between gap-3 text-con-label">
                  <span>{t(`task.${task.task_type}`)} · <span className="sm-decal">{task.zone_id}</span></span>
                  <span className="shrink-0">{t(`track.${task.track}`)}</span>
                </span>
                {task.planned_quantity != null && (
                  <span className="sm-num text-con-meta text-ink-2">
                    {t("ui.sum.task_cell", {
                      done: Math.round(task.done_quantity * 10) / 10,
                      total: t(`unit.${task.unit}`, { count: task.planned_quantity }),
                    })}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="text-con-meta text-ink-2">{t("ui.detail.no_day")}</p>
      )}
    </section>
  );
}

function MapView({ layout, siteId }: { layout: SiteLayout; siteId: string }) {
  const { t } = useTranslation();
  const now = useFrame();
  const { prev, next, lastAt, events } = useSite();
  const [selected, setSelected] = useState<string | null>(null);

  const view: Entities | null = useMemo(() => {
    if (!prev || !next) return null;
    const period = Math.max(1, next.at - prev.at);
    return interpolate(prev.data, next.data, (now - next.at) / period);
  }, [prev, next, now]);

  const day = next?.data.ts.slice(0, 10) ?? null;
  const summary = useQuery({
    queryKey: ["summary", siteId, day],
    queryFn: () => fleet.summary(siteId, day),
    enabled: day != null,
    refetchInterval: 30_000,
    retry: false,
  });
  const byId = new Map((summary.data?.machines ?? []).map((m) => [m.machine_id, m]));

  if (!view) return <p className="text-con-body">{t("ui.con.loading")}</p>;
  const stale = lastAt != null && now - lastAt > STALE_MS ? Math.round((now - lastAt) / 1000) : null;
  const sel = view.machines.find((m) => m.id === selected);

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="relative min-w-0">
        <div className="sm-rule overflow-auto">
          <ConsoleSiteMap
            size={layout.layout.size}
            zones={layout.layout.zones as never}
            label={t("ui.map.sentence", { machines: view.machines.length, trucks: view.trucks.length, people: view.workers.length })}
            northLabel={t("ui.map.north")}
            scaleLabel={t("ui.map.scale")}
            selected={selected}
            onSelect={(id) => setSelected((s) => (s === id ? null : id))}
            machines={view.machines.map((m) => ({
              id: m.id,
              label: `${m.id} · ${t(`machine.${m.type}`)} · ${t(`ui.machine.${m.state}`)}${m.proximity_tier && m.proximity_tier !== "clear" ? ` · ${t(`ui.tier.${m.proximity_tier}`)}` : ""}`,
              state: m.state,
              x: m.x_m,
              y: m.y_m,
              heading: m.heading_deg,
              rings: { caution: m.rings.caution_m, danger: m.rings.danger_m, critical: m.rings.critical_m },
              tier: m.proximity_tier,
              personBearing: m.proximity_tier && m.proximity_tier !== "clear" ? nearestPersonBearing(m, view.workers) : null,
            }))}
            trucks={view.trucks.map((tr) => ({ id: tr.id, x: tr.x_m, y: tr.y_m, heading: tr.heading_deg, waiting: tr.state === "waiting" }))}
            people={view.workers.map((w) => ({ id: w.id, x: w.x_m, y: w.y_m }))}
          />
        </div>
        <p className="mt-2 flex flex-wrap items-center gap-4 text-con-meta text-ink-2">
          <span>{t("ui.map.sentence", { machines: view.machines.length, trucks: view.trucks.length, people: view.workers.length })}</span>
          {stale != null && <StaleMark text={t("ui.map.stale", { seconds: stale })} />}
        </p>
        <div className="mt-3">
          <MapLegend
            title={t("ui.legend.title")}
            items={(["machine", "rings", "truck", "worker", "zone"] as const).map((k) => ({ symbol: <MapSymbol kind={k} />, label: t(`ui.legend.${k}`) }))}
          />
        </div>
      </div>
      <aside className="flex min-w-0 flex-col gap-5">
        {sel ? (
          <Detail m={sel} day={byId.get(sel.id)} onClose={() => setSelected(null)} />
        ) : (
          <section className="flex flex-col gap-2">
            <h2 className="text-con-heading">{t("ui.map.machines")}</h2>
            <p className="text-con-meta text-ink-2">{t("ui.map.select_hint")}</p>
            <ul className="sm-rule flex max-h-96 flex-col overflow-y-auto bg-surface">
              {view.machines.map((m) => (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(m.id)}
                    className="sm-focus sm-rule-soft-b flex min-h-(--sm-size-console-target) w-full items-center gap-3 px-3 text-left text-con-body active:bg-surface-sunk"
                  >
                    <MachineGlyph state={m.state} size={22} />
                    <span className="sm-decal font-bold">{m.id}</span>
                    <span className="flex-1 text-ink-2">{t(`ui.machine.${m.state}`)}</span>
                    {m.focus && <span className="text-con-meta">{t("ui.map.focus")}</span>}
                    {m.proximity_tier && m.proximity_tier !== "clear" && (
                      <span className="text-con-label">{t(`ui.tier.${m.proximity_tier}`)}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
        <section className="flex flex-col gap-2">
          <h2 className="text-con-heading">{t("ui.map.events")}</h2>
          {events.length === 0 ? (
            <p className="text-con-meta text-ink-2">{t("ui.map.no_events")}</p>
          ) : (
            <ul className="flex flex-col">
              {events.map((e) => (
                <li key={e.key} className="sm-rule-soft-b flex items-start gap-3 py-2 text-con-body">
                  {e.priority === "P1" || e.priority === "P2" ? (
                    <PriorityGlyph priority={e.priority} size={20} />
                  ) : (
                    <PriorityGlyph priority="P4" size={20} />
                  )}
                  <span className="flex-1">
                    {eventText(t, e)}
                    {e.machine_id && e.type !== "site_issue" && <span className="sm-decal text-ink-2"> · {e.machine_id}</span>}
                  </span>
                  <span className="sm-num text-con-meta text-ink-2">{e.ts.slice(11, 16)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>
    </div>
  );
}

export function SiteMap() {
  const { t } = useTranslation();
  const { siteId = "" } = useParams();
  const layout = useQuery({ queryKey: ["layout"], queryFn: edge.layout, retry: false, refetchInterval: 10_000 });
  const live = layout.data?.site_id === siteId;
  useSiteSocket(live ? siteId : null);

  let body;
  if (layout.isPending) body = <p className="text-con-body">{t("ui.con.loading")}</p>;
  else if (layout.isError) {
    const status = (layout.error as { status?: number }).status;
    // 409: the gateway answers but has no scenario; no status: it could not be reached at all
    body =
      status === 409 ? (
        <SystemState kind="empty" heading={t("ui.map.label")} text={t("ui.con.no_scenario")} />
      ) : status == null ? (
        <SystemState kind="error" heading={t("ui.con.edge_down")} text={t("ui.con.down_text")} />
      ) : (
        <SystemState kind="error" heading={t("ui.state.error_title")} text={layout.error.message} />
      );
  } else if (!live) {
    body = <SystemState kind="empty" heading={t("ui.map.label")} text={t("ui.con.no_scenario")} />;
  } else body = <MapView layout={layout.data!} siteId={siteId} />;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-con-title">
        {layout.data?.site_id === siteId ? layout.data.name : siteId} · {t("ui.map.label")}
      </h1>
      {body}
    </div>
  );
}
