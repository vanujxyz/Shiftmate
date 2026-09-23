# ShiftMate — Decision log

Append-only. Format per CLAUDE.md §7. Decisions marked **(user)** were made or approved by the project owner.

## D-001 — Load cycle definition
Date: 2026-09-23 · Phase: 0 · Requirement(s): PRD §7, F-FLT-01
Context: The brief's "Load Cycles" column has no definition.
Decision: For excavators and wheel loaders one load cycle = one haul truck fully loaded; for dozers = one push cycle. Defined per machine profile (`load_cycle_definition`).
Why: Matches the sample magnitudes (≈10–12 per two hours) and PRD §7; config, not code.
Alternatives: One bucket pass per cycle (would give ~150 per two hours, inconsistent with the sample).

## D-002 — Interval semantics
Date: 2026-09-23 · Phase: 0 · Requirement(s): PRD §7, TRD §5.3
Context: The brief does not say what period a row covers.
Decision: Each interval record summarises the period since the previous record for that machine. `Timestamp` is the interval end. Built every 15 machine-minutes and at task boundaries.
Why: PRD §7 assumption; makes fuel, load cycles and idling additive.
Alternatives: Point-in-time snapshots (cumulative counters) — rejected, the sample values are not cumulative.

## D-003 — Safety alert definition
Date: 2026-09-23 · Phase: 0 · Requirement(s): PRD §7, TRD §5.3, §7.5
Context: "Safety Alert Triggered" is not defined in the brief.
Decision: `Yes` if any P1 or P2 alert occurred in the interval, otherwise `No`.
Why: PRD §7; in the sample it coincides with an unfastened seatbelt, which is a P1 rule.
Alternatives: Only seatbelt alerts (too narrow for proximity and unattended running).

## D-004 — Sample rows are fixtures, not calibration
Date: 2026-09-23 · Phase: 0 · Requirement(s): PRD §7, TRD §5.6
Context: The four sample rows are not internally consistent (fuel vs engine hours).
Decision: Keep them verbatim in `fixtures/sample_rows.csv`, validate them against the schema in a test, and never use them to calibrate simulator physics.
Why: PRD §7; honest numbers.
Alternatives: Fit simulator rates to the sample — rejected, the numbers cannot all be true at once.

## D-005 — Ravi's shift heat values corrected **(user)**
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): PRD §9 beat 7, TRD §8, F-SAFE-04
Context: The TRD weather script (38 °C/60 % at 10:45, 40 °C/58 % at 11:00) gives Rothfusz heat indices of about 55 °C and 61 °C, not the 45 °C the beat and caption describe.
Decision: 34 °C / 62 % RH at 10:45 (heat index ≈ 43 °C) and 35 °C / 60 % RH at 11:00 (≈ 45 °C). TRD §8 updated.
Why: The caption and the risk band must match the physics shown on screen (honest numbers).
Alternatives: Change the caption to 61 °C (unrealistic and extreme for the demo).

## D-006 — Ravi skips the 10:30 break; waiting does not reset continuous operation **(user)**
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): PRD §9 beat 7, F-SAFE-05, F-SAFE-06, F-SHIFT-06, TRD §6.1, §8
Context: With heat index 45 °C and no other factors, the risk score is about 33 (Green), but beat 7 needs Amber and a break suggestion.
Decision: The scenario adds a `skip_break` beat at 10:30 (Ravi keeps working to catch up after the truck delay). `continuous_operation_min` resets only after ≥ 10 min in a break or with the engine off; idle while waiting for a truck does not reset it. At 11:00 risk ≈ heat 25 + continuous operation 20 + ground → Amber, and HEAT_NO_BREAK suggests a break. No risk weights change. The break suggestion uses coaching wording, never blame (e.g. "Hot today. A water break now helps you finish strong."). TRD §6.1 and §8 updated.
Why: Keeps the risk model honest and untouched; waiting in a hot seated cab is not rest.
Alternatives: Raise heat weights (rejected by the user); make ground muddy (fragile, sits exactly on the threshold).

## D-007 — Caution proximity shows live in the rail while working **(user)**
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): F-SAFE-02, F-SAFE-08, TRD §4.4, §4.6
Context: PROXIMITY_CAUTION is P3, and P3 is delivered only when paused, which would show a caution after the danger has passed.
Decision: While working, the caution tier is shown live on the Reach gauge in the status rail (no strip). PROXIMITY_DANGER (P2) and PROXIMITY_CRITICAL (P1) interrupt as specified. A queued caution P3 that is no longer true when the machine pauses is dropped to the P4 feed as history (DESIGN AlertQueue rule 2).
Why: Eyes on the work (PRD §5.3) while keeping proximity visible.
Alternatives: Promote caution to P2 (alert fatigue).

## D-008 — Extra alert rules from DESIGN.md
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): F-SAFE-04, DESIGN RiskIndicator, SystemStates
Context: DESIGN.md asks for an alert when the risk band rises (P3 to raised, P2 to high) and a P2 when proximity data goes stale; the TRD has no such rules.
Decision: Add `RISK_BAND_RAISED` (P3), `RISK_BAND_HIGH` (P2) and `PROXIMITY_STALE` (P2, only where a proximity source exists) as config rules in `safety_rules.yaml`.
Why: TRD silent, DESIGN specifies; configured, not coded.
Alternatives: Leave risk changes silent.

## D-009 — Features removed from the design **(user)**
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): DESIGN MachineDetailPanel, ReportDraftCard, PushToTalk, DemoControlBar
Context: DESIGN.md shows features with no backend in the TRD.
Decision: Removed completely (not shown disabled): "Send a truck", "Voice note to Ravi", camera clip on reports, "call supervisor" by voice, and the "switch to night shift" demo button.
Why: No invented behaviour; keeps scope to the PRD.
Alternatives: Show as disabled (rejected by the user).

## D-010 — QR badge sign-in with jsqr **(user)**
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): F-START-01, TRD §11.2
Context: Chrome on Windows has no built-in QR reader (`BarcodeDetector` is unavailable there).
Decision: Add `jsqr` (MIT, ~50 KB) for QR badge scanning from the webcam; keep the PIN pad as the fallback.
Why: F-START-01 names QR; smallest dependency that works offline.
Alternatives: PIN only.

## D-011 — Theme switching and haptics on a laptop
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): F-CAB-02, DESIGN §2, §8
Context: DESIGN.md switches theme by ambient light and uses seat/tablet haptics; the demo laptop has neither sensor nor vibration.
Decision: Theme follows the simulated `is_night` signal (Night) and otherwise Day; the operator can override to Day, Sunlight or Night at any time. Haptics are omitted; sound and on-screen cues carry urgency.
Why: Simplest behaviour consistent with the design intent.
Alternatives: Browser AmbientLightSensor API (not available in Chrome by default).

