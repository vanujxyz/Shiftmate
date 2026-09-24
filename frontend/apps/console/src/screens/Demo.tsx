/**
 * Demo control (TRD §11.3 /demo, §8 scenarios; DESIGN §10 DemoControlBar): load a scenario,
 * play or pause, change speed, jump to a story beat, take the site's internet away and back,
 * and turn the cab's captions on. Beat captions come from the scenario in the chosen language.
 * Reset demo returns everything to the start of the story (records cleared, 1×, captions off).
 * The fleet tour's scale beat points to the measured 10,000-machine run on the Fleet page.
 * The removed demo buttons (night shift, send a truck, voice note) stay removed (owner decision).
 */
import type { DemoState } from "@shiftmate/contracts";
import { Button, SegmentedControl, SystemState } from "@shiftmate/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { edge } from "../api";

const SPEEDS = [1, 5, 15, 30, 60];

export function Demo() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const state = useQuery({ queryKey: ["demo-state"], queryFn: edge.demoState, retry: false, refetchInterval: 1000 });
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: edge.scenarios, retry: false });
  const [busy, setBusy] = useState(false);

  const act = async (fn: () => Promise<DemoState>) => {
    setBusy(true);
    try {
      const next = await fn();
      queryClient.setQueryData(["demo-state"], next);
      void queryClient.invalidateQueries({ queryKey: ["layout"] });
    } finally {
      setBusy(false);
    }
  };

  if (state.isError) return <SystemState kind="error" heading={t("ui.con.edge_down")} text={t("ui.con.down_text")} />;
  if (!state.data) return <p className="text-con-body">{t("ui.con.loading")}</p>;
  const d = state.data;
  const lang = i18n.language;
  const loaded = scenarios.data?.find((s) => s.name === d.scenario);
  const caption = (c: Record<string, string> | null) => (c ? (c[lang] ?? c.en ?? "") : "");

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-con-title">{t("ui.dm.title")}</h1>

      <section className="sm-dash flex flex-col gap-4 bg-surface p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-con-label">{t("ui.dm.scenario")}</span>
          {(scenarios.data ?? []).map((s) => (
            <Button
              key={s.name}
              size="console"
              variant={s.name === d.scenario ? "primary" : "secondary"}
              disabled={busy}
              onClick={() => void act(() => edge.load(s.name))}
            >
              {s.name === d.scenario ? `${t("ui.dm.reload")}: ${s.title[lang] ?? s.title.en}` : `${t("ui.dm.load")}: ${s.title[lang] ?? s.title.en}`}
            </Button>
          ))}
          <Button size="console" variant="quiet" disabled={busy} onClick={() => void act(edge.reset)}>
            {t("ui.dm.reset")}
          </Button>
        </div>
        {d.scenario ? (
          <>
            <p className="text-con-body">
              {t("ui.dm.loaded", { title: loaded ? (loaded.title[lang] ?? loaded.title.en) : d.scenario })} ·{" "}
              <span className="sm-num">{t("ui.dm.time", { time: d.sim_time?.slice(11, 16) ?? "--:--" })}</span> ·{" "}
              {t(d.playing ? "ui.dm.playing" : "ui.dm.paused")}
            </p>
            <div className="flex flex-wrap items-center gap-4">
              <Button size="console" disabled={busy} onClick={() => void act(d.playing ? edge.pause : edge.play)}>
                {t(d.playing ? "ui.btn.pause" : "ui.btn.play")}
              </Button>
              <span className="text-con-label">{t("ui.dm.speed")}</span>
              <SegmentedControl<string>
                dense
                label={t("ui.dm.speed")}
                value={String(d.speed)}
                onChange={(v) => void act(() => edge.speed(Number(v)))}
                options={SPEEDS.map((x) => ({ value: String(x), label: `${x}×` }))}
              />
            </div>
            <div className="flex flex-wrap items-center gap-4">
              <span className="text-con-label">{t("ui.dm.network")}</span>
              <SegmentedControl<"on" | "off">
                dense
                label={t("ui.dm.network")}
                value={d.online ? "on" : "off"}
                onChange={(v) => void act(() => edge.network(v === "on"))}
                options={[
                  { value: "on", label: t("ui.dm.online") },
                  { value: "off", label: t("ui.dm.offline") },
                ]}
              />
              <span className="text-con-label">{t("ui.dm.captions")}</span>
              <SegmentedControl<"on" | "off">
                dense
                label={t("ui.dm.captions")}
                value={d.captions ? "on" : "off"}
                onChange={(v) => void act(() => edge.captions(v === "on"))}
                options={[
                  { value: "on", label: t("ui.toggle.on") },
                  { value: "off", label: t("ui.toggle.off") },
                ]}
              />
            </div>
            <p className="text-con-body">{t("ui.dm.signed_in", { who: d.signed_in ?? t("ui.dm.nobody") })}</p>
            {d.beats.some((b) => b.action === "scale_demo" && b.done) && (
              <div className="sm-rule flex flex-wrap items-center gap-4 bg-surface-sunk p-3">
                <p className="min-w-0 flex-1 text-con-body">{t("ui.dm.scale_note")}</p>
                <Button size="console" variant="secondary" onClick={() => void navigate("/fleet")}>
                  {t("ui.dm.scale_open")}
                </Button>
              </div>
            )}
            {d.waiting_for && (
              <p className="text-con-heading">
                {t("ui.dm.waiting", { beat: caption(d.beats.find((b) => b.id === d.waiting_for)?.caption ?? null) || d.waiting_for })}
              </p>
            )}
          </>
        ) : (
          <p className="text-con-body">{t("ui.con.no_scenario")}</p>
        )}
      </section>

      {d.scenario && (
        <section className="flex flex-col gap-2">
          <h2 className="text-con-heading">{t("ui.dm.beats")}</h2>
          <ol className="sm-rule flex flex-col bg-surface">
            {d.beats.map((b) => (
              <li key={b.id} className="sm-rule-soft-b flex flex-wrap items-center gap-4 px-3 py-2 text-con-body">
                <span className="sm-num w-14 font-bold">{b.at.slice(0, 5)}</span>
                <span className="min-w-0 flex-1">{caption(b.caption) || b.id}</span>
                {b.done && <span className="text-con-meta text-ink-2">{t("ui.dm.beat_done")}</span>}
                <Button size="console" variant="secondary" disabled={busy} onClick={() => void act(() => edge.seek(b.id))}>
                  {t("ui.dm.go")}
                </Button>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
