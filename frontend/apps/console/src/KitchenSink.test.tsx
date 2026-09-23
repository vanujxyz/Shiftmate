/** The kitchen sink renders every component in 3 themes × 3 languages, with no missing string. */
import { createI18n, LANGUAGES } from "@shiftmate/i18n";
import { THEMES } from "@shiftmate/ui";
import { fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { describe, expect, it } from "vitest";

import { KitchenSink } from "./KitchenSink";

const SECTIONS = ["glyphs", "reach", "rail", "alerts", "tasks", "controls", "insights", "learn", "voice", "states", "console"];

describe("kitchen sink", () => {
  for (const lang of LANGUAGES) {
    it(`renders every section in ${lang}, in every theme, without a raw key`, () => {
      const { container } = render(
        <I18nextProvider i18n={createI18n(lang)}>
          <KitchenSink />
        </I18nextProvider>,
      );
      const root = container.firstElementChild!;
      expect(root).toHaveAttribute("lang", lang);
      for (const id of SECTIONS) expect(container.querySelector(`#${id}`)).not.toBeNull();
      const themeGroup = screen.getAllByRole("group")[0]!;
      const buttons = themeGroup.querySelectorAll("button");
      expect(buttons).toHaveLength(THEMES.length);
      for (const [i, theme] of THEMES.entries()) {
        fireEvent.click(buttons[i]!);
        expect(root).toHaveAttribute("data-theme", theme);
        // i18next shows the key itself when a translation is missing
        expect(root.textContent).not.toMatch(/\b(ui|idle|alert|insight|reason)\.[a-z_.]+/);
      }
      expect(screen.getAllByRole("alertdialog")).toHaveLength(2);
    });
  }
});
