# ShiftMate — DESIGN.md


ShiftMate is an in-cab companion for the operators of excavators, wheel loaders and dozers, with a desktop console for site supervisors. It should feel like a well-made instrument that belongs in the cab: calm, rugged, easy to read and trustworthy, and warm in the way it talks to someone who knows the machine better than any app does. It looks out for the operator. It does not watch them.

Two decisions shape everything else. **ShiftMate spends no safety colour on itself.** Red, orange, yellow, green and blue already mean something on a jobsite, and ANSI's purple marks radiation (nuclear density gauges are used on roadworks), so the brand is graphite and chalk. The primary action is a solid graphite slab. **One signature, used well:** the Reach, a plan-view gauge of the machine's swing radius and working envelope, carries all proximity information in the cab, in the P1 takeover and on the supervisor's map.

## 1. Principles

**1. A glance is a safety cost.** Every screen answers one question in one look from 80 cm away. Working mode shows the rail, one task line and alerts, and nothing else.
- Do: "Load trucks 7 / 18" at 56 px with 18 load blocks.
- Don't: a Working-mode screen with a chart, a list or a paragraph.

**2. Safety colour means safety, every time, and never on its own.** Each hazard colour always comes with a shape (octagon, triangle, diamond, square), a position (stack-light lamp, ring band) and a word. The 45° hatch appears only when someone is inside the swing radius.
- Do: P2 = orange field + triangle + "Person close on your left. Slow down."
- Don't: a green "Start" button, a red "Delete" icon, caution stripes as decoration.

**3. Coach. Never blame.** Name the cause, not the person. Start with what went well. "Not sure" is an honest answer.
- Do: "Trucks were late 10:10–10:40."
- Don't: "You were idle for 1 h 05 m."

**4. Honest numbers.** Every estimate is a range with a most-likely value. Low confidence is drawn (dashed band), not hidden, and machines with basic sensors say plainly what they cannot see.
- Do: "~1 h 05 m (55 m – 1 h 25 m)", "Estimated from limited data".
- Don't: "Done at 11:47".

**5. Voice first, buttons always.** Push-to-talk sits in the same corner on every cab screen, and every spoken action has a big-button equivalent.
- Do: say "near miss at LOAD-A", or tap **Near miss**. Both lead to the same draft.
- Don't: a feature that can only be reached by voice, or only by a small tap.

**6. Offline is normal.** The tablet does everything on its own and syncs later. Losing connectivity is calm. Losing sensing is not.
- Do: rail glyph + "3 waiting", answer tagged "Offline answer · manual saved 18 Sep".
- Don't: a red "No connection!" banner.

**7. Three scripts are the design, not a translation.** Tamil runs 30–50% longer and needs taller lines, so layouts are built for Tamil first and then checked in Latin.
- Do: wrap to two lines, use `wdth 92` on chips, drop a repeated detail.
- Don't: truncate a safety message, or shrink Tamil below the Latin size.

## Using this system (for builders)

- Colours: surfaces `sm-color-ground` and `sm-color-surface`; text `sm-color-ink`, `sm-color-ink-2` and `sm-color-ink-3`; primary action `sm-color-action` with `sm-color-on-action`. Safety meaning only through `sm-safety-*` tokens, and always with the matching glyph from **Glyphs**.
- Themes: `:root` is Day; set `data-theme="sunlight"` or `"night"` on the cab root. The theme follows ambient light (lux > 20,000 goes to Sunlight, < 50 goes to Night, with hysteresis), and the operator can override it.
- Type: Anek (Latin, Tamil and Devanagari cuts of one superfamily). Cab roles are `sm-text-cab-*` and console roles are `sm-text-con-*`. Nothing in the cab is smaller than 24 px, and nothing smaller than 36 px shows while the machine moves.
- Targets: at least `sm-size-target-min` (68 px ≈ 18 mm), `sm-space-4` between targets, and `sm-space-8` or opposite sides for opposing actions.
- Layers: `sm-layer-p1` > `sm-layer-p2` > `sm-ptt` > sheet > P3 > rail > content. Only one interrupting alert at a time (see **AlertQueue**).
- Motion only marks a change of state. There is no hover anywhere.
- The Tailwind v4 `@theme` mapping and the full `tokens.css` are in **Implementation: tokens.css**.


## Proposal and self-critique

### 1. Proposal (as first written)

**Point of view.** ShiftMate is a cab instrument, not an app. It should read like the gauge cluster and the site layout drawing an operator already trusts: calm when nothing is wrong, unmistakable when something is, and always in plain words. Operators are the experts here, so the interface stays quiet and leaves the judgement to them. It speaks up only when a person's safety is involved, and even then it tells the operator what to do rather than what they did wrong.

