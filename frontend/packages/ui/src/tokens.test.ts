// @vitest-environment node
/**
 * Design-token checks (CLAUDE.md Phase 7 DoD, DESIGN §2 and §12).
 *
 * 1. Contrast: every text/background pair DESIGN lists, recomputed from tokens.css itself with the
 *    WCAG 2 relative-luminance formula, in Day, Sunlight and Night. Targets (DESIGN §12): primary
 *    text ≥ 7:1 everywhere; secondary text ≥ 4.5:1 (Sunlight ≥ 7:1: no grey text in sun);
 *    non-text marks, borders and focus ≥ 3:1.
 * 2. Tokens only in app code (golden rule 9): no hex/rgb/hsl colours, font names or raw pixel
 *    values in frontend/apps — those live in packages/ui.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const UI_SRC = fileURLToPath(new URL(".", import.meta.url));
const APPS = fileURLToPath(new URL("../../../apps/", import.meta.url));

// --- parse tokens.css ------------------------------------------------------------------------

type Vars = Record<string, string>;

function block(css: string, selector: string): Vars {
  const start = css.indexOf(selector);
  if (start < 0) throw new Error(`no ${selector} in tokens.css`);
  const open = css.indexOf("{", start);
  const close = css.indexOf("}", open);
  const out: Vars = {};
  for (const m of css.slice(open + 1, close).matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    out[m[1]!] = m[2]!.trim();
  }
  return out;
}

const css = readFileSync(join(UI_SRC, "tokens.css"), "utf-8");
const day = block(css, ':root, [data-theme="day"]');
const THEMES: Record<string, Vars> = {
  day,
  sunlight: { ...day, ...block(css, '[data-theme="sunlight"] {') },
  night: { ...day, ...block(css, '[data-theme="night"] {') },
};

function resolve(vars: Vars, name: string, depth = 0): string {
  const v = vars[name];
  if (v === undefined || depth > 10) throw new Error(`token ${name} missing`);
  const ref = v.match(/^var\((--[\w-]+)\)$/);
  return ref ? resolve(vars, ref[1]!, depth + 1) : v;
}

function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? [...h].map((c) => c + c).join("") : h;
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r!) + 0.7152 * lin(g!) + 0.0722 * lin(b!);
}

function contrast(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)].sort((p, q) => q - p);
  return (x! + 0.05) / (y! + 0.05);
}

type Kind = "primary" | "secondary" | "nontext" | "disabled";
const TARGET: Record<Kind, Record<string, number>> = {
  primary: { day: 7, sunlight: 7, night: 7 },
  secondary: { day: 4.5, sunlight: 7, night: 4.5 },
  nontext: { day: 3, sunlight: 3, night: 3 },
  disabled: { day: 3, sunlight: 3, night: 3 },
};

// The pairs of DESIGN §2 "Contrast of every text/background pair used".
const PAIRS: [string, string, Kind][] = [
  ["--sm-color-ink", "--sm-color-surface", "primary"],
  ["--sm-color-ink", "--sm-color-ground", "primary"],
  ["--sm-color-ink-2", "--sm-color-surface", "secondary"],
  ["--sm-color-ink-3", "--sm-color-surface", "secondary"],
  ["--sm-color-on-rail", "--sm-color-rail", "primary"],
  ["--sm-color-on-action", "--sm-color-action", "primary"],
  ["--sm-color-on-selected", "--sm-color-selected", "primary"],
  ["--sm-color-on-disabled", "--sm-color-disabled", "disabled"],
  ["--sm-color-ink", "--sm-color-surface-sunk", "primary"],
  ["--sm-safety-on-danger", "--sm-safety-danger", "secondary"],
  ["--sm-safety-on-warning", "--sm-safety-warning", "secondary"],
  ["--sm-safety-on-caution", "--sm-safety-caution", "secondary"],
  ["--sm-safety-on-safe", "--sm-safety-safe", "secondary"],
  ["--sm-safety-on-info", "--sm-safety-info", "secondary"],
  ["--sm-color-ink", "--sm-safety-danger-tint", "primary"],
  ["--sm-safety-danger-ink", "--sm-color-surface", "secondary"],
  ["--sm-safety-warning-ink", "--sm-color-surface", "secondary"],
  ["--sm-safety-caution-ink", "--sm-color-surface", "secondary"],
  ["--sm-safety-safe-ink", "--sm-color-surface", "secondary"],
  ["--sm-safety-info-ink", "--sm-color-surface", "secondary"],
  ["--sm-color-focus", "--sm-color-surface", "nontext"],
  ["--sm-color-focus", "--sm-color-ground", "nontext"],
  ["--sm-color-line", "--sm-color-surface", "nontext"],
  ["--sm-color-mark", "--sm-color-surface", "nontext"],
  ["--sm-color-action-border", "--sm-color-ground", "nontext"],
  ["--sm-safety-danger", "--sm-color-surface", "nontext"],
  ["--sm-safety-idle-waiting", "--sm-color-surface", "nontext"],
  ["--sm-safety-idle-warmup", "--sm-color-surface", "nontext"],
  ["--sm-safety-idle-unattended", "--sm-color-surface", "nontext"],
  ["--sm-safety-time-working", "--sm-color-surface", "nontext"],
];

describe("contrast of every token pair (DESIGN §2, §12)", () => {
  for (const [theme, vars] of Object.entries(THEMES)) {
    it.each(PAIRS)(`${theme}: %s on %s (%s)`, (fg, bg, kind) => {
      const ratio = contrast(resolve(vars, fg), resolve(vars, bg));
      expect(ratio).toBeGreaterThanOrEqual(TARGET[kind][theme]!);
    });
  }

  it("matches a figure DESIGN publishes (Day ink on surface 16.47)", () => {
    const r = contrast(resolve(day, "--sm-color-ink"), resolve(day, "--sm-color-surface"));
    expect(r).toBeCloseTo(16.47, 1);
  });
});

// --- tokens only in app code ---------------------------------------------------------------------

function sources(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (name === "node_modules" || name === "dist" || name === "public") continue;
    if (statSync(path).isDirectory()) out.push(...sources(path));
    else if (/\.(tsx?|css)$/.test(name) && !/\.test\.tsx?$/.test(name) && name !== "test-setup.ts")
      out.push(path);
  }
  return out;
}

const BANNED: [RegExp, string][] = [
  [/#[0-9a-fA-F]{3,8}\b/, "hex colour"],
  [/\b(rgba?|hsla?)\(/, "rgb/hsl colour"],
  [/font-family|\b(Anek|Noto Sans|Arial|Helvetica|Roboto|Inter)\b/, "font name"],
  [/\b\d+(\.\d+)?px\b/, "raw pixel value"],
  [/box-shadow\s*:/, "shadow value"],
];

describe("tokens only in app code (golden rule 9)", () => {
  const files = sources(APPS);

  it("finds the app sources", () => {
    expect(files.length).toBeGreaterThan(4);
  });

  it("has no colour, font or pixel literals outside packages/ui", () => {
    const problems: string[] = [];
    for (const file of files) {
      readFileSync(file, "utf-8")
        .split("\n")
        .forEach((line, i) => {
          if (line.includes("token-exempt")) return; // documented, reviewed exceptions only
          for (const [re, what] of BANNED) {
            if (re.test(line)) problems.push(`${file.slice(APPS.length)}:${i + 1} ${what}: ${line.trim()}`);
          }
        });
    }
    expect(problems).toEqual([]);
  });
});
