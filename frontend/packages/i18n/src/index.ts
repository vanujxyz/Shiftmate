/**
 * Shared en/hi/ta resources for the cab and console apps (TRD §11.4).
 * Every user-facing string goes through `t()` with a namespaced key.
 */
import i18next, { type i18n } from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import hi from "./locales/hi.json";
import ta from "./locales/ta.json";

export const LANGUAGES = ["en", "hi", "ta"] as const;
export type Language = (typeof LANGUAGES)[number];

export const resources = {
  en: { translation: en },
  hi: { translation: hi },
  ta: { translation: ta },
} as const;

/** Create and initialise an i18next instance for a React app. */
export function createI18n(language: Language = "en"): i18n {
  const instance = i18next.createInstance();
  void instance.use(initReactI18next).init({
    resources,
    lng: language,
    fallbackLng: "en",
    interpolation: { escapeValue: false }, // React already escapes
    initAsync: false, // resources are bundled, so init synchronously
  });
  return instance;
}
