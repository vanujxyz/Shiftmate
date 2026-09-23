/**
 * @shiftmate/ui — the design system in code (docs/DESIGN.md).
 * Components arrive in milestone 10. Apps import `@shiftmate/ui/tokens.css` for tokens and fonts.
 */
export const THEMES = ["day", "sunlight", "night"] as const;
export type Theme = (typeof THEMES)[number];