## D-012 — Reach ring radii come from machine profiles
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): F-SAFE-02, TRD §4.1, DESIGN Reach
Context: DESIGN.md describes the rings as "2× reach / reach + 2 m / swing radius"; the TRD profiles give fixed distances (excavator 10 / 6 / 3.5 m).
Decision: The Reach and the map rings are drawn at the effective caution / danger / critical distances from the profile, scaled by the risk band. The design's descriptive names stay as labels.
Why: The picture must always match the logic that raises the alert.
Alternatives: Derive from boom reach (would disagree with the alert thresholds).

## D-013 — Lesson length and drill results display
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): F-LRN-01, F-LRN-04
Context: DESIGN says lessons are 2–4 min and drills show "no score"; the PRD says 1–3 min and drills are scored.
Decision: Lessons are 1–3 min (PRD). Drill score is stored (TRD `drill_results.score`) but shown as facts ("2 of 3", "0.8 s"), without a single score number or leaderboard.
Why: PRD wins on behaviour; DESIGN tone kept.
Alternatives: None considered.

## D-014 — Glyphs and illustrations drawn in-house
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): DESIGN §6
Context: DESIGN.md specifies the glyph set and lesson illustrations but did not ship the SVG files.
Decision: Draw them as SVG React components following DESIGN §6 (48-unit grid, plan view, square caps, `currentColor`, `--sm-icon-stroke`).
Why: Required by the design; no copyrighted artwork.
Alternatives: Use Phosphor for these (forbidden by DESIGN).

## D-015 — History pipeline split across milestones
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): TRD §7.5, CLAUDE Phase 2–3
Context: Some §7.5 invariants (e.g. `safety_alert_triggered` iff P1/P2) need the engines, which are built after the simulator.
Decision: Milestone 3 generates ticks, tasks, dispatch log and ground truth with tick-level invariants. Milestone 5 runs the real engine pipeline over the stored ticks to produce intervals and events, and adds the interval-level invariants. `shiftmate sim generate` runs both once they exist.
Why: The intervals must come from the same engines the edge uses, not a second implementation.
Alternatives: A simplified interval builder in the simulator (two implementations to keep in sync).

## D-016 — Per-site season settings for history
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): TRD §4.3, §7.1–7.2
Context: History covers the 42 days before 24 Sep 2026; Tromsø has short nights and no frost then, but the TRD wants sub-zero, long darkness and frozen ground.
Decision: Each site config lists which month profile to use for which history days (Chennai: May for days 1–21, October for 22–42, as in the TRD; Tromsø: winter months). Daylight is computed from that season month.
Why: Condition variety is the purpose of the four sites.
Alternatives: Real calendar dates (Tromsø would look like summer).

## D-017 — Deterministic event IDs
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): TRD §5.4, §7.5, §15
Context: uuid7 normally uses the wall clock and random bits, which would break "same seed ⇒ identical event logs". Python 3.12 has no stdlib uuid7.
Decision: A small `util/ids.py` builds RFC 9562 uuid7 values from the simulated timestamp and a seeded `numpy.random.Generator`.
Why: Determinism; no extra dependency.
Alternatives: `uuid6` package (non-deterministic).

## D-018 — Test script scope
Date: 2026-09-23 · Phase: 0 · Requirement(s): CLAUDE §2, TRD §13
Context: CLAUDE.md says `test:all` = pytest + vitest + contracts check with Playwright in `pnpm e2e`; TRD §13 puts Playwright inside `test:all`.
Decision: Follow CLAUDE.md: `test:all` excludes Playwright; `pnpm e2e` runs it. Added `contracts:check` (TRD §13).
Why: CLAUDE.md has precedence on process.
Alternatives: Include e2e in `test:all` (slow, needs servers).

## D-019 — Fleet patterns from the training period
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): TRD §6.7, F-FLT-05
Context: TRD §6.7 computes fleet patterns from test-period data.
Decision: Compute them from days 1–35 (train + validation) so the test days stay untouched.
Why: Golden rule 11; never tune on or leak from test data.
Alternatives: Test-period data as written.

## D-020 — Speech recognition needs real internet **(user)**
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): F-ASK-01, F-SAFE-09, TRD §11.2
Context: Chrome's Web Speech recognition sends audio to Google; Tamil/Hindi text-to-speech voices may not be installed on Windows.
Decision: The README states that browser speech recognition needs real internet at the venue, separate from the simulated network toggle. The user installs the Windows Tamil and Hindi speech packs. Every voice action keeps a button.
Why: Honest limitation; demo resilience.
Alternatives: On-device speech models (out of scope, PRD §12).

