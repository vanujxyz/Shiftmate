// @vitest-environment node
/** Every illustration and drill scene named in config has a drawing (D-014). */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { ILLUSTRATIONS } from "./illustrations";

const CONFIG = fileURLToPath(new URL("../../../../config/", import.meta.url));

describe("illustrations", () => {
  it("cover every name used in the lessons and the checklist", () => {
    const names = new Set<string>();
    for (const file of ["lessons.yaml", "checklist.yaml"]) {
      const text = readFileSync(`${CONFIG}${file}`, "utf-8");
      for (const m of text.matchAll(/^\s*(?:illustration|scene|art):\s*([a-z0-9-]+)\s*$/gm)) names.add(m[1]!);
    }
    expect(names.size).toBeGreaterThan(40);
    expect([...names].filter((n) => !ILLUSTRATIONS.includes(n))).toEqual([]);
  });
});
