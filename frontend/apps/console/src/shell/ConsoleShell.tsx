/**
 * The console frame (DESIGN §4 Console grid, §10 DemoControlBar): a 64 px top bar with the
 * sections and the language, then the dashed "Demo mode · simulated data" strip on every page,
 * so simulated data can never be mistaken for live. The site in the links follows the scenario
 * loaded on the machine gateway (the live one), else the first site the fleet knows.
 */
import { type Language, LANGUAGES } from "@shiftmate/i18n";
import { DemoBar, SegmentedControl } from "@shiftmate/ui";
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router";

import { edge } from "../api";

const LANG_KEY = "shiftmate.console.language";

export function savedLanguage(): Language {
  try {
    const v = window.localStorage.getItem(LANG_KEY);
    return (LANGUAGES as readonly string[]).includes(v ?? "") ? (v as Language) : "en";
  } catch {
    return "en";
  }
}

/** The site to open by default: the one live on the gateway, else Chennai (the demo site). */
export function useDefaultSite(): string {
  const demo = useQuery({ queryKey: ["demo-state"], queryFn: edge.demoState, retry: false, refetchInterval: 5000 });
  return demo.data?.site_id ?? "CHN-HWY-01";
}

export function ConsoleShell() {
  const { t, i18n } = useTranslation();
  const site = useDefaultSite();
  const language = (i18n.language as Language) ?? "en";

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dataset.theme = "day";
  }, [language]);

  const setLanguage = (lang: Language) => {
    void i18n.changeLanguage(lang);
    try {
      window.localStorage.setItem(LANG_KEY, lang);
    } catch {
      /* the choice lasts for this page only */
    }
  };

  const links = [
    { to: `/site/${site}`, key: "ui.con.nav.map", match: "/site/" },
    { to: `/supervisor/${site}`, key: "ui.con.nav.summary", match: "/supervisor/" },
    { to: "/fleet", key: "ui.con.nav.fleet", match: "/fleet" },
    { to: "/demo", key: "ui.con.nav.demo", match: "/demo" },
    { to: "/eval", key: "ui.con.nav.eval", match: "/eval" },
  ];

  return (
    <div className="min-h-screen bg-ground text-ink">
      <header className="sm-rule-b flex h-16 items-center gap-8 bg-surface px-6">
        <span className="text-con-title">{t("ui.app_name")}</span>
        <nav aria-label={t("ui.con.nav_label")} className="flex min-w-0 flex-1 flex-wrap gap-1">
          {links.map((l) => (
            <NavLink
              key={l.key}
              to={l.to}
              className={({ isActive }) =>
                `sm-focus flex min-h-(--sm-size-console-target) items-center rounded-control px-3 text-con-label ${isActive ? "bg-selected text-on-selected" : "text-ink active:bg-surface-sunk"}`
              }
            >
              {t(l.key)}
            </NavLink>
          ))}
        </nav>
        <SegmentedControl<Language>
          dense
          label={t("ui.lang.label")}
          value={language}
          onChange={setLanguage}
          options={LANGUAGES.map((l) => ({ value: l, label: t(`ui.lang.${l}`), lang: l }))}
        />
      </header>
      <div className="px-6 pt-4">
        <DemoBar label={t("ui.demo.label")} />
      </div>
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  );
}