## D-021 — LLM provider: Google Gemini free tier instead of Anthropic **(user)**
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): F-ASK-01..06, F-REP-01, TRD §2, §6.10, §10, §14
Context: The TRD specifies the Anthropic API. The project owner chose not to use it.
Decision: A provider layer in `backend/src/shiftmate/assistant/llm.py` gives the assistant and the report parser one interface. Only a Gemini provider is implemented, using the official `google-genai` SDK (installed in milestone 14 after confirmation). Settings: `SHIFTMATE_LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, `SHIFTMATE_LLM_MODEL` (exact AI Studio model name). `ANTHROPIC_API_KEY` removed. Gemini JSON output mode is used for answers and report parsing; all validation stays (citations must be among retrieved chunks, else refuse). Missing key, HTTP 429, timeout or any error → immediate offline fallback with the offline label. The assistant evaluation spaces calls for the per-minute limit and caches every response (answers and judge) on disk. Everything runs without a key. TRD §2, §10.3, §10.6 and §14, `.env.example` and README updated.
Why: Owner decision (free tier); provider layer keeps the rest of the code provider-neutral.
Alternatives: Anthropic as in the TRD.

## D-022 — "Cat" naming in words only **(user)**
Date: 2026-09-23 · Phase: 0 (plan) · Requirement(s): Golden rule 8, PRD §6.7
Context: "Ask Cat" and "Cat dealer training centre" use the Cat name.
Decision: Keep the PRD names as plain words; no logos, trade dress or brand colours; no real dealer names.
Why: Owner decision; descriptive use only.
Alternatives: Rename the assistant.

## D-023 — Translation review tracking **(user)**
Date: 2026-09-23 · Phase: 0 · Requirement(s): Golden rule 10, F-CAB-05
Context: Hindi and Tamil text is written by the builder and must be reviewed by people (the owner reviews Hindi; a native speaker checks Tamil).
Decision: `pnpm i18n:review` writes `docs/TRANSLATIONS_REVIEW.md` listing every hi/ta string beside its English source with its review state. Approvals are recorded in `docs/translations-reviewed.json` with the exact approved text, so a later edit automatically returns the string to the review list. Lesson and checklist text from config is added in milestone 2.
Why: Easy to find, hard to lose track of changes.
Alternatives: Comments in the JSON (JSON has no comments).

## D-024 — Design files relocated **(user)**
Date: 2026-09-23 · Phase: 0 · Requirement(s): CLAUDE §0, TRD §11.1
Context: `DESIGN.md`, `SUMMARY.md` and `tokens.css` were delivered in the repository root.
Decision: Moved to `docs/DESIGN.md`, `docs/DESIGN_SUMMARY.md` and `frontend/packages/ui/src/tokens.css`.
Why: Paths expected by CLAUDE.md and the TRD.
Alternatives: None.

## D-025 — Tooling versions and Playwright browser
Date: 2026-09-23 · Phase: 0 · Requirement(s): TRD §2
Context: TRD asks for the latest stable versions. Latest TypeScript is 7.0, but `typescript-eslint` 8.70 supports TypeScript < 6.1 only. Playwright normally downloads its own Chromium (~170 MB).
Decision: Pin TypeScript `~6.0` (6.0.3) until typescript-eslint supports 7. Playwright runs with `channel: "chrome"` (the installed Chrome), so no browser download. uv installed with winget, pnpm with `npm install -g pnpm` (12.5.1). Python 3.12.10 is the existing system install.
Why: Working lint (golden rule 13); fewer downloads; Chrome is the target demo browser anyway.
Alternatives: TypeScript 7 without typescript-eslint type-aware rules; Playwright's bundled Chromium.

## D-026 — Font family names in tokens.css
Date: 2026-09-23 · Phase: 0 · Requirement(s): DESIGN §3, golden rule 9
Context: `tokens.css` names the fonts "Anek Latin", "Anek Tamil", "Anek Devanagari", but the `@fontsource-variable/*` packages it imports register "Anek Latin Variable" etc. As delivered, the Anek fonts would never be applied. It also imported both `wght.css` and `wdth.css` for Latin, which load the same font twice.
Decision: `--sm-font-sans` now lists the "… Variable" names first, keeping the original names and fallbacks after them; the duplicate Latin `wght.css` import is removed (`wdth.css` carries both axes, as DESIGN §3 says). A Playwright smoke test checks that Anek Tamil actually loads.
Why: Genuine bug fix; no visual change from what DESIGN.md intends.
Alternatives: Static `@fontsource/*` packages (lose the width axis the design uses).

## D-027 — Ground-truth labels in a separate table
Date: 2026-09-23 · Phase: 1 · Requirement(s): Golden rule 5, TRD §5.3, §7, §7.4
Context: TRD §5.3 lists `label_*` as columns of the interval record, while §7 lists `labels` as a separate Parquet output.
Decision: `IntervalRecord` has no label fields. The simulator writes labels to a separate `labels` table keyed by record id / segment id; only `shiftmate.eval` and simulator tests join them. A test asserts `IntervalRecord` has no `label*` field.
Why: Makes golden rule 5 structural rather than a convention.
Alternatives: Label columns on the record, guarded only by a grep test.

## D-028 — Config files and fields beyond TRD §4
Date: 2026-09-23 · Phase: 1 · Requirement(s): Golden rule 3, TRD §4, §6.6, §6.7, §7
Context: The TRD mentions thresholds for anomaly detection, estimation, simulator productivity, idle confidence and site layout that have no config file or field.
Decision: Added `config/anomaly.yaml` and `config/estimation.yaml` (TRD §6.6/§6.7 values). Added fields: machine profile `tasks` (unit, base rate, truck dependency, typical quantity); site `latitude`, `history_seasons` (D-016), `fleet`, `operators`, `operator_names`, `ground_baseline`, `training_centre`, per-month `rain_mean_mm_h`/`wind_mean_kmh`/`dust_event_prob`/`fog_prob`, truck shortage parameters, worker swing-entry probability; safety rule `category` and `trigger` (level/edge); alert policy timing knobs from DESIGN (ack re-check 3 s, reduced P1 every 5 s, queue re-evaluation 30 s, P1 speech repeat 4 s, P2 tone repeat 20 s, P3 snooze 10 min); idle `params` and per-tier `confidence`. All values are the TRD/DESIGN numbers where given.
Why: No magic numbers in engines; everything validated at start-up.
Alternatives: Constants in code.

## D-029 — Schema additions
Date: 2026-09-23 · Phase: 1 · Requirement(s): TRD §5.2, §5.3, DESIGN Reach
Context: The Reach needs a bearing for the person; fleet ingest needs an idempotency key; anomaly features need the task type and quantity progress per interval.
Decision: `SignalTick.proximity_bearing_deg` (0 = boom forward, clockwise); `IntervalRecord.record_id`, `task_type`, `task_progress_qty`. Operator `personality` is not in the `Operator` model at all (simulator-only type). `ReportDraft.parser` records online/offline.
Why: Needed by later requirements; each is optional so the brief's rows still parse.
Alternatives: Derive bearing in the UI (it has no geometry).

## D-030 — Idle-reason confidences not given by the TRD
Date: 2026-09-23 · Phase: 1 · Requirement(s): F-INS-02, TRD §6.4
Context: TRD §6.4 gives confidences only for WAITING_FOR_TRUCK and HABIT.
Decision: SCHEDULED_BREAK 0.95; WARM_UP 0.9 by coolant, 0.7 time-based (basic); UNATTENDED_RUNNING 0.95 (standard/advanced; not available on basic); UNKNOWN 0.5. In `idle_rules.yaml`.
Why: Honest intelligence: time-based evidence is weaker than a sensor.
Alternatives: A single confidence for all.

## D-031 — Site layouts, climates and fleets
Date: 2026-09-23 · Phase: 1 · Requirement(s): TRD §4.3, §7.1
Context: The TRD gives the Chennai layout for one loading zone and only names the other three sites.
Decision: Chennai keeps the TRD zones and adds DIG-B/DIG-C, LOAD-B/LOAD-C and connecting haul roads so its 24 history machines can load in parallel. Pune, Pilbara and Tromsø layouts, month profiles and truck/worker counts were written to match their descriptions (moderate / extreme heat and dust / sub-zero and dark). Fleet per site: Chennai 12/6/6, Pune 8/3/3, Pilbara 5/7/2, Tromsø 5/2/1 (excavator/loader/dozer) = 30/18/12 and 24/14/14/8 as TRD §7.1; operators 32/19/18/11 = 80. WHL014 falls in Pilbara by numbering order. Operator names are common local names; OP1001 is Ravi Kumar.
Why: The TRD totals are kept exactly; the rest is the simplest consistent choice.
Alternatives: One loading zone per site (would force most Chennai machines into non-truck tasks).

## D-032 — Lesson content choices
Date: 2026-09-23 · Phase: 1 · Requirement(s): F-LRN-01, F-LRN-04, TRD §4.9
Context: The TRD lists the lesson ids and format but not content.
Decision: L-SPOTTER-SIGNALS and L-WALKAROUND are quizzes (3 questions); the drill D-HAZARD-DRILL-1 has 7 scenes (5 hazards + 2 safe scenes, so "correct decisions" includes not stopping); all other lessons are 3–4 narrated cards plus one quiz question. L-WALKAROUND has no automatic trigger (offered from the catalogue). Fuel facts use our profile numbers (idle 3.2 L/h ⇒ about half a litre per 10 minutes) rather than the DESIGN example of "about 1 L", which our model would not support. Hand signals are generic sample content, labelled as such with the knowledge base.
Why: Honest numbers; drills that test decisions, not reflexes only.
Alternatives: All lessons as cards.

## D-033 — Alert text structure
Date: 2026-09-23 · Phase: 1 · Requirement(s): F-SAFE-09, DESIGN §8, §11
Context: DESIGN's P1/P2 layout has a situation line, an instruction and a spoken line with a word budget.
Decision: Each rule's `message_key` points to `{title, action, speak}` in every locale. Reason chips are plain phrases; the minutes effect is added by the UI as a separate value.
Why: One structure serves takeover, banner, strip and speech; no sentence concatenation (TRD §11.4).
Alternatives: One string per alert.

## D-034 — Task duration excludes breaks
Date: 2026-09-23 · Phase: 2 · Requirement(s): TRD §5.1, §6.7, F-SHIFT-02
Context: A task that spans lunch would otherwise count the break as task time, adding up to 30 minutes of pure noise to the estimation label.
Decision: `actual_duration_min` = time from the task's start to its end, excluding scheduled breaks actually taken and engine-off time. Truck waits, pauses and habit idle stay in (they are part of how long the work took). Tasks unfinished at shift end stay `active` with no duration and are not used for training.
Why: Honest labels; the live remaining-time estimate uses the same definition.
Alternatives: Wall-clock start to end.

## D-035 — Load cycle counter signal
Date: 2026-09-23 · Phase: 2 · Requirement(s): D-001, TRD §4.2, §5.2
Context: The brief's "Load Cycles" column exists for every machine, but TRD §5.2 has no tick signal from which to count it.
Decision: Ticks carry `load_cycles_total`, the machine's own cycle counter, added to the basic tier's signal list. Truck loading counts one per truck loaded; dozers count every push; excavators and loaders on tasks without trucks count 25 % of the equivalent passes (`non_truck_load_share`), which gives about 6–7 loads per hour, in line with the brief's sample (12 in two hours).
Why: Keeps the brief's column meaningful on basic machines.
Alternatives: Derive cycles from hydraulic activity in the engine (not how real machines report it).

## D-036 — Ground truth stored per tick
Date: 2026-09-23 · Phase: 2 · Requirement(s): TRD §7.4, golden rule 5
Context: TRD §7.4 labels idle segments and intervals, but intervals are built by the engines later (D-015).
Decision: The simulator writes a truth row per tick under `data/history/truth/` (activity, true idle reason, and one flag per anomaly type), plus operator personalities. Evaluation derives segment and interval labels from these (idle segment: majority true reason over its ticks; interval: anomalous if it contains an anomaly tick of that type).
Why: One ground truth, reusable for any segmentation; nothing label-like is next to the ticks engines read.
Alternatives: Pre-computed interval labels (would bake in one interval boundary scheme).

## D-037 — Simulator scope choices
Date: 2026-09-23 · Phase: 2 · Requirement(s): TRD §7.1–7.3
Context: The TRD leaves many world details open.
Decision: All 42 history days are working days with one day shift per site (no night shifts); darkness appears through Tromsø's polar night. Activity durations are whole ticks (so tick-level invariants hold exactly). Each machine-day draws Poisson episodes (habit idle, short unexplained pauses, stepping out, unbelted work, fuel and productivity anomalies, people approaching), scaled by the operator's traits. Speeding near people is a per-day behaviour of operators with that trait, in travel and in work. The dispatch log is delayed by 0–150 s and misses 3 % of entries (so dispatch-log-based classification is less certain than a sensor). Each site-day has its own seed (`[seed, site, day]`), so sites run in parallel with identical results. Parameters are in `config/simulator.yaml`.
Why: Simplest world that still produces every behaviour the engines must tell apart.
Alternatives: Continuous-time event simulation (harder to explain and test).

## D-038 — Climate tuning
Date: 2026-09-23 · Phase: 2 · Requirement(s): TRD §4.3, §7.2
Context: The first run gave Chennai October afternoons a heat index around 53 °C and rain in over half the hours, which is far wetter and hotter than reality.
Decision: Chennai month profiles set to May 34 ± 5 °C / 58 % RH, September 30 ± 4 °C / 70 %, October 29 ± 4 °C / 76 % with lower hourly rain-start probabilities; humidity falls 3 % per °C above the daily mean. Tuned for plausibility before any model was trained, not against any evaluation result.
Why: Realistic conditions; honest numbers.
Alternatives: Keep the first values.

## D-039 — Rule evaluation semantics
Date: 2026-09-23 · Phase: 3 · Requirement(s): TRD §4.4, §6.2
Context: The TRD defines rule fields but not how sustain, cooldown and missing data behave.
Decision: A tick holds for its period `dt`, so sustain counts `dt` per true tick (a 2 s sustain fires on the second 1 s tick, or the first 30 s tick). Any `None` value used by a rule makes it False (a rule never fires on data it lacks). Level rules raise once per activation and not again within `cooldown_s` of the last raise; edge rules (risk band) raise each time they switch on. All rule expressions are compiled at config load, so a typo fails start-up.
Why: One engine for 1 s live ticks and 30 s history; safe default on missing data.
Alternatives: Treat missing as "unknown → alert" (would raise false alarms on basic machines).

## D-040 — What counts as rest
Date: 2026-09-23 · Phase: 3 · Requirement(s): TRD §6.1, F-SAFE-06, D-006
Context: TRD §6.1 resets continuous operation after "≥ 10 min in a break or engine off" but does not define "in a break".
Decision: Rest = engine off, or idle inside a scheduled break window, or idle after the operator says/taps "start break". Ten minutes of rest (`risk_model.rest_reset_min`) resets continuous operation; waiting for a truck is not rest. `minutes_since_break` is wall-clock time since the last completed rest.
Why: Matches D-006 and how a supervisor would judge a real break.
Alternatives: Any idle ≥ 10 min counts (would make truck waits reset fatigue).

## D-041 — Proximity tier for the risk score
Date: 2026-09-23 · Phase: 3 · Requirement(s): TRD §6.3
Context: The risk score includes the proximity tier, but the tier's distances depend on the risk band (circular).
Decision: The proximity component uses the previous tick's effective distances; the published tier uses the new ones.
Why: Breaks the loop with a one-tick lag, which is invisible at 1 Hz.
Alternatives: Use base profile distances for the score (ignores tightening).

## D-042 — Alert policy details
Date: 2026-09-23 · Phase: 3 · Requirement(s): TRD §6.8, DESIGN AlertQueue / AlertStripP3
Context: Details not fixed by the TRD.
Decision: Alert ids are deterministic (`<machine>-<rule>-<epoch ms>`), no randomness in engines. The ack event records the reaction time. An acknowledged P1 is re-checked 3 s later; if still true it becomes a reduced P1 until cleared. A P3 strip stays until the operator taps Done or Later (Later re-shows it after 10 min if still true); P3s whose condition stopped before the pause go to the feed. Escalation is recorded as an `alert` event with `phase: escalated`, always shared with the supervisor.
Why: DESIGN behaviour, expressed without inventing new event types.
Alternatives: New `alert_escalated` event type (not in TRD §5.4).

## D-043 — One engine pipeline for live and history
Date: 2026-09-23 · Phase: 3 · Requirement(s): TRD §1.1, §6, D-015
Context: History intervals and events must come from the same logic the edge runs live.
Decision: `engines/pipeline.py` chains machine state → risk → safety → (alert policy) → idle reason → interval builder for one machine. `edge/replay.py` feeds it the stored 30 s ticks, the dispatch log and the task list, and writes `intervals.parquet`, `events.parquet` and `idle_segments.parquet`; `shiftmate sim generate` runs it after the simulator. The replay reads the tick period from the history manifest, never from the simulator config (the ground-truth guard enforces this).
Why: One implementation to test and defend.
Alternatives: A separate batch implementation (two copies of the logic).

## D-044 — Interval building details
Date: 2026-09-23 · Phase: 3 · Requirement(s): TRD §5.3, §6.5, D-002
Context: TRD §6.5 says "every 15 machine-minutes and at task start/end".
Decision: Intervals close at wall-clock quarter hours of site time and when the task id changes; intervals with no engine-on time or no operator are skipped. Counters (engine hours, load cycles, task progress) at the end come from the first tick after the interval, because each tick reports its start-of-step reading. Idle minutes by reason use the segment's final reason if it closed within the interval, else its provisional reason at the interval end. Proximity counts are counts of raised proximity alerts.
Why: Exact sums (fuel, engine hours, idling) that invariant tests can check against the ticks.
Alternatives: Fixed 15-minute offsets from engine start.

## D-045 — Idle classification details
Date: 2026-09-23 · Phase: 3 · Requirement(s): TRD §6.4
Context: Some §6.4 conditions need an operational definition.
Decision: "Seat empty for at least 120 s within the segment" is cumulative. "Coolant below ready" is measured at the segment start. "Seat occupied" for truck waits and habit means the seat was empty for less than 120 s, or the seat is not sensed. Machines without a truck sensor use the dispatch log (arrived to departed); a logged arrival without a departure stops counting after 15 minutes (`dispatch_presence_timeout_min`). First match wins, so a truck wait inside a break window is a break.
Why: Simplest reading of the TRD that works on every tier.
Alternatives: Continuous seat-empty runs only.

## D-046 — Anomaly direction and baseline window
Date: 2026-09-23 · Phase: 3 · Requirement(s): TRD §6.6, F-INS-05
Context: TRD §6.6 says "|z| at least 3". Unusually low fuel or high productivity is not a problem to flag.
Decision: Each feature has a "worse" direction (`higher_is_worse` in `anomaly.yaml`; only loads per working hour is lower-is-worse). The z-score test and explanations use the worse direction only. The 14-day baseline window ends at the start of the interval's day. Features missing for a tier are dropped, never filled in.
Why: Coaching points must describe a real problem; no self-comparison within a day.
Alternatives: Two-sided |z|.

## D-047 — Lesson recommender scoring and offers
Date: 2026-09-23 · Phase: 3 · Requirement(s): TRD §6.9, F-LRN-02, F-LRN-03
Context: TRD §6.9 says "trigger count × recency" without a formula.
Decision: score = sum over the lesson's triggers of count / (1 + days since last seen), from events in the last 7 days; top 3; lessons completed in the last 3 days are skipped. Offers happen only when a pause starts that is expected to be long (waiting for a truck, scheduled break, engine off), at most once per pause and once every 30 minutes. Condition flags (HEAT, RAIN, WET_GROUND, NIGHT) count when that condition scores risk points. Parameters live in `lessons.yaml` under `recommender`.
Why: Simple, explainable, and never offers during work.
Alternatives: Exponential decay with a tuned half-life.

## D-048 — Offline report parser
Date: 2026-09-23 · Phase: 3 · Requirement(s): TRD §6.10, F-REP-01
Context: Keyword classification needs an order and a default.
Decision: Keywords from all three languages are matched together (operators mix languages). Type order: near miss, then incident, then equipment problem ("almost hit" is a near miss); nothing matched gives near miss. Severity: high on injury or fire words, medium on people, damage or near-miss words, else low. The summary is the transcript (offline mode cannot translate); the operator confirms or edits every draft.
Why: Safe defaults; a person confirms.
Alternatives: Language-specific matching only.

## D-049 — Simulator realism fixes found by the engine replay
Date: 2026-09-23 · Phase: 3 · Requirement(s): TRD §7.2
Context: The first replay showed about 23 caution alerts per machine per day, and speed-near-person alerts ten times the true episodes: wandering workers walked through working zones, and simulated operators only slowed down inside the base caution ring.
Decision: Wandering ground crew pick targets at least 20 m from running machines and step back outside 14 m; deliberate approach episodes still bring people close. Operators slow down once a person is within 1.5 times the caution distance, and speeders do not. These change the simulated world only, not any engine or threshold, and were made before any model was trained or evaluated.
Why: A realistic site; alerts that mean something.
Alternatives: Lower the engines' sensitivity (would hide real events).

## D-050 — Evaluation investigation: three simulator bugs fixed
Date: 2026-09-23 · Phase: 4 · Requirement(s): CLAUDE Phase 4 DoD, TRD §7.2, §7.4
Context: The first evaluation missed the idle-reason target on advanced machines (89.6 % against 90 %), and 253 true "warm-ups" were classified "Not sure". Per CLAUDE.md, one investigation, genuine bugs only.
Decision: The misses were 60 s idles right after a 15-minute engine-off break, when the coolant was still above the ready temperature; the simulator labelled them warm-up because its day flow always passed through a warm-up step after boarding. Three genuine simulator bugs were fixed: (1) warm-up only happens when the coolant is below the ready temperature (a warm engine goes straight to work); (2) coolant cools to air temperature overnight (it used to carry yesterday evening's temperature into the morning); (3) the speed-near-person truth flag uses the documented definition, a person within the profile's caution distance (D-049 had accidentally widened it to 1.5 × caution). No engine, threshold, feature or model setting was changed, and nothing was fitted to test days. Regression tests cover (1) and (2). After regenerating: idle accuracy advanced 96.1 %, standard 91.8 %, basic 83.3 %; anomaly precision 67.2 %, recall 41.8 %; estimation median error 10.5 %, p10–p90 coverage 64.5 %. Using a single-machine group as a "fleet pattern" was also stopped (at least 3 machines).
Why: Truth labels must follow the world's own rules; honest numbers.
Alternatives: Loosen the engine's warm-up rule to match the old labels (would be tuning to the test data).

## D-051 — Targets still missed after the investigation (reported, not tuned)
Date: 2026-09-23 · Phase: 4 · Requirement(s): PRD §10, golden rule 11
Context: After D-050, three targets remain unmet: anomaly precision (67 %) and recall (42 %) against 80 %, estimation coverage (64.5 % against 75–85 %), and the TRD's mean-error figure (13.8 % against 12 %; the PRD's median error, 10.5 %, is met).
Decision: Report them as measured, with causes, and change nothing. Causes: (a) Anomaly recall is capped by the TRD rule itself: the model may flag only its top 5 % of intervals while about 10 % of test intervals are truly anomalous; habitual behaviour is part of an operator's own baseline, so it is not "unusual" for them; machines without proximity or seat sensors cannot see speeding near people or an empty cab; abnormal fuel and low productivity are diluted in whole-interval features. (b) Anomaly precision loses to P1 safety rules (e.g. a worker entering the swing radius, which is not an operator anomaly in the labels) and to IsolationForest-only flags. (c) The estimation range is too narrow on validation too (66 %), a known property of quantile regression under shift; truck-loading tasks are the least predictable (truck supply). Options for the owner, not applied: calibrate the p10/p90 range on the validation days (conformal adjustment, no test data used); make the model's flag rate match the anomaly prevalence (contamination) or add task-progress-rate features; restrict the hard rule to operator-controlled P1 rules. Each would change TRD-specified behaviour, so each needs the owner's decision.
Why: CLAUDE.md: fix genuine bugs once, then report honestly.
Alternatives: Tune thresholds until the targets pass (forbidden).

## D-052 — Background machines run in the world only
Date: 2026-09-23 · Phase: 5 · Requirement(s): TRD §1.1, §8, F-FLT-03
Context: The live site has the focus machine (Ravi's EXC001) plus background machines for the map, trucks and workers. Running a full `MachineRuntime` (all engines, estimation, anomaly, alerts, store) for every machine at 1 s ticks is not needed for any demo beat.
Decision: Only the scenario's focus machine runs a `MachineRuntime`. Background machines are simulated in the world (position, state, trucks, workers) and appear on `/machines` and the map, but produce no engine events at the edge. Fleet-wide numbers come from the history replay and the fleet service.
Why: Every PRD beat is about the cab of one machine; keeps the live loop fast (about 1,300× real time) and deterministic.
Alternatives: A runtime per machine (slower, more events nobody sees in the cab demo).

## D-053 — A lesson about the current pause is offered first
Date: 2026-09-23 · Phase: 5 · Requirement(s): F-TRAIN-02, TRD §6.9
Context: The recommender ranks lessons by the operator's recent history. During a pause, a history-ranked lesson can outrank one about what is happening right now (e.g. waiting for a truck, engine off before stepping out).
Decision: When the offer happens during a pause with a known provisional reason, lessons whose triggers include that reason (and were not completed recently) are placed first; the history-ranked list follows without duplicates. Nothing is offered while working (unchanged).
Why: PRD principle — the right help at the right moment; supports the truck-delay and step-out beats (CLAUDE Phase 12 DoD).
Alternatives: Add a large weight to the scoring formula (hides the rule inside numbers).

## D-054 — Estimate reasons are what-if effects on recognisable conditions
Date: 2026-09-23 · Phase: 5 · Requirement(s): F-SHIFT-03, TRD §6.7
Context: Using raw `pred_contrib` for every feature produced reasons operators cannot act on or recognise ("machine faster", "site slower", "time of day") and mixed up direction for categorical features: contributions are relative to the training average, not to a normal day.
Decision: Only recognisable conditions are reasons (`reason_keys` trimmed: ground, rain, heat, night, operator skill/experience, quantity, truck supply). Where a natural reference exists (`reference_values`: dry ground, no rain, daytime, 30 °C, average operator), the effect is the p50 now minus the p50 with that condition at its reference. Ground reasons name today's ground (`reason.ground_wet_slower`, …). Quantity and truck supply keep the `pred_contrib` effect. Under one minute: no chip. The model and its evaluation are unchanged; this only affects the explanation.
Why: Honest, understandable reasons ("Wet ground adds time: +15 min").
Alternatives: SHAP values against a background set (heavier, same idea); keep all features (confusing chips).

## D-055 — Demo PIN is the operator number
Date: 2026-09-23 · Phase: 5 · Requirement(s): F-START-01, D-010
Context: D-010 adds a PIN fallback to the QR badge, but PRD §3 excludes login systems, so there is no PIN store.
Decision: The demo PIN is the numeric part of the operator ID (OP1001 → 1001). A wrong PIN returns 401 "That PIN didn't match." It is documented as a demo convenience, not security.
Why: No login system (non-goal); easy to demonstrate; still exercises the fallback flow.
Alternatives: PINs in config (adds a credential-looking file for no benefit).

## D-056 — Edge ingest endpoints, extra channel message types and the telemetry throttle
Date: 2026-09-23 · Phase: 5 · Requirement(s): TRD §9.1, §9.2, §9.3, F-REP-04, F-CAB-04
Context: TRD §9.2 lists only `/ingest/intervals` and `/ingest/events`, but the edge also queues saved reports and finished task summaries (both allowed by `privacy.yaml → fleet_upload`). TRD §9.1 names the main cab and site messages but not how a client resynchronises or learns demo state. At 60× the world produces up to 60 telemetry ticks per real second.
Decision: The outbox posts four kinds, each as `{source, records}`: intervals → `/ingest/intervals`, events → `/ingest/events`, reports → `/ingest/reports`, task summaries → `/ingest/tasks`; the fleet ingests idempotently by the record's own id (`record_id`, `event_id`, `report_id`, `task_id`). Extra message types: `snapshot` (full state, first on connect and after load or seek; it replaces any messages queued before it), `session`, `demo` (captions, waits, seek, end of shift), `alert_queued` and `alert_feed` from the alert policy. `telemetry` is sent at `edge.yaml → feeds.telemetry_hz` (latest value wins) and provisional idle-segment updates are coalesced; everything else is sent in order, every time.
Why: Reports and task summaries are what the supervisor and the fleet estimation model need (F-SUP, F-FLT-05); snapshots keep a reconnecting screen from showing stale data (golden rule 6); a screen cannot use 60 telemetry messages a second.
Alternatives: Send reports as events (loses the draft and context); send every tick (floods the socket at demo speeds).

## D-057 — A truck wait is a site issue, anonymous and attributed to the site
Date: 2026-09-23 · Phase: 5 · Requirement(s): PRD P-04, F-INS-03, PRD §9 beat 4
Context: The supervisor must see truck shortages (PRD §9 beat 4), but P-04 says waiting caused by the site must never count against the operator.
Decision: While a WAITING_FOR_TRUCK segment is open, the site map gets a live `site_event` (`site_issue`, status `open`, machine and zone, no operator). When the segment closes, the edge records a shared `site_issue` event with `operator_id` null (start, end, minutes, zone) and the cab gets the insight "not you". If the wait ends without being classified as a truck wait, a `cleared` site_event withdraws the notice.
Why: The supervisor learns about dispatch problems without any operator being named (P-04).
Alternatives: Share the operator's idle segment (names the operator); report only at the end of the shift (too late to act).

## D-058 — Equipment problems get their own event type
Date: 2026-09-23 · Phase: 5 · Requirement(s): F-REP-01, F-START-03
Context: Checklist problems and spoken equipment reports were logged with event type `incident`, which inflated safety counts and was shared as if someone had been hurt.
Decision: New `EventType.EQUIPMENT_PROBLEM` (and `SITE_ISSUE`). A saved report records an event of its own draft type (incident, near_miss or equipment_problem). Incidents and near misses are shared with the supervisor; equipment problems are not shared as events, but the report itself still uploads (it goes to maintenance through the fleet).
Why: Honest safety numbers; the right people see the right report.
Alternatives: Keep `incident` with a sub-type in the payload (every consumer has to remember to filter).

## D-059 — API models are exported to the frontend contracts
Date: 2026-09-23 · Phase: 5 · Requirement(s): CLAUDE.md §4 (types only from contracts), TRD §9
Context: Milestone 7 added the REST models in `schema/api.py` but did not add them to the JSON Schema export, so the frontend would have had to hand-write API types (forbidden).
Decision: `schema/__init__.py` appends every pydantic model defined in `schema/api.py` (including the WebSocket envelope and payload models) to `EXPORTED_MODELS`; the contracts are regenerated and `pnpm contracts:check` guards them.
Why: One source of truth for every type that crosses the network.
Alternatives: List the models by hand (easy to forget one again).

## D-060 — The headless run reports an equipment problem while offline
Date: 2026-09-23 · Phase: 5 · Requirement(s): PRD §9 beat 10, F-REP-04, CLAUDE.md Phase 5 DoD
Context: The Phase 5 DoD asks that "network off → outbox grows". In the scenario, only one record (a 15-minute interval) closes during the 8 minutes offline, and PRD §9 beat 10 says "reports queue" — something the operator does, not a scripted beat.
Decision: The headless driver (`edge/headless.py`) acts as Ravi: it signs in at the sign-in wait, speaks a near-miss report at the near-miss wait, and, once the internet is off, speaks one equipment-problem report through the same REST calls as the cab. The test checks the outbox grows while offline, that report reaches the fake fleet after reconnecting, and the outbox drains to 0. The scenario file is unchanged.
Why: Shows exactly what F-REP-04 promises (reports work offline and sync later) with a real report, not only a background interval.
Alternatives: Add a scripted report beat to the scenario (changes what the judges see); rely on the interval alone (a weak check).

## D-061 — A downloaded model becomes LATEST only after it loads
Date: 2026-09-23 · Phase: 5 · Requirement(s): TRD §6.7 publishing, F-FLT-03
Context: The model downloader wrote the cache's `LATEST` pointer before loading the new model. A broken download therefore stayed "latest" on disk, and at the next start the loader (which only caught missing files) would fail on the unreadable booster.
Decision: The edge loads the downloaded version first and writes `LATEST` only on success; at start, any error loading the cache (or the bundled model) falls through to the next source, and without any model estimates are simply off (the cab says so). Report uploads now also carry `report_id`, `operator_id` and `machine_id`, which the fleet needs for idempotent ingest.
Why: Estimates must never depend on the network or on a bad download (TRD §9.3); the edge must always start.
Alternatives: Verify checksums in the manifest (useful later, but still needs the load check).

## D-062 — The fleet store is seeded with the history the edges uploaded
Date: 2026-09-23 · Phase: 6 · Requirement(s): TRD §9.2, F-SUP-02…05
Context: The Fleet Service starts empty, but the supervisor views need weeks of site data (trends, similar days, baselines), and in the real product the fleet would have received those summaries over time.
Decision: A new, empty fleet store (`data/fleet/fleet.duckdb`) loads the simulated history exactly as the edges would have uploaded it: the edge-replay intervals, the events the edge shares (shared, or incident / near miss), and task summaries — tagged `source = history`. Ground-truth files are never read. Live uploads (Ravi's day) are added on top through the normal ingest endpoints. `fleet.yaml → ingest.seed_from_history` turns this off; tests start empty.
Why: Honest (only what edges send), simple, and the demo's supervisor views have real depth.
Alternatives: Replay the history through HTTP ingest at start (slow, same result); leave the fleet empty (no trends or suggestions).

## D-063 — On-track and behind: the fleet's usual pace for that task on that machine type
Date: 2026-09-23 · Phase: 6 · Requirement(s): F-SUP-02
Context: The PRD asks for on-track/behind indicators but does not define them. A first version used one pace per task type, which flagged nearly every excavator as behind, because dozers clear ground far faster.
Decision: Expected duration = planned quantity × the fleet median minutes per unit of finished tasks of the same task type on the same machine type over the previous 14 days (task type alone if fewer than 5 such tasks). An active task is *behind* if the time since it started exceeds the time its progress should have taken × 1.15 + 10 min (fleet.yaml), otherwise *on track*; finished tasks are *done*, unstarted ones *not started*, and without a baseline *unknown*. A machine shows its worst task. For a finished day this is an end-of-day view: tasks still open at the end of the shift are mostly the slow ones and show as behind.
Why: Simple, explainable ("slower than the fleet usually is at this"), comparable like with like; thresholds in config.
Alternatives: The estimation model's p90 per task (needs operator features the fleet should not use for a supervisor view); planned finish times (the simulator has none).

## D-064 — Where time is lost: lead reason and the add-a-truck suggestion
Date: 2026-09-23 · Phase: 6 · Requirement(s): F-SUP-03, PRD P-04, DESIGN IdleCausesBreakdown
Context: DESIGN shows one suggestion with a range and its basis ("Add one truck to LOAD-A, 10:00–12:00 · would likely save 1 h 30 m – 2 h 10 m · based on 3 similar days") without saying how it is computed.
Decision: The lead is the largest *explained* lost-time reason (truck waits, short-stop habit, unattended running); breaks and warm-up are needed time and "not sure" stays in the table. The truck suggestion picks the zone (from the task being worked) and the 2-hour window with the most truck waiting today (≥ 20 min). Its range is the 25th–75th percentile of the truck waiting in that zone and window on today plus the similar days of the last 14 (days with ≥ 20 min there) — the most one more truck could have recovered; "based on N similar days" is that count, and with fewer than 2 days there is no range. Other suggestions: a toolbox talk on idling (≥ 15 min of short stops per active machine, lesson L-IDLE-FUEL) and a shutdown briefing (≥ 5 min unattended running, L-SHUTDOWN). The API returns keys and numbers; the console (milestone 13) words them in three languages. The view never names operators (P-04).
Why: Every number traces to uploaded waits; nothing is invented; the wording stays honest ("likely save" up to the waiting observed).
Alternatives: A queueing model of trucks (not supported by the data the fleet has).

## D-065 — Task summaries are sent when a task starts and when it ends
Date: 2026-09-23 · Phase: 5–6 · Requirement(s): F-SUP-02, privacy.yaml task_summaries
Context: The edge queued a task summary only when a task finished, so the fleet could not show today's active task (its plan, zone and progress).
Decision: The edge also queues the summary when a task becomes active. The fleet upserts tasks by `task_id`, keeping the most advanced status (scheduled → active → done, never backwards), and computes progress from the interval summaries' `task_progress_qty`.
Why: The supervisor sees today's work while it happens; still only task summaries leave the machine.
Alternatives: A separate "plan" upload (a second path for the same data).

## D-066 — Scale mode resamples real summaries; the projection uses the runtime footprint
Date: 2026-09-23 · Phase: 6 · Requirement(s): F-FLT-07, TRD §7.6
Context: TRD §7.6 asks for a lightweight statistical generator for 10,000 machines but gives no distributions, and the projection formula needs per-machine bytes and records.
Decision: `sim scale` gives each synthetic machine a stretch of real interval summaries (and the shared events in it) from a random history machine, re-labelled (`SX00001…`, sites `SCALE-<country>`, `source = scale`) and moved to now, posted in time order in batches of 500 through the real ingest endpoints. Synthetic machines never appear in real site views. Ingest throughput is records ÷ time spent inside requests (one sequential client), so generating records does not count. The projection uses the runtime benchmark's upload per machine-hour when available (real `MachineRuntime` output), else the scale run's, × 24 h × 1.6 M, and is always labelled "projection" with its basis. `bench runtime` feeds several runtimes the ticks of the same simulated machine to reach 200. Both write `data/fleet/scale.json` and the EVAL.md scale section.
Why: No invented numbers; realistic payload sizes and event rates; clearly separated measurement and projection (golden rule 11).
Alternatives: A parametric generator (needs made-up distributions); counting generation time in throughput (understates ingest).

## D-067 — Today's site views show the machines that upload today
Date: 2026-09-23 · Phase: 6 · Requirement(s): F-SUP-02…04, D-052
Context: In the live demo only the focus machine runs a MachineRuntime (D-052), so for the demo day the fleet receives data from EXC001 only; the other 23 Chennai machines appear in the day summary without tasks.
Decision: Accept this: the summary lists every machine on the site roster, and those with no uploads today show as not started with no hours. Site views default to the latest day with data; the console can pick earlier days, which have all machines (history).
Why: Honest — the fleet only shows what machines sent (golden rule 6: never fake data). Running runtimes for every background machine would slow the live demo.
Alternatives: Fill today from the history generator (fake data for the live day).

## D-068 — Tamil and Hindi status rail: wrap, and drop repeated details
Date: 2026-09-23 · Phase: 7 · Requirement(s): DESIGN §3, §10 StatusRail, review row 11; PRD §5 principle 7
Context: With a queued alert, items waiting and the machine segment, the Paused rail in Tamil was about 330 px wider than 1280 px; letting segments shrink made words overlap.
Decision: In Tamil and Hindi, rail labels step down to 24 px and wrap to two lines within a 7 em budget (DESIGN §10 StatusRail). The machine's state word is dropped (its glyph carries the state as its accessible label). In Tamil only, the risk reason is dropped from the rail (as in the DESIGN review; the risk line carries it) and, as in the 1024 × 768 layout, the machine segment is hidden; the cab app shows the machine ID in the Paused content header instead. Segments never shrink below their content.
Why: Wrap, don't truncate, never overlap; Tamil first (DESIGN principle 7); the same drops DESIGN already made for Tamil and for the smaller screen.
Alternatives: Shrink Tamil below 24 px (forbidden); ellipsis (forbidden on safety strings).

## D-069 — Components carry no words; a component layer next to the delivered tokens
Date: 2026-09-23 · Phase: 7 · Requirement(s): golden rules 9 and 10, DESIGN "Using this system"
Context: tokens.css is the delivered design file. Components need a few things tokens alone do not give (the Sunlight/Night weight shift, script line-heights, the hatch, idle patterns, motion, focus ring), and every visible word must exist in three languages.
Decision: `packages/ui/src/ui.css` (imported after tokens.css) holds that layer; tokens.css is not edited. Components take every word through props, so apps translate with `t()` and the same component renders in en, hi and ta; the design vocabulary (rail words, navigation, push-to-talk states, buttons, states) is in the i18n files under `ui.*` (165 keys, DESIGN §11 lines used as written). Glyph strokes use `vector-effect: non-scaling-stroke`, so the stroke stays at `--sm-icon-stroke` at every size.
Why: One source of visual truth; no hard-coded English in shared components; the design file stays diffable against its source.
Alternatives: Default English labels in components (breaks golden rule 10 silently); editing tokens.css (loses the link to its generator).

## D-070 — How "tokens only" and "no overflow" are enforced
Date: 2026-09-23 · Phase: 7 · Requirement(s): CLAUDE.md Phase 7 DoD
Context: The DoD asks for a lint rule or test banning hex and font literals outside packages/ui, contrast checks, and a kitchen sink without overflow in 3 themes × 3 languages.
Decision: A vitest test scans `frontend/apps/**` for hex/rgb/hsl colours, font names, raw px values and shadow literals (a line may opt out only with a `token-exempt` comment, which review must see). Another recomputes every contrast pair of DESIGN §2 from tokens.css in all three themes against the DESIGN §12 targets (90 checks). A Playwright test opens `/_kitchen-sink` in the installed Chrome and, for each theme × language, fails if any element in a 1280 px cab frame sticks out of the frame or has content wider than its own box (the push-to-talk listening ring grows on purpose and is skipped). jsdom tests cover roles, labels and missing translations.
Why: Automatic and repeatable; layout can only be judged in a real browser.
Alternatives: A custom ESLint rule (more code for the same result); screenshots checked by eye only.
