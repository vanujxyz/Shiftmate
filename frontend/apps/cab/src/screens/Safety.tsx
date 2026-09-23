/**
 * Safety guard (F-SAFE-02, 04, 05, 06; DESIGN §10 ProximityPanel, RiskIndicator, §9 Risk
 * contributions). Where people are relative to the swing, today's warning distances (wider when
 * risk is raised), what is raising the risk, time without a break, recent alerts, and the cab
 * settings (theme, language, read alerts aloud) with sign-out.
 */
import type { Language } from "@shiftmate/contracts";
import {
  AlertFeedP4,
  Button,
  formatMetres,
  LargeToggle,
  Reach,
  RiskContributions,
  SegmentedControl,
  StackLight,
  StaleMark,
  type Theme,
} from "@shiftmate/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { api } from "../api";
import { useLive } from "../live/store";
import { useSession } from "../session";
import { staleSeconds, staleWords } from "../shell/railProps";
import { useNow } from "../shell/useNow";
import { clockOf, newestFirst, RISK_WORD, sideOf } from "../text";

const LANGS: Language[] = ["en", "hi", "ta"];

export function Safety() {
  const { t, i18n } = useTranslation();
  const live = useLive();
  const session = useSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const tel = live.telemetry;
  const stale = staleWords(t, staleSeconds(live, useNow()));

  const noSensing = !tel || tel.proximity_tier == null;
  const tier = tel?.proximity_tier ?? "clear";
  const person = !noSensing && tier !== "clear" && tel?.proximity_m != null;
  const proxSentence = noSensing
    ? t("ui.safety.prox_basic")
    : person
      ? t("ui.safety.prox_person", {
          distance: formatMetres(tel!.proximity_m!),
          side: t(`ui.side.${sideOf(tel!.proximity_bearing_deg)}`),
        })
      : t("ui.safety.prox_clear");

  const thresholds = live.risk?.thresholds ?? tel?.thresholds ?? {};
  const band = live.risk?.band ?? tel?.risk_band ?? "green";
  const riskWord = t(RISK_WORD[band]);
  const top = (live.risk?.top ?? []) as { component: string; points: number }[];
  const total = top.reduce((s, c) => s + c.points, 0);
  const recent = newestFirst(live.alerts.feed)
    .slice(0, 4)
    .map((a) => ({ id: a.alert_id, title: t(`${a.message_key}.title`), meta: clockOf(a.raised_at) ?? "" }));

  const setLanguage = (lang: Language) => {
    session.setLanguage(lang);
    void i18n.changeLanguage(lang);
  };
  const signOut = async () => {
    await api.signOut().catch(() => undefined);
    session.signOut();
    live.reset();
    queryClient.removeQueries({ queryKey: ["shift"] });
    void navigate("/start");
  };

  const distances: [string, string][] = [
    ["ui.safety.dist_caution", "caution_m"],
    ["ui.safety.dist_danger", "danger_m"],
    ["ui.safety.dist_critical", "critical_m"],
  ];

  return (
    <div className="grid gap-6 p-6 xl:grid-cols-2">
      <section className="sm-rule flex flex-col gap-4 bg-surface p-5">
        <h1 className="text-cab-heading">{t("ui.safety.proximity")}</h1>
        <div className="flex flex-wrap items-center gap-6">
          <Reach
            tier={tier}
            bearing={tel?.proximity_bearing_deg}
            size={230}
            label={proxSentence}
            noSensing={noSensing}
          />
          <div className="flex min-w-0 flex-1 flex-col gap-3">
            <p className="text-cab-body">{proxSentence}</p>
            {stale.text && <StaleMark text={stale.text} />}
            {!noSensing && (
              <>
                <h2 className="text-cab-label">{t("ui.safety.distances")}</h2>
                <ul className="flex flex-col gap-1">
                  {distances.map(([label, key]) =>
                    thresholds[key] != null ? (
                      <li key={key} className="flex justify-between gap-4 text-cab-meta">
                        <span>{t(label)}</span>
                        <span className="sm-num font-bold">{formatMetres(thresholds[key])}</span>
                      </li>
                    ) : null,
                  )}
                </ul>
                {band !== "green" && <p className="text-cab-meta text-ink-2">{t("ui.safety.wider")}</p>}
              </>
            )}
          </div>
        </div>
        {tel && (
          <p className="sm-num text-cab-meta">
            {t("ui.safety.working_for", { minutes: Math.round(tel.continuous_operation_min) })}
            {thresholds.fatigue_warn_min != null && (
              <span className="block text-ink-2">
                {t("ui.safety.break_after", { minutes: Math.round(thresholds.fatigue_warn_min) })}
              </span>
            )}
          </p>
        )}
      </section>

      <section className="sm-rule flex flex-col gap-4 bg-surface p-5">
        <h2 className="text-cab-heading">{t("ui.safety.risk")}</h2>
        <p className="flex items-center gap-4 text-cab-title">
          <StackLight band={band} label={riskWord} size="surface" />
          {riskWord}
        </p>
        <h3 className="text-cab-label">{t("ui.safety.risk_why")}</h3>
        {total > 0 ? (
          <RiskContributions
            rows={top.map((c) => ({ factor: t(`ui.risk.${c.component}`), share: c.points / total }))}
          />
        ) : (
          <p className="text-cab-meta text-ink-2">{t("ui.safety.risk_none")}</p>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-cab-label">{t("ui.safety.recent")}</h2>
        {recent.length > 0 ? (
          <AlertFeedP4 items={recent} label={t("ui.safety.recent")} />
        ) : (
          <p className="text-cab-meta text-ink-2">{t("ui.safety.no_recent")}</p>
        )}
      </section>

      <section className="flex flex-col gap-5 pb-24">
        <h2 className="text-cab-label">{t("ui.safety.settings")}</h2>
        <SegmentedControl<Theme>
          label={t("ui.theme.label")}
          value={session.theme}
          onChange={session.setTheme}
          options={(["day", "sunlight", "night"] as Theme[]).map((v) => ({ value: v, label: t(`ui.theme.${v}`) }))}
        />
        <SegmentedControl<Language>
          label={t("ui.lang.label")}
          value={session.language}
          onChange={setLanguage}
          options={LANGS.map((l) => ({ value: l, label: t(`ui.lang.${l}`), lang: l }))}
        />
        <LargeToggle
          label={t("ui.toggle.read_aloud")}
          on={session.readAloud}
          onChange={session.setReadAloud}
          onText={t("ui.toggle.on")}
          offText={t("ui.toggle.off")}
          disabled={live.mode === "working"}
        />
        {live.mode === "working" && <p className="text-cab-meta text-ink-2">{t("ui.safety.locked")}</p>}
        <div>
          <Button variant="secondary" onClick={() => void signOut()}>
            {t("ui.safety.sign_out")}
          </Button>
        </div>
      </section>
    </div>
  );
}
