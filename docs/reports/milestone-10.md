# Milestone 10 — Design system in code

## What was built
- **Tokens and themes** (`packages/ui`):
  - The delivered `tokens.css` is wired into Tailwind v4 through its `@theme` block, and is not edited.
  - A new `ui.css` layer adds everything else the components need:
    - Sunlight +100 and Night −50 weight on every text style;
    - Tamil and Devanagari line heights, with no letter-spacing;
    - rule, heavy and dashed borders;
    - the focus ring (4 px outside a 3 px chalk gap), and the press shift (no hover anywhere);
    - the 45° critical hatch;
    - lightness-plus-pattern idle swatches, with no safety hues;
    - the motion keyframes (P1 flash at 1 Hz, alert arrivals, listening ring), with reduced-motion alternatives;
    - Night behaviour (no large fields of safety colour).
  - Anek Latin, Tamil and Devanagari are self-hosted variable fonts, including the width axis for decals and dense Tamil.
- **Glyphs** (`glyphs.tsx`, all drawn by us on a 48-unit grid, with strokes that never scale):
  - machine state (working, idle, travel, off, in plan view);
  - the six idle reasons (none of them points at a person);
  - proximity tiers as miniature Reaches;
  - seatbelt on and off;
  - site-mast sync states (online, offline, waiting, syncing, synced);
  - sensor tier;
  - priority shapes P1–P4 plus the safe tick (safety fill with an ink keyline);
  - conditions (heat, rain, wet ground, dark, fatigue, clock).

  Any glyph given a label is announced as an image with that label.
- **The Reach** (`reach.tsx`), the signature gauge:
  - swing radius (heavy), reach + 2 m (solid), 2× reach (dashed);
  - bezel ticks from 120 px, tracks from 200 px, and the boom and house rotating with the swing;
  - the occupied band as a 56° sector, with the hatch only when someone is inside the swing radius;
  - a person marker;
  - a dashed, slashed "no sensing" gauge for basic machines.
- **Components**, each following its DESIGN card:
  - **Cab frame:** StatusRail (Paused 96 px and Working 176 px; stack light, stale mark, queue pip), BottomNav, PushToTalk.
  - **Alerts:** AlertTakeoverP1 (full screen, flashing frame, hatch band, one action, queue line), AlertBannerP2, AlertStripP3, AlertFeedP4.
  - **Tasks:** TaskRow, RangeBar (normal, low-confidence dashed band with a note, unknown in words), ReasonChip, LoadBlocks, ConditionsSummary, RiskContributions.
  - **Controls:** Button (primary, secondary, quiet, stop, danger-quiet; standard, xl, console, compact; loading and disabled), LargeToggle, SegmentedControl, PinPad, BadgeTarget, ChecklistItem.
  - **My Day:** TimeSplit, IdleSegmentRow, CoachingNote, Sparkline.
  - **Learn:** LessonCard, NarratedCardPlayer, QuizOption, DrillFrame, BookingSlot, SkillLadder.
  - **Voice:** TranscriptSheet, SourceChip, AssistantAnswer (online, offline, "I don't know").
  - **States:** SystemState (empty, error, stale, offline), SyncState, ReportDraftCard.
  - **Console:** MapLegend, MapSymbol, DemoBar, FleetTile.

  Format helpers write "1 h 05 m", "55 m – 1 h 25 m" and a 24 h clock.
- **Kitchen sink:** `/_kitchen-sink` in the console shows every component, with theme (Day, Sunlight, Night) and language (en, hi, ta) switches. Cab components sit in 1280 px cab frames.
- **Strings:** 165 design-vocabulary strings in all three languages (`scripts/i18n/m10_ui.yaml`), taken from DESIGN §11 where DESIGN gives them. Components carry no words of their own (D-069). `docs/TRANSLATIONS_REVIEW.md` has been regenerated.

## Checks that enforce the design
- **Contrast** (90 checks): every text/background pair in DESIGN §2 is recomputed from `tokens.css` in all three themes against the DESIGN §12 targets. Primary text is at least 7:1; secondary at least 4.5:1 (7:1 in Sunlight); marks and focus at least 3:1. All pass, and the Day ink-on-surface pair matches DESIGN's published 16.47.
- **Tokens only in app code:** a test fails on any hex, rgb or hsl colour, font name, raw px value or shadow literal in `frontend/apps` (D-070).
- **No overflow:** a Playwright test in the installed Chrome opens the kitchen sink in 3 themes × 3 languages and fails if anything sticks out of a cab frame or overflows its own box. It passes in all 9 combinations.

## What the overflow check found and fixed
- **Rail words broke in the middle** ("Cle ar"). `overflow-wrap: anywhere` lets flex items shrink to one character, so it became `break-word`.
- **The Tamil Paused rail was about 330 px too wide.** Rail labels now wrap at 24 px within a width budget. The repeated state word is dropped in Tamil and Hindi, and in Tamil the risk reason and the machine segment are dropped too, as DESIGN's review and its 1024 × 768 layout do (D-068).
- **Smaller Tamil fixes:** the Edit button in the report card, the booking slot's "Full" label, the stale note and a condition row now wrap or use a compact size.
- **The Reach undercarriage** was drawn over the critical hatch. It now sits underneath.
- **Night buttons** now get DESIGN's lit border on primary actions.

## How to test
```
pnpm --filter console dev
```
Open http://localhost:5174/_kitchen-sink and use the theme and language switches.
```
pnpm test:all
pnpm e2e
pnpm lint:all
```

## Tests run
- Frontend: 120 tests pass. That's 104 in `ui` (90 contrast, the tokens-only scan and 11 component-behaviour tests), 6 in console (the kitchen sink in en, hi and ta across all three themes with no raw keys, plus the placeholder tests), 3 in cab, and the i18n completeness test.
- e2e: 2 of 2 pass, the kitchen-sink overflow test and the cab smoke test.
- Lint: ruff, eslint and tsc are clean.
- The backend was unchanged in this milestone; its 225 tests passed at milestone 9.

## Decisions
- D-068: Tamil and Hindi status rail: wrap, and drop repeated details.
- D-069: components carry no words; a component layer sits next to the delivered tokens.
- D-070: how "tokens only" and "no overflow" are enforced.

## Observations (for the owner)
- **Translations need a native check.** Hindi and Tamil strings that aren't from DESIGN §11 were written for this milestone and are listed in `docs/TRANSLATIONS_REVIEW.md` for review by native speakers.
- **Ravi's screen changes slightly in Tamil.** Tamil is the demo language, so the Tamil rail shows the machine ID in the screen header rather than in the rail (D-068). Milestone 11 builds that header.
- **Not built yet:** the colour-blindness simulation that DESIGN §12 asks for at release. The shape + word + position cues are built into every component, and the full simulation belongs with the final review (milestone 18).

## Not in this milestone (milestone 11)
The cab app itself: frame, alert layer and queue, sign-in, My Shift and Safety, driven by the Edge Gateway.

## Downloads
None. The fonts and the icon package were already installed in milestone 1.
