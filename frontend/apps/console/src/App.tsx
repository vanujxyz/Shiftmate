/** Milestone 1 placeholder: shows that the app builds, translates and reaches its backend. */
import { LANGUAGES, type Language } from "@shiftmate/i18n";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { fetchHealth } from "./health";

export function App() {
  const { t, i18n } = useTranslation();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: false,
    refetchInterval: 5000,
  });

  const statusKey = health.isPending
    ? "ui.health.checking"
    : health.isSuccess
      ? "ui.health.fleet_ok"
      : "ui.health.fleet_down";

  return (
    <main lang={i18n.language} className="min-h-screen bg-ground p-12 font-sans text-ink">
      <h1 className="text-con-title">{t("ui.app_name")}</h1>
      <p className="mt-6 text-con-body">{t("ui.scaffold.console")}</p>
      <p role="status" className="mt-6 text-con-label">
        {t(statusKey)}
      </p>
      <div role="group" aria-label={t("ui.lang.label")} className="mt-8 flex gap-4">
        {LANGUAGES.map((lang: Language) => (
          <button
            key={lang}
            type="button"
            lang={lang}
            aria-pressed={i18n.language === lang}
            onClick={() => void i18n.changeLanguage(lang)}
            className="min-h-(--sm-size-console-target) rounded-control border-2 border-action-border px-6 text-con-label aria-pressed:bg-selected aria-pressed:text-on-selected"
          >
            {t(`ui.lang.${lang}`)}
          </button>
        ))}
      </div>
    </main>
  );
}
