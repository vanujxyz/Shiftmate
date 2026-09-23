/** Golden rule 10: every key exists in en, hi and ta, and no value is empty. */
import { describe, expect, it } from "vitest";

import { LANGUAGES, type Language, resources } from "./index";

type Tree = { [key: string]: string | Tree };

function flatten(tree: Tree, prefix = ""): Map<string, string> {
  const out = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") out.set(path, value);
    else for (const [k, v] of flatten(value, path)) out.set(k, v);
  }
  return out;
}

describe("i18n completeness", () => {
  const flat = Object.fromEntries(
    LANGUAGES.map((lang) => [lang, flatten(resources[lang].translation as Tree)]),
  ) as Record<Language, Map<string, string>>;
  const allKeys = new Set(LANGUAGES.flatMap((lang) => [...flat[lang].keys()]));

  it.each(LANGUAGES)("%s has every key", (lang) => {
    const missing = [...allKeys].filter((key) => !flat[lang].has(key));
    expect(missing).toEqual([]);
  });

  it.each(LANGUAGES)("%s has no empty strings", (lang) => {
    const empty = [...flat[lang].entries()].filter(([, v]) => v.trim() === "").map(([k]) => k);
    expect(empty).toEqual([]);
  });

  it("interpolation variables match across languages", () => {
    const vars = (s: string) => [...s.matchAll(/\{\{\s*(\w+)\s*\}\}/g)].map((m) => m[1]).sort();
    for (const key of flat.en.keys()) {
      for (const lang of LANGUAGES) {
        expect(vars(flat[lang].get(key) ?? ""), `${lang}:${key}`).toEqual(vars(flat.en.get(key)!));
      }
    }
  });
});
