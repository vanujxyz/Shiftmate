/**
 * @shiftmate/ui — the design system in code (docs/DESIGN.md).
 *
 * Apps import `@shiftmate/ui/tokens.css` then `@shiftmate/ui/ui.css`, set `data-theme` on their
 * root (`day` is the default, `sunlight`, `night`) and `lang`, and compose these components.
 * Components carry no words of their own: every string arrives translated through props, so the
 * same component renders in en, hi and ta.
 */
export const THEMES = ["day", "sunlight", "night"] as const;
export type Theme = (typeof THEMES)[number];

export * from "./alerts";
export * from "./console";
export * from "./controls";
export * from "./format";
export * from "./glyphs";
export * from "./insights";
export * from "./learn";
export * from "./rail";
export * from "./reach";
export * from "./states";
export * from "./tasks";
export * from "./voice";