**Palette (first draft).** Concrete neutrals, a "survey violet" brand accent (#4B2E83), and ISO/ANSI safety hues.

**Type.** Anek (Ek Type), a single OFL superfamily with Latin, Tamil and Devanagari cuts and a width axis. Cab scale 24 / 28 / 30 / 36 / 48 / 72 / 120 px; console 13–40 px.

**Cab layout.**

```
WORKING (machine moving)                         PAUSED (still ≥ 30 s)
┌────────────────────────────────────────────┐   ┌────────────────────────────────────────────┐
│ REACH ◎ Clear │▮ Risk raised │ Belt on │ 10:42│   │◎Clear│▮Risk│Belt│EXC001│        ⟟✓ │ 10:42 │ 96
│  (148)        │  Heat        │         │      │176├────────────────────────────────────────────┤
├────────────────────────────────────────────┤   │ ┌1 Now Load trucks ─── ~1h05 ▭▭█▮▭ ┐ ┌Likely┐ │
│                                            │   │ │  18 loads LOAD-A 7/18  [Trucks…] │ │15:10–│ │
│ [1] Load trucks  7 / 18                    │   │ ├2 Trench ──────────── ~2h10 ▭▭▭█▮┤ │15:55 │ │
│     ~1 h 05 m left (55 m – 1 h 25 m)       │   │ │  60 m DIG-A     [Wet ground +20–40]│ │Heat  │ │
│ ■■■■■■■□□□□□□□□□□□□  (loads)               │   │ ├3 Backfill ─────────── ~1h00 ▭█▮▭▭┤ │Ground│ │
│                                            │   │ │  120 m³ DIG-A   [Heat +10 breaks] │ │Risk ▮│ │
│        (alert safe zone: P2 drops here)    │   │ └──────────────────────────────────┘ └──────┘ │
│                                      (PTT) │   ├──────┬──────┬──────┬──────┬──────┬────(PTT)─┤
│ [P3 strip — bottom, clear of PTT]          │   │Shift │Safety│Report│My day│Learn │Hold to   │ 112
└────────────────────────────────────────────┘   └──────┴──────┴──────┴──────┴──────┴──────────┘
```

**Console layout.** A 1440 px, 12-column grid: a top bar, then either the map at 8–9 columns with a 380 px detail panel, or summary panels. A site layout drawing rather than a dashboard.

**Iconography.** Custom plan-view glyphs for machine states, idle reasons, proximity, belt and sync. Phosphor Bold for generic UI.

**Signature.** The Reach: the machine's swing radius, reach + 2 m and 2× reach as a plan-view gauge.

### 2. Self-critique and what changed

I checked the draft against the §5 list and against what I would produce for any "industrial dashboard" prompt.

| Overlap found | Why it was a problem | Change |
| --- | --- | --- |
| **Survey-violet brand** | ANSI Z535.1 includes safety purple for radiation hazards, and nuclear density gauges are common on roadworks. Violet also collapses into blue (information) for many colour-blind operators. The brief rules out "any safety colour". | **No brand hue at all.** Brand = graphite + chalk. The primary action is a graphite slab (a lit-border slab at Night). Identity comes from the Reach and from Anek's stencil-like wide cut, not from a hue. |
| Dark graphite rail in every theme | This is the generic "dark industrial dashboard" look, and dark panels mirror the sky in direct sun. | The rail is graphite in Day and Night, **white with a 5 px black rule in Sunlight**. |
| One radius (12 px) on panels, buttons and chips | The SaaS card kit. | Radius by role: layers 0, plates 6, controls 10, instrument bezels 20, discs full. Task rows are joined by shared rules, not floating cards. |
| Soft shadow on panels | Card-kit tell. | Elevation is a hard edge or a scrim, never a blur (`sm-elev-*`). |
| KPI tile row on the supervisor summary | §5 explicitly. | The summary opens with **one sentence** ("212 of 230 truck loads…") and one lead number inside the "where time was lost" panel. Tiles appear only on the Fleet view, where the brief asks for the scale panel. |
| ALL-CAPS labels for rail segments and section heads | §5 eyebrow tell. | Sentence case everywhere. The wide (wdth 125) decal style is reserved for identifiers that are already uppercase on the machine: `EXC001`, `LOAD-A`. |
| Idle categories in "earth" hues (ochre, clay, laterite) | Ochre reads as caution yellow and laterite as danger red, especially in glare. | Idle categories use **lightness steps of slate and stone plus a pattern** (solid, ticks, dots, lines, dashed outline), always with a label. |
| Reach used everywhere (progress rings, lesson art, empty states) | Boldness spread thin stops being a signature and starts to look like a gimmick. | The Reach appears only where proximity is the subject: rail, Safety Guard, P1 and map rings. Progress uses load blocks and ladders. |
| Stack light, Reach and hatch all "bold" | Three bold ideas compete with each other. | The stack light was made quiet (small, one lamp lit). The hatch is kept strictly for critical proximity. The Reach carries the boldness. |

**Where the brief conflicts, safety wins:**
- The brief's proximity tier is named "danger", but ANSI DANGER is red. A person inside reach + 2 m calls for *slowing down* (warning), so that tier uses orange (`sm-safety-prox-danger` → warning) and red is reserved for "critical / stop".
- The "7:1 on all text" target applies in Sunlight. In Night, lower luminance protects dark adaptation, so secondary text sits at 4.5–5.8:1 while primary text stays ≥ 9:1.
- Red and green differ by hue more than lightness in Day. They are never used without shape and position (stack-light position, octagon versus circle-tick), which meets the colour-independence rule without changing the standard hues.
- The 1280 × 800 layouts assume the brief's reference density (68 px = 18 mm). A physically smaller 10" tablet must scale up (`--sm-density`) and use the 1024 × 768 grid rather than shrink targets.

### 3. Review pass (step 4): one element removed from each screen

Every screen was rendered at 1280 × 800 (console 1440 × 900) in Day, the starred screens also in Sunlight and Night, and My Shift in Tamil and Hindi. Overflow was checked in a headless browser and contrast with a script (see Colour). What was found and what was taken out:

| Screen | Found in review | Removed / fixed |
| --- | --- | --- |
| 1 My Shift Paused | Third task row clipped; the page title repeated the tab | Removed the "My shift" title and the "Daylight until" row (irrelevant at 10:42); "Likely finish" moved into the conditions panel |
| 2 My Shift Working | Progress was only words | Removed the machine segment and the sync word from the Working rail; added one row of load blocks |
| 3 P1 person | Four numbers competing; queue line clipped | Removed the 120 px "2 m" hero; the Reach shows where, and the distance moved into one line |
| 4 P1 seatbelt | A 72 px two-line headline wrapped badly | Removed the Reach from this takeover (proximity is not the subject); split the headline |
| 5 Idle: waiting | The last-hour bar competed with the one fact that matters | Removed the time-split bar and legend; kept the cause, the ETA and the no-blame line |
| 6 Safety Guard | Contribution bars unreadable at 200 px | Removed the "Cameras + radar" label; bars now run full width under each factor |
| 7 Report | Draft pushed Send under the nav | Merged "Where" and "When" into one field |
| 8 My Day | Six idle rows plus notes overflowed | Removed "Breaks" as a row (still visible in the bar) |
| 9 Lesson / drill | Language control pushed Pause off-screen | Moved the language control to the header; removed the lesson-name breadcrumb |
| 10 Ask Cat | "Show the page" duplicated the source chips | Removed the "Show the page" button (source chips open the page) |
| 11 Tamil / Hindi | Rail, chips and panel overflowed in Tamil | Removed the sync word when synced (glyph only, all languages); in Tamil removed the repeated risk reason from the rail and the finish note (the risk line and chips carry both); shortened chip strings; `wdth 92` on chips |
| 12 Basic sensors | An empty Reach looked like "clear" | Removed the gauge rings; replaced them with the dashed, slashed "No sensing" gauge |
| 13 Live map | Carriageway band dominated the drawing | Thinned the band and reduced it to 60% |
| 14 Day summary | Panel clipped at 900 px | Shortened the waiting-by-hour chart (170 → 124 px) |
| 15 Fleet | Empty space under the scale panel | Removed the "Sorted by local time" label; added the ingest sparkline and region table in the space |


## 2. Colour

ShiftMate has **no brand hue**. The brand is graphite (`sm-color-action`, `sm-color-rail`) and chalk (`sm-color-chalk`): the colours of a stencilled plate and a chalk line. Every chromatic colour in the system is a safety colour, and each one keeps a single meaning. Safety colours follow ISO 3864 / ANSI Z535 logic: red = danger/stop, orange = warning, yellow = caution, green = safe condition, blue = information or mandatory action.

Three themes: **Day** (default, `:root`), **Sunlight** (`[data-theme="sunlight"]`: pure black on white, heavier strokes, no greys, all text ≥ 7:1) and **Night** (`[data-theme="night"]`: dark ground, ink held to about 45% of white, no large bright fields, blue desaturated, alert hues kept apart by shape and position).

### Rules
- Text goes on `sm-color-surface` or `sm-color-ground` in `sm-color-ink`, `-ink-2` or `-ink-3`. Coloured text uses `sm-safety-*-ink` only, at 30 px bold or larger.
- A safety fill always takes its `sm-safety-on-*` text: black on orange and yellow, white on red, green and blue in Day and Sunlight, near-black on every hue at Night.
- Safety glyphs are keylined in `sm-color-ink`. Yellow and orange do not reach 3:1 on light surfaces by themselves.
- The 45° hatch (`sm-safety-danger` + `sm-safety-hatch`) is used only for a person inside the swing radius.
- Idle categories and time-split segments are never safety hues. They are slate/stone lightness steps with a pattern.
- Night: never fill more than a banner-sized area with a hue. P1 at Night keeps the red frame and drops the red fill.

### Tokens by theme

| Token | Day | Sunlight | Night | Usage |
| --- | --- | --- | --- | --- |
| `sm-color-ground` | `#E2E1DC` | `#FFFFFF` | `#0B0B0A` | Cab and console background: the concrete everything sits on. Never used behind body text at rest; panels sit on it. |
| `sm-color-surface` | `#F4F3F0` | `#FFFFFF` | `#11100E` | Instrument face: panels, task rows, sheets. Primary text (sm-color-ink) and secondary text (sm-color-ink-2) are measured on this. |
| `sm-color-surface-sunk` | `#D5D4CE` | `#EDEDED` | `#070706` | Wells and tracks: the empty part of range bars, progress tracks, input wells. Never carries text smaller than 26px. |
| `sm-color-rail` | `#1C1B19` | `#FFFFFF` | `#070706` | Status rail background (the instrument cluster band). Dark in Day and Night, white in Sunlight where dark panels mirror the sky. |
| `sm-color-on-rail` | `#F4F3F0` | `#000000` | `#C4BBA8` | Text and glyphs on sm-color-rail. |
| `sm-color-rail-rule` | `#3A3935` | `#000000` | `#2E2C28` | Segment dividers inside the status rail. |
| `sm-color-ink` | `#151514` | `#000000` | `#C4BBA8` | Primary text and structural glyphs on sm-color-surface and sm-color-ground. Night value is deliberately dim (≈45% luminance of white) to protect dark adaptation. |
| `sm-color-ink-2` | `#46443F` | `#000000` | `#958D7E` | Secondary text (reasons, meta, units) on sm-color-surface. Sunlight collapses it to black: no grey text in sun. |
| `sm-color-ink-3` | `#5A5751` | `#1A1A1A` | `#8A8374` | Tertiary text (timestamps, source lines) in Paused mode and on the console only; never in Working mode. On sm-color-surface. |
| `sm-color-line` | `#151514` | `#000000` | `#6E685C` | Structural rules and control borders (2px Day/Night, 3px Sunlight). Meets 3:1 on surface and ground. |
| `sm-color-line-soft` | `#A9A7A0` | `#000000` | `#2E2C28` | Dividers inside a panel that carry no meaning. Sunlight maps it to black: there are no faint lines in sun. |
| `sm-color-action` | `#1C1B19` | `#000000` | `#2A2825` | Primary action fill (graphite). ShiftMate has no brand hue: the primary action is a solid graphite slab in Day/Sunlight, a raised dark slab with a lit border in Night. |
| `sm-color-on-action` | `#F4F3F0` | `#FFFFFF` | `#D8CFBC` | Label and glyph on sm-color-action. |
| `sm-color-action-pressed` | `#000000` | `#333333` | `#3A3834` | Pressed state of sm-color-action (shown for the whole press; there is no hover). |
| `sm-color-action-border` | `#1C1B19` | `#000000` | `#8A8374` | Border of primary and secondary actions. In Night the lit border, not the fill, carries the shape. |
| `sm-color-chalk` | `#F4F3F0` | `#FFFFFF` | `#1A1916` | The brand second colour: chalk. Used for the inner gap of the focus ring and for chalk-line marks on the map. |
| `sm-color-focus` | `#1C1B19` | `#000000` | `#D8CFBC` | Focus ring (4px solid, outside a 3px sm-color-chalk gap). Visible on every surface and on sm-color-action. |
| `sm-color-selected` | `#1C1B19` | `#000000` | `#3A3834` | Current tab / selected option fill (inversion, not a hue). |
| `sm-color-on-selected` | `#F4F3F0` | `#FFFFFF` | `#E0D6C2` | Text on sm-color-selected. |
| `sm-color-disabled` | `#B9B7B0` | `#8C8C8C` | `#2E2C28` | Disabled control fill/border. Disabled controls also lose their glyph and gain the word "Not now". |
| `sm-color-on-disabled` | `#4A4843` | `#000000` | `#8A8374` | Text on sm-color-disabled. |
| `sm-color-scrim` | `rgba(21,21,20,0.72)` | `rgba(0,0,0,0.80)` | `rgba(0,0,0,0.78)` | Backdrop behind the P1 takeover and the transcript sheet. Opaque enough that nothing beneath competes; no blur. |
| `sm-color-mark` | `#6B6760` | `#000000` | `#6E685C` | Non-text marks with meaning: bar outlines, range whiskers, map linework. ≥3:1 on surface. |
| `sm-safety-danger` | `#B8122B` | `#A50018` | `#DE4B43` | DANGER / stop. Fills: P1 takeover band, critical proximity ring, red risk lamp. Always paired with the octagon glyph or hatch. |
| `sm-safety-on-danger` | `#FFFFFF` | `#FFFFFF` | `#0B0B0A` | Text and glyphs on a sm-safety-danger fill. |
| `sm-safety-danger-ink` | `#A31025` | `#8E0016` | `#E0625B` | Danger as text (≥30px, bold) on sm-color-surface. |
| `sm-safety-danger-tint` | `#F6D9DC` | `#FFFFFF` | `#2A0F0D` | Ground behind danger text in banners; ink on it is sm-color-ink. |
| `sm-safety-warning` | `#F37A1C` | `#F7811F` | `#E0893D` | WARNING / slow down. P2 banner fill, "danger" proximity band. Always paired with the triangle glyph. |
| `sm-safety-on-warning` | `#151514` | `#000000` | `#0B0B0A` | Text on a sm-safety-warning fill (black on orange, as ANSI WARNING signs). |
| `sm-safety-warning-ink` | `#9A3A06` | `#853000` | `#E89A55` | Warning as text (≥30px, bold) on sm-color-surface. |
| `sm-safety-caution` | `#F6B71A` | `#FFC400` | `#D9BC4E` | CAUTION / take care. P3 strip, amber risk lamp, caution proximity band. Paired with the diamond glyph. |
| `sm-safety-on-caution` | `#151514` | `#000000` | `#0B0B0A` | Text on a sm-safety-caution fill. |
| `sm-safety-caution-ink` | `#6E5000` | `#5C4300` | `#DDC266` | Caution as text on sm-color-surface (rare: prefer ink beside a caution glyph). |
| `sm-safety-safe` | `#00773A` | `#006633` | `#4FA56E` | SAFE CONDITION. Green risk lamp, clear proximity band, completed check. Paired with the circle-tick glyph. |
| `sm-safety-on-safe` | `#FFFFFF` | `#FFFFFF` | `#0B0B0A` | Text on a sm-safety-safe fill. |
| `sm-safety-safe-ink` | `#006430` | `#005C2E` | `#62B380` | Safe as text on sm-color-surface. |
| `sm-safety-info` | `#0B5CAD` | `#00489A` | `#7496C4` | INFORMATION / mandatory action. P4 feed marker, "do this now" instruction pictograms. Paired with the square glyph. Night value is desaturated to cut blue light. |
| `sm-safety-on-info` | `#FFFFFF` | `#FFFFFF` | `#0B0B0A` | Text on a sm-safety-info fill. |
| `sm-safety-info-ink` | `#0A4F96` | `#003F87` | `#86A5CF` | Information as text on sm-color-surface. |
| `sm-safety-hatch` | `#F4F3F0` | `#FFFFFF` | `#0B0B0A` | The second stripe of the 45° critical hatch (with sm-safety-danger). Diagonal hatch is reserved for real hazards. |
| `sm-safety-risk-green` | `{sm-safety-safe}` | `{sm-safety-safe}` | `{sm-safety-safe}` | Live risk band: low. Bottom lamp of the stack light. |
| `sm-safety-risk-amber` | `{sm-safety-caution}` | `{sm-safety-caution}` | `{sm-safety-caution}` | Live risk band: elevated. Middle lamp. |
| `sm-safety-risk-red` | `{sm-safety-danger}` | `{sm-safety-danger}` | `{sm-safety-danger}` | Live risk band: high. Top lamp. |
| `sm-safety-prox-clear` | `{sm-safety-safe}` | `{sm-safety-safe}` | `{sm-safety-safe}` | Proximity tier clear: nobody inside the outer ring. |
| `sm-safety-prox-caution` | `{sm-safety-caution}` | `{sm-safety-caution}` | `{sm-safety-caution}` | Proximity tier caution: person in the outer (2× reach) ring. |
| `sm-safety-prox-danger` | `{sm-safety-warning}` | `{sm-safety-warning}` | `{sm-safety-warning}` | Proximity tier "danger": person inside reach + 2 m. Warning semantics (orange): slow, stop swinging that way. |
| `sm-safety-prox-critical` | `{sm-safety-danger}` | `{sm-safety-danger}` | `{sm-safety-danger}` | Proximity tier critical: person inside the swing radius. Stop semantics (red) + hatch + P1. |
| `sm-safety-alert-p1` | `{sm-safety-danger}` | `{sm-safety-danger}` | `{sm-safety-danger}` | P1 critical takeover. |
| `sm-safety-alert-p2` | `{sm-safety-warning}` | `{sm-safety-warning}` | `{sm-safety-warning}` | P2 urgent banner. |
| `sm-safety-alert-p3` | `{sm-safety-caution}` | `{sm-safety-caution}` | `{sm-safety-caution}` | P3 advisory strip. |
| `sm-safety-alert-p4` | `{sm-safety-info}` | `{sm-safety-info}` | `{sm-safety-info}` | P4 quiet feed marker. |
| `sm-safety-time-working` | `#1C1B19` | `#000000` | `#B5AC99` | Time-split: working (solid, darkest in Day). Not a safety meaning; lives here so it is never re-coloured green. |
| `sm-safety-idle-waiting` | `#3F4B57` | `#1F2A36` | `#7F8C98` | Idle reason: waiting for truck (external). Solid slate. |
| `sm-safety-idle-warmup` | `#7B8793` | `#56606B` | `#5F6A75` | Idle reason: warm-up / cool-down (machine needs it). Slate + vertical ticks. |
| `sm-safety-idle-break` | `#B7B2A7` | `#9A958A` | `#4A4740` | Idle reason: break. Stone, solid. |
| `sm-safety-idle-unattended` | `#5C5850` | `#3A3730` | `#6E695F` | Idle reason: engine running, cab empty. Basalt + dots. |
| `sm-safety-idle-habit` | `#948F84` | `#6E6A60` | `#57534B` | Idle reason: habit / short stops. Grey + horizontal lines. |
| `sm-safety-idle-unknown` | `#F4F3F0` | `#FFFFFF` | `#11100E` | Idle reason: unknown. Surface with a dashed sm-color-mark outline; honesty over guessing. |
| `sm-safety-time-off` | `#D5D4CE` | `#EDEDED` | `#1A1916` | Time-split: engine off. Track colour. |

### Contrast of every text/background pair used

Computed with the WCAG 2 relative-luminance formula (`check.py`). Targets: Day and Night text ≥ 4.5:1 (primary ≥ 7:1); Sunlight text ≥ 7:1; non-text marks ≥ 3:1.

| Pair | Foreground on background | Day | Sunlight | Night |
| --- | --- | --- | --- | --- |
| Primary text | `sm-color-ink` on `sm-color-surface` | 16.47 | 21.00 | 9.98 |
| Primary text on ground | `sm-color-ink` on `sm-color-ground` | 13.95 | 21.00 | 10.33 |
| Secondary text | `sm-color-ink-2` on `sm-color-surface` | 8.77 | 21.00 | 5.79 |
| Tertiary text (Paused/console) | `sm-color-ink-3` on `sm-color-surface` | 6.49 | 17.40 | 5.05 |
| Status rail text | `sm-color-on-rail` on `sm-color-rail` | 15.51 | 21.00 | 10.58 |
| Primary action label | `sm-color-on-action` on `sm-color-action` | 15.51 | 21.00 | 9.50 |
| Selected tab label | `sm-color-on-selected` on `sm-color-selected` | 15.51 | 21.00 | 8.11 |
| Disabled label (exempt; still ≥3) | `sm-color-on-disabled` on `sm-color-disabled` | 4.55 | 6.25 | 3.70 |
| Text in wells | `sm-color-ink` on `sm-color-surface-sunk` | 12.30 | 17.94 | 10.58 |
| Text on danger fill | `sm-safety-on-danger` on `sm-safety-danger` | 6.65 | 8.04 | 4.87 |
| Text on warning fill | `sm-safety-on-warning` on `sm-safety-warning` | 6.62 | 8.11 | 7.33 |
| Text on caution fill | `sm-safety-on-caution` on `sm-safety-caution` | 10.19 | 13.15 | 10.55 |
| Text on safe fill | `sm-safety-on-safe` on `sm-safety-safe` | 5.68 | 7.12 | 6.51 |
| Text on info fill | `sm-safety-on-info` on `sm-safety-info` | 6.67 | 8.77 | 6.47 |
| Text on danger tint | `sm-color-ink` on `sm-safety-danger-tint` | 13.82 | 21.00 | 9.40 |
| Danger text | `sm-safety-danger-ink` on `sm-color-surface` | 7.12 | 9.71 | 5.49 |
| Warning text | `sm-safety-warning-ink` on `sm-color-surface` | 6.35 | 8.68 | 8.32 |
| Caution text | `sm-safety-caution-ink` on `sm-color-surface` | 6.73 | 9.30 | 10.85 |
| Safe text | `sm-safety-safe-ink` on `sm-color-surface` | 6.60 | 8.17 | 7.50 |
| Info text | `sm-safety-info-ink` on `sm-color-surface` | 7.36 | 10.19 | 7.51 |
| Focus ring on surface (non-text) | `sm-color-focus` on `sm-color-surface` | 15.51 | 21.00 | 12.29 |
| Focus ring on ground (non-text) | `sm-color-focus` on `sm-color-ground` | 13.14 | 21.00 | 12.73 |
| Control border (non-text) | `sm-color-line` on `sm-color-surface` | 16.47 | 21.00 | 3.44 |
| Data marks (non-text) | `sm-color-mark` on `sm-color-surface` | 5.07 | 21.00 | 3.44 |
| Action outline on ground (non-text) | `sm-color-action-border` on `sm-color-ground` | 13.14 | 21.00 | 5.23 |
| Danger fill vs surface (non-text) | `sm-safety-danger` on `sm-color-surface` | 5.99 | 8.04 | 4.70 |
| Idle: waiting segment | `sm-safety-idle-waiting` on `sm-color-surface` | 8.03 | 14.56 | 5.53 |
| Idle: warm-up segment (+ticks) | `sm-safety-idle-warmup` on `sm-color-surface` | 3.30 | 6.40 | 3.45 |
| Idle: unattended segment | `sm-safety-idle-unattended` on `sm-color-surface` | 6.38 | 11.87 | 3.49 |
| Working segment | `sm-safety-time-working` on `sm-color-surface` | 15.51 | 21.00 | 8.44 |

Failing pairs: none. Note: the idle warm-up swatch is 3.3:1 in Day, 6.4:1 in Sunlight and 3.45:1 at Night; it always carries its tick pattern and a label, and it is never the only cue.

#### Hazard hues told apart without hue
The red/green pair differs by only 1.2:1 in lightness in Day, which is the same trap as the standard sign colours. ShiftMate never relies on that difference:
- **Risk**: stack-light *position* (red top, amber middle, green bottom) + word.
- **Alerts**: octagon (P1), triangle (P2), diamond (P3), square (P4) + words.
- **Proximity**: which *ring band* is occupied + hatch for critical + words and distance.
- **Safe**: a circle-tick glyph, never a plain green fill.


## 3. Typography

### Family: Anek (Ek Type), one superfamily in three scripts

Anek was designed in India as a multi-script family with a shared skeleton. It has flared, slightly stencil-like terminals that feel at home next to machine decals, and a **width axis (75–125)** that ShiftMate uses deliberately. Wide (125) is the decal voice for identifiers. Normal (100) is for all text. Slightly condensed (92) absorbs long Tamil labels. It is OFL-1.1 and self-hosts offline.

| Script | Fontsource package (variable) | Axes / weights used | Static fallback package |
| --- | --- | --- | --- |
| Latin | `@fontsource-variable/anek-latin` (import `wdth.css`, which carries wght + wdth) | wght 450, 500, 600, 700, 750, 800; wdth 92–125 | `@fontsource/anek-latin` 400, 500, 600, 700, 800 |
| Tamil | `@fontsource-variable/anek-tamil` (`wdth.css`) | same | `@fontsource/anek-tamil` 400, 500, 600, 700 |
| Devanagari | `@fontsource-variable/anek-devanagari` (`wdth.css`) | same | `@fontsource/anek-devanagari` 400, 500, 600, 700 |

Stack: `"Anek Latin", "Anek Tamil", "Anek Devanagari", "Noto Sans", system-ui, sans-serif`. Latin digits and punctuation in Tamil and Hindi strings come from Anek Latin, so figures look the same in all three languages. Verified: Anek Latin has the `tnum` (tabular figures) feature, and cap height is 0.639 em (1278/2000).

### Cab scale: sized for 80 cm, while vibrating

The reference density from the brief is 3.78 px/mm (68 px = 18 mm). At 80 cm, one arc-minute is 0.233 mm. The minimum for in-vehicle glance reading is about 20′ of character height (ISO 15008). The cab uses **≥ 26′ for anything shown while the machine moves** and ≥ 17′ only for Paused-mode metadata.

| Token | Size / line | Weight | Tracking | Cap height ≈ arc at 80 cm | Use |
| --- | --- | --- | --- | --- | --- |
| `sm-text-cab-hero` | 120 / 120 | 700 | −0.01em | 87′ | Critical numbers; tabular |
| `sm-text-cab-display` | 72 / 80 | 700 | −0.005em | 52′ | P1 headline |
| `sm-text-cab-title` | 48 / 56 (Working task line 56 / 64) | 600 | 0 | 35′ | Working task line, titles, P2 |
| `sm-text-cab-heading` | 36 / 44 | 600 | 0 | 26′ | Headings, P3 strip |
| `sm-text-cab-body` | 30 / 40 | 450 | 0 | 22′ | Sentences (Paused) |
| `sm-text-cab-label` | 28 / 34 | 600 | 0.005em | 20′ | Buttons, chips, tabs |
| `sm-text-cab-meta` | 24 / 32 | 500 | 0.005em | 17′ | Units, sources (Paused only) |
| `sm-text-cab-decal` | 28 / 32, **wdth 125** | 700 | 0.03em | — | IDs only: EXC001, LOAD-A, TRK-07 |

Sunlight adds **+100 weight** to every style (`--sm-text-weight-shift`). Night subtracts 50, because light-on-dark text blooms.

### Console scale (desk, 50–70 cm)

| Token | Size / line | Weight | Use |
| --- | --- | --- | --- |
| `sm-text-con-display` | 40 / 48 | 600 | One lead sentence or number per page |
| `sm-text-con-title` | 28 / 36 | 600 | Page and panel titles |
| `sm-text-con-heading` | 20 / 28 | 600 | Section heads |
| `sm-text-con-body` | 16 / 24 | 400 (500 in Sunlight) | Body |
| `sm-text-con-label` | 14 / 20 | 600 | Controls, table headers (sentence case) |
| `sm-text-con-meta` | 13 / 18 | 500 | Smallest text anywhere |
| `sm-text-con-num` | 28 / 32 | 600 | Tabular figures |

### Numerals
- `font-feature-settings: 'tnum' 1, 'lnum' 1` (`--sm-font-numeric`) wherever figures align or update: clock, ranges, counts, tables, distances.
- Durations are written "1 h 05 m" (with spaces, zero-padded minutes), times "10:42" (24 h), distances "2 m", temperatures "45 °C".
- "~" marks the most-likely value of a range; the range uses an en dash: "55 m – 1 h 25 m".

### Latin, Devanagari and Tamil rules

| | Latin | Devanagari (hi) | Tamil (ta) |
| --- | --- | --- | --- |
| Body line-height | 1.33 (30/40) | **1.53** (30/46) | **1.6** (30/48) |
| Title | 48/56 | 46/62 | 44/60 |
| P1 display | 72/80 | 64/88 | 60/84 |
| Max line length (cab body) | 40 characters | 34 aksharas | 28 characters |
| Max line length (console body) | 75 | 65 | 55 |
| Width axis | 100 | 100 | 100; chips and where-lines at 92 |
| Length budget vs English | 1× | ~1.2× | **1.3–1.5×** |

- **Wrap, don't truncate.** Titles may take two lines, then the layout drops a repeated detail. Never use an ellipsis on a safety string, an instruction or a reason.
- Truncation is allowed only for proper names in the console (machine or operator), with the full value in the detail panel.
- Never letter-space Devanagari or Tamil (tracking breaks the shirorekha and conjuncts). Tracking tokens apply to `:lang(en)` only.
- Tamil and Devanagari never go below 24 px in the cab. Where Latin uses 22 px (range lo–hi), Tamil uses 24 px and wraps.
- Mixed strings keep IDs and units in Latin: "18-ல் 7", "LOAD-A".
- Don't fake bold or italic. Anek has no italic; emphasis is weight.


## 4. Space, sizing and layout

### Spacing scale (4 px base)
`sm-space-1` 4 · `-2` 8 · `-3` 12 · `-4` 16 · `-5` 24 · `-6` 32 · `-7` 48 · `-8` 64 · `-9` 96.
The cab uses 16 px and up between elements. 4, 8 and 12 exist for glyph/label pairs and the console.

### Touch targets (glove sizes)

| Token | px | mm | Use |
| --- | --- | --- | --- |
| `sm-size-target-min` | 68 | 18 | Smallest control in the cab |
| `sm-size-target` | 88 | 23 | Standard button, row, tab |
| `sm-size-target-xl` | 120 | 32 | P1 acknowledge (132), drill STOP (140), Send report |
| `sm-size-ptt` | 136 | 36 | Push-to-talk disc |
| gap | ≥ 16 | ≥ 4 | Between any two targets |
| opposite actions | ≥ 64 or opposite sides | ≥ 17 | Send / Delete, OK / Problem are at least a full button apart |

No gestures are required: no swipe, long-press-only or pinch. Every scroll area also has buttons. A tap counts on release inside the target, with a 12 px slop allowance for vibration.

**Density calibration.** The layouts are specified at 3.78 px/mm (the brief's 68 px = 18 mm). On each device model, set `--sm-density` so that one reference px is 0.2646 mm. A 10.1" 1280 × 800 tablet (≈ 149 ppi) therefore renders at about 1.5× and falls back to the 1024 × 768 grid. The system never shrinks a target to fit a smaller screen.

### Cab grid: 1280 × 800 landscape

```
y   0 ┌───────────────────────────── status rail 96 (Working 176) ──────────────────────────────┐
   96 ├──48 margin──┬───────── content 1184 (12 cols × 76, gutters 24) ─────────┬──48 margin──┤
      │             │  P2 banner anchors here (under the rail)                   │             │
      │             │                                                            │  PTT safe   │
  688 ├─────────────┴───────────── P3 strip anchors above the nav ───────────────┴─ zone 360×72┤
      │  nav 112: 5 tabs (minmax 0,1fr) + 300 PTT cell; PTT disc 136, right 40, bottom 22       │
  800 └────────────────────────────────────────────────────────────────────────────────────────┘
```
- Paused content height is 592 px. Screens use 24–32 px side padding inside the content area where panels need the width, and never less.
- Common splits: 8 + 4 columns (task list | conditions panel, 400 px) or 7 + 5.
- **PTT safe zone**: 360 × 72 px directly above the nav at the right. Panels end 52 px above the nav on that side.
- **Alert layer**: P2 anchors at y = rail height, full width, min 136 px. P3 anchors at the bottom of the content area (Working: screen bottom), full width, with right padding 232 px to clear the PTT. P1 covers everything, rail included.

### Cab grid: 1024 × 768 landscape
- Rail 96 (Working 160). Nav 104: 5 tabs + a 220 px PTT cell; PTT disc 120 px (32 mm, never smaller).
- Content 928 wide (8 columns × 94, gutters 24), margins 48.
- My Shift: the conditions panel moves *below* the task list as a single row of three conditions. The task row's range column narrows to 240 px and the most-likely value stays 34 px.
- Rail: the machine segment is dropped (its ID moves into the Paused content header). The Reach, risk, belt and clock remain.

### Console grid: 1440 px and wider
- Top bar 64 (the rail's console twin). Main area padding 24, 12 columns, gutter 20.
- Live map: map 8–9 columns plus a 380 px detail panel. The map keeps a fixed metres-per-pixel scale and pans; it never squashes.
- Summary: 8 + 4 columns (wide analysis | safety). Fleet: 4-up site tiles, then full-width panels.
- ≥ 1920 px: side panels stay fixed width and the map or analysis column grows.
- Console controls are 40–44 px tall (desk mouse or touch), and at least 44 px wherever the console runs on a touchscreen in a site office.


## 5. Shape and elevation

### Radius by role

| Token | Value | Applies to | Why |
| --- | --- | --- | --- |
| `sm-radius-none` | 0 | P1, P2, P3, status rail, task-row stack, panels | Full-bleed layers and joined rows are structure, not objects |
| `sm-radius-chip` | 6 | Reason chips, source chips, number plates, keycaps, queue pip | Cut-plate corners, like a riveted tag |
| `sm-radius-control` | 10 | Buttons, toggles, segmented controls, PIN keys, slots | Enough to feel pressable in a glove |
| `sm-radius-bezel` | 20 | Instrument housings: Reach panel, camera frame, lesson player, drill frame, badge target | The only large radius. It says "instrument" |
| `sm-radius-disc` | full | Push-to-talk, stack-light lenses, map people | Circles are round |

### Borders
- `sm-border-rule` 2 px (Sunlight 3): structure and control outlines, in `sm-color-line`.
- `sm-border-heavy` 4 px (Sunlight 5): the active task, the selected option, instrument bezels, and the top edge of the transcript sheet.
- `sm-border-alert` 12 px: the P1 frame.
- `sm-border-dash` 3 px dashed: unknown, estimated and offline things (unknown idle, offline source chip, "No sensing" gauge, empty states).
- **Sunlight has no hairlines.** `sm-color-line-soft` maps to black there, and every divider is at least 2 px.

### Elevation and overlays
Nothing in the cab floats on a blur. Depth comes from a hard edge, an inversion or a scrim.

| Layer | `z` token | How it is separated |
| --- | --- | --- |
| Content | `sm-layer-base` 0 | Panels on `sm-color-ground`, 2 px rules |
| Status rail | `sm-layer-rail` 10 | Rail colour + 2 px bottom rule (5 px Sunlight) |
| P4 toast | `sm-layer-p4` 20 | Paused only; rule above |
| P3 strip | `sm-layer-p3` 30 | 3 px ink rules above and below |
| Transcript / answer sheet | `sm-layer-sheet` 40 | `sm-elev-sheet` (hard 3 px top edge) + `sm-color-scrim` over content, rail left visible |
| Push-to-talk | 45 | Chalk lens ring + action-border ring |
| P2 banner | `sm-layer-p2` 50 | `sm-elev-banner` hard 4 px drop edge |
| **P1 takeover** | `sm-layer-p1` 100 | Covers the whole screen, rail included; 12 px frame; no scrim needed because it is opaque |

The P1 takeover sits above everything, including the transcript sheet and the PTT disc. Voice is cancelled while a P1 is shown and resumes, with its draft kept, after the P1 is acknowledged.


## 6. Iconography

### Style
- 48-unit grid with 2 units of padding. Square caps, mitred joins, no rounded "friendly" terminals.
- **Plan view** (top-down) for anything that is a machine, the same view as the Reach and the site map. A machine is two tracks and a house square; the boom shows direction.
- Outline for things, fill for state: a filled house means working, an open house means idle, a dashed outline means off, unknown or not sensed.
- Stroke `--sm-icon-stroke`: **4 in Day and Night, 5 in Sunlight**. Strokes never scale with the glyph. The 44–48 px rail size and the 300 px P1 size use the same stroke weight.
- Glyphs use `currentColor`. The only coloured glyphs are the priority shapes and the safe tick, which are filled with the safety colour and keylined in ink.
- Sizes: 28–32 (in text and chips), 36–48 (rail, tabs, rows), 56–72 (buttons with glyphs, P2, empty states), 104–112 (P1 octagon), 160–300 (P1 cause).

### Custom glyph set (see the Glyphs card)

| Group | Glyphs | Notes |
| --- | --- | --- |
| Machine state | `machine-working`, `machine-idle`, `machine-travel`, `machine-off` | Working: filled house + extended boom. Idle: open house + pause bars. Travel: tracks filled + chevron ahead. Off: dashed + slash |
| Idle reason | `idle-waiting` (truck + empty bay dashes), `idle-warmup` (gauge needle low), `idle-break` (a steel tea tumbler), `idle-unattended` (empty seat + engine hum), `idle-habit` (loop), `idle-unknown` (dashed circle ?) | None of these point at a person |
| Proximity tier | Reach miniatures: clear, caution (dot in outer band), danger (dot in middle band), critical (hatched inner sector) | The same geometry as the Reach |
| Seatbelt | `belt-on` (strap + buckle across the torso), `belt-off` (strap loose, buckle hanging) | |
| Connectivity / sync | `net-online`, `net-offline`, `net-waiting`, `net-syncing`, `net-synced` | A site mast, not a phone signal, so it cannot be mistaken for machine signal strength |
| Sensor tier | `sensor-full` (3 filled), `sensor-basic` (1 filled, 2 open) | Always shown with words on basic machines |
| Priority | P1 octagon, P2 triangle, P3 diamond, P4 square, safe circle-tick | Shape = priority, independent of colour |
| Conditions | `heat`, `rain`, `wet-ground`, `dark`, `fatigue`, `clock` | Used in reason chips and risk contributions |

### Base set for generic UI
**Phosphor Icons, Bold weight**: `@phosphor-icons/react` v2 (MIT), `weight="bold"`, at the sizes above. Used only for generic actions: microphone, check, close, play/pause, replay, book, calendar, camera, document, pencil, speaker, download. Phosphor is never used unmodified for a machine state, idle reason, safety state or sync state; those are always ShiftMate glyphs. The previews draw matching generic glyphs inline so they work offline without the package.

### Accessibility
Every glyph that stands alone has `role="img"` and an `aria-label` that says the state in words ("Seatbelt unbuckled", "Offline, 3 items waiting"). Decorative glyphs next to a word are `aria-hidden`.


## 7. Motion

Motion only tells the operator that something changed state. Nothing enters with a fade-and-slide, nothing drifts, and there is no hover.

| Moment | Token | Duration / easing | What moves |
| --- | --- | --- | --- |
| Press | `sm-motion-press` | 80 ms, linear | Darker fill + 2 px down-shift for the press |
| P1 arrival | `sm-motion-p1-in` | **0 ms** | Appears instantly. Danger never animates in |
| P1 frame flash | `sm-motion-p1-flash` | 1000 ms period, `steps(1)` | Frame alternates red ↔ ink at 1 Hz until acknowledge (well below the 3 flashes/s seizure threshold) |
| Acknowledge | `sm-motion-ack` | 200 ms, `sm-motion-ease-exit` | P1 collapses into its rail segment, which then shows the tier glyph for 10 s |
| P2 arrival | `sm-motion-alert-in` | 160 ms, `sm-motion-ease` | Slides down from under the rail; no fade |
| P3 arrival | `sm-motion-alert-in` | 160 ms | Rises from the bottom edge |
| Mode change | `sm-motion-mode` | 320 ms, `sm-motion-ease` (back to Working: 160 ms exit, *after* the switch to Working mode) | Rail height, shared task-line element, panels rise 24 px |
| Voice listening | `sm-motion-listen` | 1200 ms loop | One ring expands from the PTT disc; the level meter follows the real input |
| Thinking | — | 3-step bar, 400 ms per step | Shows work, not a spinner |

Easing: `sm-motion-ease` = `cubic-bezier(0.2, 0, 0, 1)` (quick start, firm stop, like a hydraulic ram); `sm-motion-ease-exit` = `cubic-bezier(0.4, 0, 1, 1)`.

### Reduced motion (`prefers-reduced-motion` or the in-app setting)
- Arrivals, acknowledge and mode change become instant (0 ms).
- The listening ring is replaced by a steady thick ring plus the word "Listening…".
- The P1 frame stops flashing and becomes a steady 16 px frame. The P1 tone and haptic still pulse, because sound and vibration carry the urgency.

### Never
Parallax, skeleton shimmer, counting-up numbers, confetti on completed lessons, animated charts, or motion while the machine is moving other than alert arrival.


## 8. Sound and haptics

Cabs are loud: 75–85 dB(A) inside, with low-frequency engine and hydraulic noise below 500 Hz. Alert tones therefore sit between 1–3 kHz, where hearing is most sensitive and machine noise is thinnest. They are built from **pitch patterns**, not volume, so they stay distinct through ear defenders, and they play at least 10 dB above measured cab noise (the tablet samples ambient level every 5 s).

### P1: critical
- Pattern: **three rising pulses** (1,400 → 1,800 → 2,400 Hz), each 120 ms with 60 ms gaps, then 400 ms of silence. The 1.0 s cycle repeats until acknowledged.
- Timbre: square-ish wave with the 3rd harmonic, so it cuts through.
- After acknowledge: one falling pair (2,400 → 1,400 Hz, 150 ms each) confirms.
- If the condition persists after acknowledge: one pattern every 5 s.
- Haptic (seat or tablet mount, where fitted): 3 strong pulses per cycle, in time with the tone.
- The spoken line follows the first cycle, then the tone continues under the speech at −12 dB.

### P2: urgent
- Pattern: **two level pulses** at 1,600 Hz, 150 ms each with a 100 ms gap. Plays **once** on arrival and again after 20 s if the banner has not been seen.
- Haptic: 2 medium pulses.

### P3: advisory
No tone; one short 80 ms haptic tick. Optionally spoken in Paused mode only.

### P4: quiet
Silent.

### Voice UI sounds
Listening start: a single 880 Hz 40 ms tick. Error: a low double tick (440 Hz × 2). Answer ready: none; the answer is spoken.

### Spoken alerts
- **Order**: command first, then the where, then the what. "Stop. Person behind you, left side." Never start with the product name or "Warning:".
- **Length**: ≤ 6 words for P1, ≤ 10 for P2. One sentence.
- **Pace**: 150–160 words per minute in English (slightly slower than conversation), with a 300 ms pause after the command word. Tamil and Hindi lines are written short enough to take the same time, not translated word for word.
- **Voice**: calm, low-mid pitch, level intonation; the same voice for every priority. Urgency comes from the tone and the words, not from shouting.
- **Language**: the operator's chosen language. The P1 command word is also said in the site language when it differs ("Stop" / "நிறுத்து").
- **Repeat**: P1 repeats the spoken line once after 4 s if not acknowledged. P2 never repeats speech.
- Speech ducks for other speech: a P1 line cuts off an assistant answer mid-word, and the answer resumes from the start of its sentence afterwards.

| Priority | Example spoken line (en) |
| --- | --- |
| P1 | "Stop. Person behind you, left side." |
| P1 | "Stop. Seatbelt off." |
| P2 | "Person close on your left. Slow down." |
| P3 | "Water break at eleven." (Paused only) |


## 9. Data visualisation

Charts in ShiftMate are instruments: few, large, labelled in words, and built from tokens. There is no chart the operator has to decode while the machine is moving.

### Time-split bar
- **Anatomy**: 64–72 px bar, 4 px ink frame; segments in time order separated by 3 px surface gaps; axis labels at shift start, every 2 h and shift end (tabular, 22 px cab / 13 px console); a legend of swatch + name + duration, or row labels beside it.
- **Tokens**: `sm-safety-time-working` (solid ink); `sm-safety-idle-waiting` (solid slate); `-warmup` (vertical ticks); `-break` (light stone); `-unattended` (dots); `-habit` (horizontal lines); `-unknown` (surface + dashed `sm-color-mark` outline); `sm-safety-time-off` (track).
- **Rule**: no diagonal hatch (reserved), no safety hue.

### Estimate range bar
- **Anatomy**: most-likely value (34 px) → track (24 px, sunk, 2 px `sm-color-mark` outline) → band low–high (`sm-color-ink`) → most-likely tick (6 px, overshoots 10 px, surface halo) → "low – high" text.
- A shared 0–3 h scale on a screen, so rows compare. Low confidence is drawn as a dashed band with the sensor glyph note. Done time is a `sm-color-mark` fill from 0.

### Sparkline (console)
- 2.5 px `sm-color-ink` polyline on the panel surface, one baseline in `sm-color-line-soft`, no area fill, no dots. The last value and the peak are written as text beside it, never shown on hover only.
- In the cab, sparklines are not used. A trend is a sentence ("2 s faster than last week").

### Risk contributions
- **Anatomy**: rows of factor glyph + factor with its value ("Heat 45 °C") + share (bold tabular %) with a full-width 22 px bar underneath (sunk track, ink fill). Sorted by share. The stack light and the band word sit above the rows.
- The bars are ink, not safety hues: the contribution is an explanation, and the band is the only hazard signal.

### Proximity display
The Reach (see its card) and the camera overlay: the ground-plane arcs in the camera use the same three radii, projected (swing radius red 10 px solid, reach + 2 m orange 7 px, 2× reach yellow 6 px dashed), plus the tier tag on the detected person ("Caution · 7 m").

### Site map symbology (console)

| Element | Symbol | Tokens |
| --- | --- | --- |
| Grid | 50 m lines, heavier at 250 m | `sm-color-line-soft` |
| Haul road | 30 px band + dashed centreline | `sm-color-surface-sunk`, `sm-color-mark` |
| Zone | Dashed ink rectangle + decal label | `sm-color-ink` |
| Trench | 14 px line; dug part ink, planned part ink-2 | |
| Excavator / loader / dozer | Swing rings (2× reach dashed, reach + 2 m solid, swing radius heavy) + boom line + house square (filled working, open + bars idle, dashed off) + ID plate | `sm-color-mark`, `sm-color-ink`; selected = inverted plate + surface fill inside the swing radius |
| Person in a ring | Tier sector, as in the cab | `sm-safety-prox-*`, hatch for critical |
| Truck | Plan rectangle + cab block; open = waiting, filled = moving; ID beside | `sm-color-ink` |
| Worker tag | 5 px dot with a surface halo | `sm-color-ink` |
| North, scale | Arrow + 50 m bar | always visible |
| Legend | Bottom-left plate, 2 px frame | |

### General rules
- Every chart has a sentence that says what it shows, and a table alternative for screen readers.
- Axes start at zero. Durations use "h m", never decimals of hours.
- No 3D, no gradients, no donut charts, no dual axes.


## 10. Components

Each component has its own card with a live preview and full guidelines (anatomy, sizes, states, theme behaviour). This page holds the rules they all share.

### Shared states

| State | Rule |
| --- | --- |
| Default | Tokens only; colours from `sm-color-*`, meaning only from `sm-safety-*` |
| Pressed | For the whole press: darker or sunk fill, 2 px down-shift on buttons (`sm-motion-press`). There is no hover state anywhere |
| Focused | 4 px `sm-color-focus` ring outside a 3 px `sm-color-chalk` gap |
| Disabled | `sm-color-disabled` / `sm-color-on-disabled`, glyph removed. Prefer hiding the control, or saying why ("Available when parked") |
| Loading | The control keeps its size; a dashed progress line or a 3-step bar. No spinners in the cab |
| Error | Written in words next to the thing, with what still works. Never red for a system error; red means danger to a person |
| Offline | Dashed outline or tag on anything that depends on the network, and the action label changes ("Send when online") |
| Stale | Stale mark + age ("No update 40 s"). Stale proximity data escalates to P2 |

### Theme behaviour, all components
- **Sunlight**: borders +1 px, weights +100, glyph stroke 5, `line-soft` becomes black, rail white.
- **Night**: no field of safety colour larger than a banner: P1 keeps the frame and drops the fill; P2 and P3 become surface-coloured with a coloured 4–6 px border. The primary action is a dark slab with a lit border.

### Inventory
Cab frame: StatusRail, BottomNav, ModeTransition, PushToTalk, TranscriptSheet.
Alerts: AlertTakeoverP1, AlertBannerP2, AlertStripP3, AlertFeedP4, AlertQueue.
Tasks: TaskRow, RangeBar, ReasonChip, ConditionsSummary, RiskIndicator. Safety: ProximityPanel, Reach.
Controls: Button, LargeToggle, SegmentedControl, PinPadAndBadge, ChecklistItem. Report: ReportDraftCard.
Insights: TimeSplit, IdleSegmentRow, CoachingNote. Learn: LessonCard, NarratedCardPlayer, QuizOption, DrillFrame, BookingSlot, ProgressView.
Voice: AssistantAnswer. States: SystemStates, SyncStates. Iconography: Glyphs.
Console: ConsoleSiteMap, MachineDetailPanel, IdleCausesBreakdown, SafetyOverview, FleetTiles, DemoControlBar.


### Reach

The Reach is ShiftMate's one signature element: a plan-view gauge of the machine's own working envelope — swing radius, reach + 2 m, and 2× reach — drawn the way operators already think about space.

#### Anatomy
- **Bezel ticks** every 30° (heavier at 0/90/180/270), like a gauge face. Omitted below 120 px.
- **Caution ring** (2× reach): dashed like a string line, `sm-color-mark`.
- **Danger ring** (reach + 2 m): solid `sm-color-mark`.
- **Swing-radius ring**: heavy `sm-color-ink`. This is the line that matters most, so it is the heaviest.
- **Boom** shows the current swing direction; the house square rotates with it. Tracks (≥ 200 px only) stay fixed, as the undercarriage does.
- **Occupied sector**: a 56° annular sector in the tier's band, filled with `sm-safety-prox-caution` / `sm-safety-prox-danger`, or the 45° critical hatch (`sm-safety-danger` + `sm-safety-hatch`). Outlined in ink so yellow and orange hold 3:1 on light surfaces.
- **Person marker**: ink disc with a surface ring, placed mid-band at the detected bearing.

#### Sizes
| Where | Size | Ticks | Tracks |
| --- | --- | --- | --- |
| Status rail, Paused | 84 px | no | no |
| Status rail, Working | 148 px | yes | no |
| Safety Guard proximity panel | 230 px | yes | yes |
| P1 takeover | 460 px | yes | yes |
| Console map | ring geometry only, scaled to metres | no | no |

#### Rules
- Bearing 0° is the boom's forward direction at rest; bearings run clockwise. Behind the operator is 180°.
- Never draw the hatch unless someone is inside the swing radius. The hatch *is* the critical signal.
- The Reach never appears as decoration — not on empty states, not on the cover of lessons, not as a progress ring.
- Always paired with a word ("Clear", "1 near", "Stop") and, for tiers above clear, the tier glyph.
- Machines with basic sensors show the dashed "no sensing" Reach with a slash; never an empty (clear-looking) Reach.

#### Consumer provides
`bearing` (deg), `tier` (`clear | caution | danger | critical`), `boomAngle` (deg), `size`, `label` (spoken/aria text).


### StatusRail

The status rail is the always-visible instrument band: proximity, risk, seatbelt, machine, sync and time — the only thing on screen that never moves.

#### Anatomy (left → right)
1. **Reach segment** on `sm-color-surface` (the only light segment in Day, so the proximity picture reads first): Reach gauge + word (+ `safe_tick` when clear).
2. **Risk**: stack light (3 lamps; the lit lamp's *position* carries the level) + word + main reason.
3. **Seatbelt**: glyph + word.
4. **Machine** (Paused only): state glyph + ID decal + state word.
5. Flexible gap.
6. **Queue pip** (only when alerts are queued): priority glyph + count.
7. **Sync**: glyph; words only when something needs attention (offline, items waiting).
8. **Clock**, tabular figures.

#### Sizes
| Mode | Height | Label | Clock | Reach |
| --- | --- | --- | --- | --- |
| Paused | `sm-size-rail-paused` 96 px | 28 px | 40 px | 84 px |
| Working | `sm-size-rail-working` 176 px | 40 px | 56 px | 148 px |

#### Colour and theme
- Day: `sm-color-rail` graphite band, `sm-color-on-rail` text. Night: near-black band, dimmed ink. Sunlight: **white** band with a 5 px black bottom rule — dark panels mirror the sky in direct sun.
- Segment dividers: `sm-color-rail-rule`.

#### States
Default · alert-linked (the segment that raised a P1/P2 shows the tier glyph beside its word) · offline (sync shows words) · stale (a segment whose data is older than 30 s shows the stale mark and "No update 40 s") · basic sensors (Reach replaced by the "No sensing" gauge).

#### Rules
- The rail is never covered, except by a P1 takeover.
- Tamil/Hindi: labels wrap to two lines at 24 px; the calm "Synced" state is glyph-only in every language.
- Not interactive in Working mode. In Paused mode, tapping a segment opens its screen (Reach/Risk → Safety Guard).


### ModeTransition

Working mode shows only the rail, one task line and alerts; Paused mode (machine idle ≥ 30 s) shows the full interface. The change is one continuous move, never a page swap.

#### Trigger
- **To Paused**: engine on, no travel, no hydraulic demand, no swing for 30 s (debounced; a 2 s joystick nudge does not count as moving).
- **To Working**: any travel or implement movement, *immediately* (0 ms delay). Safety beats continuity.

#### Motion (`sm-motion-mode` 320 ms, `sm-motion-ease`)
1. Rail height 176 → 96 px; rail labels step down 40 → 28 px (no scaling of glyph strokes).
2. The task line slides up into the first task row's position (shared element).
3. Content panels and the nav bar rise 24 px into place; no fade.
4. Push-to-talk does not move: it is in the same place in both modes.
Going back to Working, content drops out in 160 ms (`sm-motion-ease-exit`) and the rail grows. Reduced motion: instant swap.

#### Rules
- Never interrupt an operator mid-tap: if a finger is down when movement starts, finish the press, then switch.
- An open transcript sheet stays open across the change; any other sheet closes.
- A P2/P3 alert survives the change and re-anchors (P2 under the rail, P3 above the nav or screen bottom).


### BottomNav

Five sections plus the push-to-talk cell, shown only in Paused mode.

- Height `sm-size-nav` 112 px; five equal tabs (`minmax(0,1fr)`), a 300 px push-to-talk cell.
- Tab: glyph 44 px over a 26 px label (24 px, two lines allowed, in Tamil/Hindi). Whole tab is the target (≈ 196 × 112 px).
- Current tab: inversion (`sm-color-selected` / `sm-color-on-selected`), never a colour.
- Pressed: `sm-color-surface-sunk` for the press. No hover.
- Labels: "My shift", "Safety", "Report", "My day", "Learn". Ask Cat lives behind push-to-talk, not in a tab.


### PushToTalk

The push-to-talk disc is reachable from every cab screen, in the same place in both modes: bottom-right, 136 px (36 mm), partly rising out of the nav bar.

#### Anatomy
Graphite disc (`sm-color-action`), 6 px chalk lens ring (`sm-color-chalk`), outer ring in `sm-color-action-border`, mic glyph 60 px. A second ring (`sm-ptt__ring`) expands once per `sm-motion-listen` (1.2 s) while listening.

#### Behaviour
- **Hold** to talk, release to finish. A single tap starts a 6 s listening window (for gloves that cannot hold) and shows "Tap again to stop".
- It routes by intent: "report…" → Quick Report draft; a question → Ask Cat; "call supervisor" → call sheet.
- Every voice action has a big-button equivalent on its screen.

#### States
| State | Visual | Words (label + transcript sheet) | Sound |
| --- | --- | --- | --- |
| Idle | graphite disc | "Hold to talk" | — |
| Listening | pressed fill + expanding ring + live level meter | "Listening…" + live transcript | one short 880 Hz tick on start |
| Transcribing | ring stops; meter freezes | "Writing it down" | — |
| Thinking | three-step bar in the sheet | "Checking the manual" | — |
| Answered | disc returns to idle | answer sheet opens, read aloud | — |
| Error | disc idle; sheet shows message | "Didn't catch that. Try again, or use the buttons below." | low double tick |
| Offline | idle disc; sheet shows the offline label | "Offline answer" | — |
| Disabled (P1 active) | hidden behind the takeover | — | — |

#### Rules
- Never place any other control within 32 px of the disc (the *PTT safe zone*: 360 × 72 px above the nav on the right).
- The disc does not move, resize or change colour for alerts.


### TranscriptSheet

The sheet that rises from the bottom while push-to-talk is active, showing what ShiftMate hears in real time.

- Full width, from the bottom; `sm-elev-sheet` hard top edge, 4 px rule; content clear of the PTT safe zone (right padding 240 px). Behind it: `sm-color-scrim` over content only — the rail stays visible.
- **State line**: glyph + state word (26 px bold) and a level meter (13 bars, `sm-color-ink`) that proves the mic is hearing.
- **Live transcript** 40/52 px. Words not yet final are shown in `sm-color-ink-2` with a dashed underline (`mark`); they become ink when final.
- **Helper line** 24 px: what happens next ("Nothing is sent until you check it").
- Tamil and Hindi transcripts use the script line-heights (1.6 / 1.53) and wrap; maximum 4 lines visible, older lines scroll up.
- Error: the transcript area is replaced by "Didn't catch that. Try again, or use the buttons below." — never a red state.


### AlertTakeoverP1

The P1 critical takeover: full screen, above everything, one action. Used only for an immediate danger to a person — someone inside the swing radius, seatbelt off while moving, rollover warning.

#### Anatomy
- **Frame**: `sm-border-alert` (12 px) in `sm-safety-alert-p1`, flashing to ink at 1 Hz (`sm-motion-p1-flash`, steps) until acknowledged. Night keeps the frame and drops any red fill.
- **Hatch band** (32 px, 45°, danger + hatch) across the top of the message column.
- **Left**: the cause, drawn big — the Reach at 460 px with the hatched sector, or the seatbelt glyph at 300 px.
- **Right**: octagon (104 px) + one-word command ("Stop."), the situation (72/80), the instruction (40/50), the where (32/40, with distance in tabular figures).
- **Acknowledge**: one xl primary button (132 px tall, full column width): "I've stopped". There is no dismiss.
- **Queue line**: "1 more alert after this", with the queued alert's priority glyph.

#### Behaviour
- Appears in **0 ms**. It never animates in. P1 tone + haptic start with it (see Sound).
- Pre-empts everything: an open P2 banner is pushed into the queue; the transcript sheet is cancelled (draft kept).
- **Acknowledge** means "I have done the action", not "go away". If the condition is still true 3 s after acknowledge, the takeover returns as a reduced P1 (frame + rail segment + tone every 5 s) until it clears.
- Seatbelt P1 clears by itself when the belt latches.
- Collapses into its rail segment on clear (`sm-motion-ack` 200 ms).

#### Layer
`sm-layer-p1` (100) — above `sm-layer-p2` (50), the transcript sheet (40) and the push-to-talk disc (45).


### AlertBannerP2

The P2 urgent banner drops from under the rail and stays until the condition clears or the operator taps **Seen**. Used for "slow down / take care now": a person inside reach + 2 m, a truck reversing into the swing path, overheating.

- Full width, min 136 px, `sm-safety-alert-p2` fill with `sm-safety-on-warning` (black) text — the way ANSI WARNING signs are printed. Triangle glyph 84 px. 4 px ink bottom edge + `sm-elev-banner`.
- Text: situation 44/52 bold, detail 28/34. One action, "Seen", 200 px min width, drawn inverted on the orange.
- Arrives with `sm-motion-alert-in` (160 ms slide from under the rail, no fade); P2 tone once.
- Content below remains visible and usable: P2 does not block the task line.
- Night: surface-coloured banner with a 6 px orange border (no large orange field at night).
- If a P1 arrives, the banner is queued and returns after the P1 clears (if still true).


### AlertStripP3

The P3 advisory strip: one line along the bottom of the screen (above the nav in Paused mode; at the screen bottom in Working mode, clear of push-to-talk).

- Min 84 px, `sm-safety-alert-p3` fill, ink text 32/38 semibold, diamond glyph 52 px, 3 px ink rules top and bottom.
- One optional action ("Later" snoozes 10 min; "Done" clears). No sound, one short haptic.
- Used for advice with time to act: water break due, fatigue (> 4 h without a break), light fading, rain starting.
- Night: surface strip with a 4 px caution-yellow border.
- Only one strip at a time; a newer P3 replaces the older one, which moves to the P4 feed.


### AlertFeedP4

The P4 quiet feed: information that can wait until the machine is paused. Never interrupts, never makes a sound.

- Row: square info glyph (36 px) + title 26/34 + meta 22/28 in `sm-color-ink-3`. Unread shows a 12 px `sm-safety-info` square after the title.
- Lives on My Shift (Paused) as "Updates"; P3 strips that were replaced also land here.
- In Working mode, P4 items are held; the count appears only when Paused.


### AlertQueue

One interrupting alert at a time. This is the arbitration rule every alert component follows.

1. Priority order: **P1 > P2 > P3 > P4**. Within a priority, the newest wins, except that a proximity alert always beats a non-proximity alert of the same priority.
2. A higher alert **pre-empts** a lower one immediately. The lower one goes to the queue (if still true when its turn comes, it returns; otherwise it is dropped to the P4 feed as history).
3. A lower alert never interrupts a higher one; it waits in the queue.
4. The queue is shown as a **pip in the status rail**: the glyph of the highest queued priority + the count ("+1"). The P1 takeover also says "1 more alert after this".
5. Nothing queues behind a P1 for more than 30 s without being re-evaluated.
6. Spoken alerts follow the same order; a P1 voice line cuts off any other speech mid-word.


### TaskRow

A task in My Shift: what, where, how far along, how long it will likely take, and why.

#### Anatomy
`[number plate 56] [title · where-line · reason chips] [range bar 280]`
- **Number plate**: 56 px square, radius-chip. Active = graphite fill; done = sunk.
- **Title** 30/38 semibold; the active row carries a "Now" plate.
- **Where-line** 24/30 `sm-color-ink-2`: quantity · zone decal (`LOAD-A`, wdth 125) · progress words.
- **Reason chips** (see ReasonChip): the reasons that move the estimate.
- **Range bar** (see RangeBar).

#### Sizes and states
Min height 88 px; typical 176 px. Rows are joined (shared 2 px rules), not floating cards. Active: 4 px ink frame. Done: title in ink-2, range replaced by actual time. Offline: unchanged (estimates are computed on the tablet). Stale estimate (> 10 min): "Estimate from 10:20" stale mark under the range. Pressed: sunk fill; opens the task detail.

#### Tamil and Hindi
Titles wrap to two lines rather than truncate; the where-line and chips use `wdth 92`. If a row still overflows, drop the where-line's quantity (it is repeated in the detail) — never the reasons.


### RangeBar

The honest estimate: a range with a most-likely value, never a single promised number.

#### Anatomy
- **Most likely** first, big (34/40 bold, tabular), prefixed "~".
- **Track**: 24 px, `sm-color-surface-sunk` with a 2 px `sm-color-mark` outline; the shared scale is 0–3 h across all rows on a screen, so bars compare.
- **Band**: low→high in solid `sm-color-ink`.
- **Most-likely tick**: 6 px ink bar extending 10 px beyond the track, with a surface halo so it reads on the band.
- **Low–high** text under the track (22/28, ink-2).
- **Done part** (optional): `sm-color-mark` fill from 0 to elapsed.

#### Confidence
- Normal: solid band.
- Low (basic-sensor machines, fewer than 3 similar days): band drawn as dashes and a note with the sensor glyph: "Estimated from limited data". The range is wider; it is never narrowed to look confident.
- Unknown: no bar; the words "Not enough data yet".

#### Screen reader
"Likely 1 hour 5 minutes, between 55 minutes and 1 hour 25 minutes."


### ReasonChip

A small plate that says why something takes the time it does: a glyph, a plain reason and, where it applies, the effect ("+20–40 min").

- 48 px min height, radius-chip (6 px, cut-plate corners), 2 px ink border, 24 px semibold; the effect in bold tabular figures.
- Not a button in the task list (tapping the row opens detail). Where a chip *is* interactive (task detail), it grows to 68 px.
- Variant `adds`: sunk fill, used when the chip explains extra time in a summary.
- Reasons use condition glyphs (heat, wet ground, rain, dark, fatigue) or idle-reason glyphs — never safety shapes. A reason is not a warning.
- Tamil: chips run at `wdth 92` and may wrap inside the chip; never ellipsis.


### ConditionsSummary

The right-hand panel on My Shift: when the day will likely end and the conditions that shape it.

- Header: "Likely finish" + a 48 px tabular range (never a single time) + one sentence on what could move it.
- Up to 3 condition rows (glyph 44, label 28, value 28 bold tabular, nowrap). Show only conditions that currently affect the estimate or the risk; hide the rest (daylight is hidden until 2 h before dark).
- Ends with the risk sentence and stack light when risk is raised or high.


### RiskIndicator

The live risk level as a **stack light**: three lamps in a column, red on top, amber in the middle, green at the bottom — the same order as a jobsite tower light. Only the current lamp is lit.

- Colour is backed by **position** (top/middle/bottom) and by the **word** beside it ("Risk low / raised / high") and the main reason.
- Rail: 34 × 74 px (Working 48 × 112). On surfaces: `sm-stack--onsurface` (ink housing).
- Tokens: `sm-safety-risk-green`, `sm-safety-risk-amber`, `sm-safety-risk-red` (aliases of safe / caution / danger).
- Risk is computed from heat, rain, darkness and fatigue; see the risk-contributions chart for the why. A change of band raises a P3 (to raised) or P2 (to high) once, then lives quietly in the rail.


### ProximityPanel

Camera view + Reach, side by side: the camera shows *who*, the Reach shows *where relative to the swing*.

- **Camera frame**: 4 px ink border, radius 12 (inside the bezel's 20). Ground-plane arcs are overlaid in perspective: swing radius (solid danger red, 10 px), reach + 2 m (warning, 7 px), 2× reach (caution, dashed). They are projected from the same ring geometry as the Reach.
- **Detected person**: box in the tier colour with a black keyline, and a tag plate ("Caution · 7 m") in the tier fill with its `on-` text colour.
- **Reach**: 230 px with tracks; tier glyph + count + distance below.
- **One sentence** under both saying what to do.
- States: camera lost → the frame shows "Rear camera not responding" on sunk fill and the Reach continues from radar; both lost → P2 "People sensing is off. Look around before you swing."
- The camera view is never shown in Working mode except inside a P1 or P2 where it adds information.


### Button

Glove-sized, square-shouldered buttons. The primary action is graphite, not a hue: ShiftMate spends no safety colour on itself.

| Variant | Fill | Label | Use |
| --- | --- | --- | --- |
| primary | `sm-color-action` | `sm-color-on-action` | The one thing to do on a screen |
| secondary | `sm-color-surface` + 2 px `sm-color-action-border` | ink | Alternatives |
| quiet | none, 3 px underline | ink | "Not now", "Later" |
| stop | `sm-safety-danger` + octagon | `sm-safety-on-danger` | Drill STOP only |
| danger-quiet | none, `sm-safety-danger-ink` outline | danger ink | "Delete draft" — never next to its opposite |

#### Sizes
min 68 × 68 px (`sm-size-target-min`, 18 mm); standard height 88 px; xl 120–132 px. Label 28 px (xl 36–40 px). Glyph 40 px. Radius `sm-radius-control` 10 px.

#### States
- **Pressed**: darker fill (`sm-color-action-pressed`) and a 2 px downward shift for the press duration (`sm-motion-press` 80 ms). No hover.
- **Focused** (keyboard, switch access, D-pad on some rugged tablets): 4 px `sm-color-focus` ring outside a 3 px `sm-color-chalk` gap.
- **Disabled**: `sm-color-disabled` fill, `sm-color-on-disabled` label, glyph removed. Prefer hiding a control to disabling it.
- **Loading**: label hidden behind a dashed progress line; the button keeps its size.
- **Error**: the button returns to default and the error is written next to it ("Not sent. Saved on this tablet.").
- **Offline**: an action that needs the network changes its label ("Send when online") rather than failing.

#### Spacing rules
- ≥ 16 px (`sm-space-4`) between any two targets.
- Opposite or destructive pairs (Send / Delete, Start / Stop) sit on opposite sides of the screen or ≥ 64 px apart (`sm-space-8`), never adjacent.


### LargeToggle

A 136 × 72 px switch with the state written inside ("ON"/"OFF") — the knob position is never the only cue.

- Track: 4 px ink border, radius-control. On: graphite track with chalk "ON"; off: sunk track with "OFF".
- The whole row (switch + label, ≥ 88 px tall) is the target.
- Changes apply immediately; no confirm. Settings that affect safety (read alerts aloud) cannot be switched off in Working mode.


### SegmentedControl

Two to four mutually exclusive options in one plate: theme, language, report type.

- 80 px tall (68 px minimum in dense rows), each segment ≥ 96 px wide; 4 px ink frame, 2 px dividers.
- Selected = inversion (`sm-color-selected`), plus `aria-pressed`.
- Language segments show each language in its own script (EN · த · हि).


### PinPadAndBadge

Sign-in at the start of a shift: badge scan first, PIN as the fallback.

- PIN keys: 112 × 96 px, 16 px gaps, 44 px tabular digits. The blank key keeps the grid; backspace is bottom-right, far from "1".
- Four dots show progress; wrong PIN clears the dots and says "That PIN didn't match. Try again." (no shake).
- Badge target: 360 × 228 dashed plate; on read, the operator's name and last machine appear for confirmation.
- Offline: sign-in works against the roster cached on the tablet; the rail shows the offline glyph.


### ChecklistItem

Pre-start checks: each item has two explicit answers, **OK** and **Problem**, never a single tick box (an unticked box is ambiguous).

- Row: text 30/38 + two 180 × 76 px answer buttons, 16 px apart. The two answers are opposites but not destructive; "Problem" opens the report draft with the item pre-filled.
- Answered: the chosen answer inverts; the other stays outlined.
- Voice: "all OK" answers the remaining items OK after reading them back.


### ReportDraftCard

What ShiftMate understood from the operator's voice report, laid out as fields to check. Nothing is sent until the operator confirms.

- Grid: key 220 px (24 px ink-2) · value (30/38 semibold) · edit 132 px (92 × 68 px button).
- Fields: Type, Where + when, What happened, People involved (never named by default), Evidence (camera clip auto-attached around the time).
- Editing a field re-opens push-to-talk scoped to that field, or big-button choices for Type.
- Actions: "Send report" (xl primary, right) and "Delete draft" (quiet danger, far left) — never adjacent.
- Offline: the dashed "Will send when back online" tag; the report is saved on the tablet and counted in the rail's waiting number.
- Error: fields ShiftMate is unsure of show a dotted underline and "Check this".


### TimeSplit

The shift as one bar: working, each idle reason, engine off — in time order, so the operator can see *when*, not just *how much*.

- 64–72 px tall, 4 px ink frame; segments separated by 3 px surface gaps.
- Idle categories are **not safety colours**. They are told apart by lightness **and pattern**: waiting = solid slate; warm-up = vertical ticks; break = light stone; engine on, cab empty = dots; short stops = horizontal lines; not sure = surface with a dashed outline. Diagonal hatch is never used here (it is reserved for real hazards).
- Working is the darkest (solid ink); engine off is the track colour.
- Axis labels under the bar at shift start, every 2 h, and shift end (tabular).
- Screen reader: the summary sentence ("Working 5 h 10 m, idle 2 h 45 m, engine off 35 m") plus a table of segments.


### IdleSegmentRow

One idle reason: glyph, pattern swatch, name, the plain explanation and the total. The explanation carries the no-blame stance.

- Columns: glyph 40 · swatch 28 · name 250 (26/32 semibold) · why (22/28 ink-2, up to 2 lines) · value 100 (26 bold tabular).
- Why-lines state the cause, not the person: "Trucks were late 10:10–10:40", not "You waited 1 h 05 m". For engine-on-cab-empty, give the fact and the saving, never "you left the engine running".
- "Not sure" is a first-class reason. ShiftMate does not guess habits it cannot see.


### CoachingNote

Two notes end every My Day: **Went well** (always first, always specific) and **One idea for tomorrow** (at most one).

- Went well: 4 px ink frame, star glyph. Must cite a number the operator can recognise ("18 of 18 loads").
- Idea: 2 px frame, book glyph, links to a lesson ≤ 2 min. Phrased as an option ("Trucks on your swing side save about 3 s a load"), never an instruction or a score.
- No rankings against other operators, no percentages of "efficiency", no red.


### LessonCard

A short lesson in the Learn list: art plate, title as a plain promise, length and format.

- 168 px min height; art plate 200 × 128 on sunk fill with bezel radius. Title 32/40. Status word above ("Recommended", "New", "Done") — not a colour.
- Lessons are 2–4 min, narrated, playable eyes-free, and only start in Paused mode. If the machine starts moving, narration pauses and resumes at the card's start.


### NarratedCardPlayer

One idea per card, read aloud: a plan-view diagram, one sentence, one supporting fact.

- Player frame: 4 px ink, bezel radius; diagram 520 × 330 in site-drawing style (ink on sunk, dashed = "place it here").
- Progress: segmented, one block per card (never a thin scrubber).
- Controls: Pause/Play (xl primary), Again (replays this card). Swipe is not required; cards advance when narration ends.
- Narration language: segmented control EN · த · हि; captions follow the narration language.


### QuizOption

Full-width answer plates, 96 px tall, letter key + answer text.

- Right: 5 px `sm-safety-safe` border **and** a check glyph **and** the explanation sentence.
- Wrong (after answering): dashed border, ink-2 text. No red, no cross; the right answer is shown.
- Answers can be spoken ("B").


### DrillFrame

The hazard-reaction drill: a scene, hidden hazards to spot, and a big STOP. Runs in Paused mode only (the rail says so).

- Scene frame: 4 px ink, bezel radius. Hazard markers: 96 px rings with a chalk ring and ink keyline; found = caution-yellow ring.
- STOP: xl stop button (140 px, `sm-safety-danger` + octagon). This is the only place a danger fill is a button, because it trains the real reaction.
- Results in big tabular figures ("2 of 3", "0.8 s"); no score, no leaderboard.


### BookingSlot

Instructor slots as large plates: day, time (32 px tabular), instructor and place.

- ≥ 104 px tall, 2 px border. Selected: inversion + 4 px border. Full: sunk fill, dashed border, the word "Full".
- Booking confirms with one primary button; the slot then appears in My Shift for that day.


### ProgressView

Personal progress, private to the operator unless they share it.

- Skill ladders: one block per level (44 px tall, ink when reached), with the next concrete step written out.
- Month summary: three tabular numbers with words. No percentages, no comparisons with other people.


### AssistantAnswer

Ask Cat's answer: the question as heard, a short spoken-style answer, and where it came from.

- 4 px ink frame. Question 26/34 ink-2 ("You asked: …"). Answer 34/46, max 3 sentences; longer answers become numbered steps read one at a time.
- **Source chips** (68 px, tappable): document + section. Tapping opens the manual page.
- **Offline**: dashed "Offline answer · manual saved 18 Sep" tag; source chips become dashed. Calm, not an error.
- **Doesn't know**: dashed frame, "I don't know… I won't guess", and a next step (Ask supervisor). Never invent a value.
- Read aloud automatically in the operator's language; "Read it again" and "Show the page" follow the answer.


### SystemStates

Empty, error, stale-data and offline states share one quiet form: a dashed plate, a glyph, a heading that says what happened, a sentence that says what it means for the operator, and at most one action.

- **Empty**: say why it is empty and when it will fill. Never a cartoon.
- **Error**: never blame the operator; say what still works ("Your work is still being recorded").
- **Stale**: any live value older than its freshness limit (proximity 1 s, position 10 s, estimates 10 min) shows the stale mark and its age. Stale proximity data raises a P2 — it is never shown as "clear".
- **Offline**: normal, calm, no red, no exclamation marks. The rail glyph changes; a count of waiting items appears.


### SyncStates

Connectivity uses a site-mast glyph, not a phone signal icon: online (arcs), offline (no arcs, short level dashes), items waiting (a filled square + count), sending (dashed arcs), synced (tick).

- The rail shows the glyph alone when synced/online; words appear when something is waiting.
- Offline is expected and calm: no colour, no alert. Only if proximity or seatbelt *sensing* is lost does anything escalate — that is a sensor problem, not a connectivity one.


### Glyphs

ShiftMate's own glyphs for everything that means a machine, a person or a safety state; Phosphor (Bold) for generic UI.

- 48-unit grid, plan-view where a machine is drawn, square caps, mitred joins.
- Stroke `--sm-icon-stroke`: 4 (Day, Night), 5 (Sunlight). Fills are used for state (filled house = working).
- Sizes: 32 (with body text), 44–48 (rail, chips), 72 (P2, empty states), 160–300 (P1).
- Priority shapes are always filled with the safety colour **and** keylined in ink (yellow and orange need the keyline to reach 3:1 on light surfaces).


### ConsoleSiteMap

A live top-down site layout drawing: survey grid, haul roads, zones, machines with their swing rings, trucks, and tagged people.

#### Symbology
- **Grid**: 50 m, `sm-color-line-soft`; heavier every 250 m.
- **Zones**: dashed ink rectangles with a decal label (`LOAD-A`); the trench as a thick line, dug part in ink, planned part in ink-2.
- **Machines**: the Reach ring geometry at map scale — dashed 2× reach, solid reach + 2 m, heavy swing radius; boom line shows current swing. House fill = state (solid working, open + bars idle, dashed engine off). ID plate beside; selected machine's plate inverts.
- **People-in-zone**: the same tier sectors as the cab; critical uses the hatch. Hatch appears on the map *only* for a live critical event.
- **Trucks**: plan rectangles with cab block; open = waiting, filled = moving; ID in 11 px.
- **People**: 5 px ink dots with a surface halo (tags, not names).
- North arrow and a 50 m scale bar always visible; legend bottom-left.


### MachineDetailPanel

The right-hand panel when a machine is selected on the live map: who, what, how it is going, and what is near it.

- Header: ID decal (20 px wdth 125) + state chip; operator name + ID; model, sensor tier and last sync.
- Current task with the range bar and likely time.
- Key-value rows: Nearby, Risk (with stack light), Seatbelt, Idle today (with the top reason), Alerts today (with acknowledge times).
- Today's time-split bar.
- Actions: "Voice note to Ravi" (plays in the cab only when Paused) and "Send a truck". There is no "flag operator" action.


### IdleCausesBreakdown

The supervisor's "where time was lost": the lead sentence in 40 px ("3 h 20 m waiting for trucks"), then a table of idle causes with pattern swatches and share bars, then waiting-by-hour bars, then **one suggestion** with a range and its basis ("Add one truck to LOAD-A, 10:00–12:00 · would likely save 1 h 30 m – 2 h 10 m · based on 3 similar days").

- Causes use the idle tokens and patterns, same as the cab.
- The lead sentence names the cause, not the operators. Machine-level detail is one click away; operator names are not shown in this view.


### SafetyOverview

The day's safety events: P1s with time, what, machine · operator and outcome (acknowledge time), grouped P2 counts, risk-band hours with the main reason, and operator reports.

- Priority shapes at 20 px in the first column; outcomes are facts ("Stopped in 2 s").
- Footer states the principle: counts are for learning, not ranking; operators see the same data about themselves.


### FleetTiles

One tile per site across countries: country and local time, site name, machines active of total, the risk-band distribution (a 3-part bar with counts in words), the main condition and sync state.

- The scale panel beneath reports the simulated fleet (10,000 machines), live ingest (events/s, p95 alert latency), offline machines buffering, and a clearly labelled **projection** for 1.6 million machines ("Linear from 4.13 events/s per machine … Projection, not measured").


### DemoControlBar

For demos only: a dashed bar labelled "Demo mode · simulated data" with scenario buttons (person enters swing zone, trucks 20 min late, drop network at LOAD-A, switch to night shift, reset). Never present in production builds; its dashed border and label make simulated data impossible to mistake for live.


## 11. Content voice

ShiftMate talks like a trusted senior operator sitting beside you: brief, specific, never fussy, never scolding.

### Principles
1. **Say what happened, then what to do.** "Person close on your left. Slow down."
2. **Plain words, short sentences, active voice.** ≤ 12 words a sentence in the cab. No jargon the operator wouldn't use on site ("idle event", "telemetry", "compliance" are console words at most).
3. **Name the cause, not the person.** "Trucks were late", not "You were idle". Never "you failed", "you forgot" or "violation".
4. **Start with what went well.** It has to be true and specific.
5. **Be honest about uncertainty.** Ranges, "likely", "Not sure", "I don't know". Never pretend.
6. **Calm about systems, firm about people.** Offline, sync and errors are calm. Danger to a person is direct and imperative.
7. **No exclamation marks, no emoji, no ALL CAPS** (except the STOP drill button and IDs like EXC001).
8. **Write each language natively.** Tamil and Hindi lines are written for the same meaning and speaking time, not translated word for word. Use the words operators actually use on site: ட்ரக்/லாரி, बेल्ट, லோடு.
9. **Numbers the way they are read on site**: 24-hour times, "1 h 05 m" on screen in every script, durations spoken in words.

### Example strings

| # | Context | English | हिन्दी | தமிழ் |
| --- | --- | --- | --- | --- |
| 1 | P1 person | Stop. Person behind you. | रुकिए। पीछे कोई है। | நிறுத்துங்கள். பின்னால் ஒருவர் இருக்கிறார். |
| 2 | P1 seatbelt | Stop the machine. Buckle up. | मशीन रोकिए। बेल्ट लगाइए। | இயந்திரத்தை நிறுத்துங்கள். பெல்ட் போடுங்கள். |
| 3 | P2 proximity | Person close on your left. Slow down. | बाईं ओर कोई पास है। धीरे चलाइए। | இடது பக்கம் அருகில் ஒருவர் இருக்கிறார். மெதுவாக. |
| 4 | P3 heat | Water break due at 11:00. | 11:00 बजे पानी का ब्रेक है। | 11:00-க்கு தண்ணீர் இடைவேளை. |
| 5 | Idle: truck | Waiting for a truck. The next one is about 3 min away. | ट्रक का इंतज़ार है। अगला करीब 3 मिनट में आएगा। | லாரிக்காகக் காத்திருப்பு. அடுத்தது சுமார் 3 நிமிடத்தில் வரும். |
| 6 | Idle: no blame | Logged as a truck delay, not your idle time. | यह ट्रक की देरी में गिना गया, आपके खाली समय में नहीं। | இது லாரி தாமதமாகப் பதிவானது, உங்கள் சும்மா நேரமாக அல்ல. |
| 7 | Idle: engine on, cab empty | The engine ran 10 min with the cab empty. Switching off for stops over 5 min saves about 1 L. | केबिन खाली था और इंजन 10 मिनट चला। 5 मिनट से लंबे रुकने पर इंजन बंद करें, करीब 1 लीटर बचेगा। | கேபின் காலியாக இருந்தபோது இன்ஜின் 10 நிமிடம் ஓடியது. 5 நிமிடத்துக்கு மேல் நின்றால் அணைத்தால் சுமார் 1 லிட்டர் மிச்சம். |
| 8 | Estimate | Likely 1 h 05 m, between 55 m and 1 h 25 m. | लगभग 1 घंटा 5 मिनट, 55 मिनट से 1 घंटा 25 मिनट के बीच। | பெரும்பாலும் 1 மணி 5 நிமிடம்; 55 நிமிடம் முதல் 1 மணி 25 நிமிடம் வரை. |
| 9 | Low confidence | Estimated from limited data. | कम डेटा से अनुमान। | குறைந்த தரவிலிருந்து மதிப்பீடு. |
| 10 | Reason | Wet ground adds 20–40 min. | गीली ज़मीन से 20–40 मिनट ज़्यादा लगेंगे। | ஈரமான தரையால் 20–40 நிமிடம் கூடுதலாகும். |
| 11 | Voice error | Didn't catch that. Try again, or use the buttons below. | समझ नहीं आया। फिर बोलिए, या नीचे के बटन दबाइए। | சரியாகக் கேட்கவில்லை. மீண்டும் சொல்லுங்கள், அல்லது கீழே உள்ள பட்டன்களை அழுத்துங்கள். |
| 12 | Offline | Offline. Everything still works. 3 reports will send when the signal is back. | ऑफ़लाइन। सब काम कर रहा है। सिग्नल आते ही 3 रिपोर्ट चली जाएँगी। | இணைப்பு இல்லை. எல்லாம் வேலை செய்கிறது. சிக்னல் வந்ததும் 3 அறிக்கைகள் போகும். |
| 13 | Offline answer | Offline answer, from the manual saved on 18 Sep. | ऑफ़लाइन जवाब, 18 सितंबर को सेव की गई मैनुअल से। | இணைப்பில்லாத பதில் — 18 செப்டம்பர் அன்று சேமித்த கையேட்டிலிருந்து. |
| 14 | Assistant doesn't know | I don't know. It isn't in the manuals on this machine, and I won't guess. | मुझे नहीं पता। यह इस मशीन की मैनुअल में नहीं है, और मैं अंदाज़ा नहीं लगाऊँगा। | எனக்குத் தெரியாது. இந்த இயந்திரத்தின் கையேட்டில் இல்லை; நான் ஊகிக்க மாட்டேன். |
| 15 | Lesson | Park the truck so you swing less than 90°. | ट्रक ऐसे लगवाइए कि 90° से कम घुमाना पड़े। | 90°-க்குக் குறைவாகச் சுழலும்படி லாரியை நிறுத்தச் சொல்லுங்கள். |
| 16 | Empty state | No tasks yet. Your supervisor's plan usually arrives before 07:00. | अभी कोई काम नहीं। सुपरवाइज़र का प्लान आमतौर पर 07:00 से पहले आता है। | இன்னும் வேலைகள் இல்லை. மேற்பார்வையாளரின் திட்டம் பொதுவாக 07:00-க்கு முன் வரும். |
| 17 | Went well | 18 of 18 loads. Loading cycle 21 s, 2 s faster than last week. | 18 में से 18 लोड। लोडिंग साइकिल 21 सेकंड, पिछले हफ़्ते से 2 सेकंड तेज़। | 18-க்கு 18 லோடு. ஏற்றும் சுழற்சி 21 வினாடி — கடந்த வாரத்தைவிட 2 வினாடி வேகம். |

Hindi and Tamil lines are drafts for review with operators at the Chennai site before release. Speaking time is checked with the TTS voice: each P1/P2 line must take no longer than 110% of the English line.

### Words we use / avoid

| Use | Avoid |
| --- | --- |
| Waiting for a truck | Idle violation, downtime event |
| Engine on, cab empty | Unauthorised idling, left running |
| Not sure | Unclassified |
| Likely / about | Exactly (unless it is exact) |
| Seen · I've stopped | OK · Dismiss (for alerts) |
| Offline answer | Error: no connection |
| Idea for tomorrow | Improvement required |


## 12. Accessibility

### Contrast targets per theme

| Theme | Primary text | Secondary text | Non-text marks, borders, focus | Measured (see Colour) |
| --- | --- | --- | --- | --- |
| Day | ≥ 7:1 | ≥ 4.5:1 (all cab text is ≥ 24 px, but AA-normal is still met) | ≥ 3:1 | ink 16.5, ink-2 8.8, ink-3 6.5 |
| Sunlight | ≥ 7:1 on **all** text | ≥ 7:1 | ≥ 3:1, no hairlines, strokes +1 | ink 21, ink-2 21, ink-3 17.4; lowest text pair 7.1 (white on safe green) |
| Night | ≥ 7:1 | ≥ 4.5:1 | ≥ 3:1 | ink 10.0, ink-2 5.8, ink-3 5.05; text on danger fill 4.9 |

### Colour independence
Every safety meaning has at least three cues: **colour + shape + word**, and usually position too.
- Priorities: octagon, triangle, diamond, square.
- Risk: stack-light lamp *position*.
- Proximity: which ring band is occupied, hatch for critical, distance in figures.
- Idle categories: pattern + label.
- Selected / current: inversion + `aria-current` / `aria-pressed`, never a tint.
- Release check: run deuteranopia, protanopia and tritanopia simulations of all three themes; every state must stay identifiable by shape and word alone.

### Focus visibility
4 px solid `sm-color-focus` outline with a 3 px `sm-color-chalk` gap (`outline-offset: 3px`), visible on surfaces and on graphite actions in all themes (≥ 12:1 on surfaces). Focus order: rail → content (reading order) → nav → push-to-talk. Supports external keypads and switch access on rugged tablets.

### Minimum sizes
- Targets ≥ 68 px (18 mm); standard 88 px; ≥ 16 px apart.
- Cab text ≥ 24 px (Paused), ≥ 36 px while moving; console text ≥ 13 px.
- Glyphs ≥ 28 px beside text, ≥ 44 px standing alone.

### Reduced motion
Respect `prefers-reduced-motion` and the in-app setting (see Motion). Urgency moves to sound and haptics, never lost.

### Screen-reader labels for glyph-only elements

| Element | Label |
| --- | --- |
| Reach (rail) | "Proximity: clear" / "One person, caution ring, right rear, 7 metres" |
| Stack light | "Risk raised, mainly heat" |
| Belt glyph | "Seatbelt fastened" / "Seatbelt unbuckled" |
| Sync glyph (no word) | "Synced at 10:42" |
| Queue pip | "One more alert waiting: warning" |
| Range bar | "Likely 1 hour 5 minutes, between 55 minutes and 1 hour 25 minutes" |
| Load blocks | "7 of 18 loads" |
| Time-split bar | Summary sentence + a table of segments |
| Push-to-talk | "Hold to talk" (+ `aria-pressed` while listening) |
| Map | "Live site map" + a machine list table as the accessible alternative |

Alerts use `role="alertdialog"` (P1), `role="alert"` (P2) and `role="status"` (P3/P4); the transcript uses `aria-live="polite"`.

### Hearing and speech
Every sound has a visual equivalent, and every spoken prompt appears as text. Voice input always has buttons. Accent-robust recognition is tested with Tamil-, Hindi-, Norwegian- and Australian-English speakers in cab noise.


## Appendix: tokens.css

See the `tokens.css` file delivered alongside this document.
