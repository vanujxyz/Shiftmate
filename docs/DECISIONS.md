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

## D-071 — Status rail short forms: stale age, sync count, 1024 × 768 drops
Date: 2026-09-24 · Phase: 8 · Requirement(s): DESIGN §4 Cab grid 1024 × 768, §10 StatusRail; F-CAB-03
Context: In the live cab, with stale data, raised risk and reports waiting, the rail was wider than the screen: by 4 px in English at 1280 px, and by up to 90 px in Tamil at 1024 px. The clock was pushed off the screen.
Decision: The rail always draws the stale mark as the dashed square plus the age ("40 s"; in minutes, "4 min", from 2 minutes on). The full sentence ("No update 40 s") is its accessible name and is written out on the Safety screen. In Tamil and Hindi, and in any language below 1280 px, the sync segment shows only the count beside the mast glyph, which keeps the full words as its label. Below 1280 px the machine segment is dropped in every language (DESIGN §4) and Tamil/Hindi rail words wrap at 5.5 em. The Hindi risk reason is dropped at every width, as the Tamil one already is (D-068); the Safety screen names it. The proximity word keeps its tier glyph on one line. The bottom nav's push-to-talk cell is 220 px below 1280 px (DESIGN §4), so Tamil tab labels fit.
Why: Nothing in the rail may be cut or pushed off the screen. The dashed mark carries "stale" on its own, and the full words stay available.
Alternatives: Shrinking text below 24 px (forbidden); an ellipsis (forbidden on safety strings); dropping the stale mark (hides stale data).

## D-072 — The cab snapshot carries the risk breakdown
Date: 2026-09-24 · Phase: 8 · Requirement(s): F-SAFE-04, TRD §9.1
Context: `risk_update` is only sent when the score moves by 3 or more or the band changes, so a cab that reconnected had a risk band but no "what raises it" until the next change.
Decision: `CabSnapshot.risk` holds the last risk payload (score, band, top contributors, thresholds), built by the same `MachineRuntime.risk_payload` as `risk_update`.
Why: A reconnect never leaves the Safety screen half-empty; a single function builds both.
Alternatives: The cab fetches the risk over REST after connecting (a second path to keep in step).

## D-073 — The P1 takeover's acknowledge button is always on screen
Date: 2026-09-24 · Phase: 8 · Requirement(s): F-SAFE-09, DESIGN §10 AlertTakeoverP1
Context: In Tamil the real "Person inside the swing zone" P1 wrapped to four lines at 72 px and pushed "I've stopped" below the bottom of the screen. The kitchen-sink test only checked horizontal overflow.
Decision: The message sits in a region that may shrink; the acknowledge button and queue line are fixed below it. The situation line is 72/80 in English and 52 px in Tamil and Hindi (instruction 40 → 32 px), so the whole message fits at 1280 × 800. The kitchen-sink e2e now fails if a P1 message is cut or its button leaves the takeover.
Why: A P1 that cannot be acknowledged is a safety defect. Script-aware sizes follow DESIGN §3.
Alternatives: Scroll the whole takeover (the button could still scroll away); cut the text (forbidden).

## D-074 — P3 strip action: "Done" for notices, "Later" for advice
Date: 2026-09-24 · Phase: 8 · Requirement(s): DESIGN §10 AlertStripP3, alert_policy.yaml
Context: DESIGN gives a P3 strip one optional action, either "Later" (snooze 10 min) or "Done" (clear), without saying which. A risk-band notice stays on the strip after the band drops, since the edge keeps P3 strips until acted on or replaced.
Decision: Strips in the `risk` category offer "Done" (the edge files the strip to the feed); all other strips (fatigue, heat and water breaks) offer "Later".
Why: Advice with time to act can be snoozed; a notice only needs to be seen.
Alternatives: Always "Later" (a stale risk notice keeps coming back).

## D-075 — Sign-in flow on the cab
Date: 2026-09-24 · Phase: 8 · Requirement(s): F-START-01…04
Context: The Start screen must work before the edge answers, and it must not reveal which operator IDs exist.
Decision: The language choice comes first and always shows; the edge's state (checking, not reachable, no shift loaded) is said under it in the chosen language. Badges read `SHIFTMATE:OP####` (jsQR, camera stays on the tablet); with no camera or no permission the PIN pad opens with a note. The PIN is the operator number (OP1001 → 1001); an unknown operator reads exactly like a wrong PIN. Digits are tracked synchronously, so two quick glove taps both count. The checklist needs an explicit OK or Problem per item ("All OK" fills the rest); problems become reports on the edge.
Why: Tamil-first operators read the error in Tamil; no user enumeration; glove-proof input.
Alternatives: Show the language picker only once the edge is up (the old smoke test's flow).

## D-076 — Cab session and edge authority
Date: 2026-09-24 · Phase: 8 · Requirement(s): F-START-03, F-CAB-01
Context: A reload should keep the operator signed in, but the edge decides who is at the controls (a new scenario load or another sign-in replaces the session).
Decision: The cab keeps `{operator, machine, name}`, language, theme and "read alerts aloud" in localStorage (every access guarded). When a snapshot says a different operator, or that nothing is loaded, the cab signs out locally and returns to /start. Going to Working mode is immediate unless a finger is already down, and then it waits for the press to end (DESIGN ModeTransition).
Why: A reload doesn't cost a sign-in, but stale sessions can't survive a replaced world.
Alternatives: sessionStorage only (a reload of the tablet loses the session); no edge check (a demo reload keeps showing the previous operator).

## D-077 — What the tablet keeps, and reports that can't reach the gateway
Date: 2026-09-24 · Phase: 8 · Requirement(s): F-CAB-04, F-REP-04, P-01; TRD §11.2 Offline
Context: The edge already queues everything for the fleet while the site has no internet. The cab also has to work when the gateway itself is unreachable (a Wi-Fi drop in the cab, or a restart), and TRD asks Dexie to keep the profile, shift, pending reports and last insights.
Decision: `offline/db.ts` holds three tables: `cache` (the last good copy of the shift, config, insights and reports), `drafts` (the report being written, restored on reload) and `pending` (confirmed reports the gateway did not receive). If IndexedDB is missing or fails, the same calls work in memory. Queries fall back to the kept copy only on a network failure. An answer the gateway did send, even an error such as the 403 for someone else's My Day, is never replaced. Pending reports are sent oldest first whenever the socket reconnects. They carry no context, so `ReportSaveRequest.context` is now optional and the edge fills time, place, task and weather when the report arrives. Signing out deletes that operator's cached My Day from the tablet.
Why: Nothing the operator confirmed is lost, screens never go blank, and private insights don't outlive the session on a shared tablet.
Alternatives: Keep everything in react-query memory (lost on reload); stamp the tablet's own place and time (the tablet has no position; the gateway is the source of truth).

## D-078 — Typed and tapped report flow
Date: 2026-09-24 · Phase: 8 · Requirement(s): F-REP-02, F-REP-03, F-REP-05
Context: Voice reports arrive in milestone 15. The typed/tap flow must end in the same draft and must work with gloves.
Decision: Three big type buttons (near miss, incident, machine problem), then a few typed words, then "people involved" and "anyone hurt" as Yes/No. "Check this" sends the words to `/reports/parse` for context and severity. Explicit taps always win over parser keywords, and with no words typed the English summary stays empty (the parser saw only the type's name). Where and when is shown but not editable, since the gateway fills it. Type, severity, people and the words can be changed with big buttons. Send and Delete sit at opposite ends. The recent-reports list shows each report's state: on this tablet, waiting for internet, or sent to the office.
Why: Honest, correctable drafts; the operator's own answers are authoritative (golden rule: never fake data).
Alternatives: Trust parser keywords over taps (a "no" tap could be overridden by a word like "worker").

## D-079 — My Day presentation
Date: 2026-09-24 · Phase: 8 · Requirement(s): F-INS-06, F-INS-07, F-INS-08; TRD §11.2 /insights
Context: The edge's time split has `working`, `travel`, `engine_off` and idle-reason pieces (27 on the demo day), plus one row per idle segment with evidence codes.
Decision: The route is `/insights`, as in the TRD; the tab is still called "My day". Moving counts as working in the time-split bar, and neighbouring pieces of one kind are drawn as one. Stops are grouped by cause, longest total first, with the evidence of that cause's longest stop in plain words (the cause, never the person; e.g. "No truck at the loading point"), the number of stops and the fuel used. Truck waits carry the line "a site delay, not your idle time". The page shows fuel per load against the operator's usual, fuel used while stopped and fuel used today, up to two "went well" notes and up to two ideas. Unit codes inside notes ("loads") become words in the operator's language. The week view is a table of earlier days. The page says it is private.
Why: Readable at a glance; fair to the operator; nothing appears in English inside Hindi or Tamil.
Alternatives: One row per idle segment (27 rows); a separate `/day` route (differs from the TRD).

## D-080 — The cab is an installable PWA; offline is tested in Chrome
Date: 2026-09-24 · Phase: 8 · Requirement(s): F-CAB-04, TRD §11.2 Offline
Context: The cab must open with no network. The preview browser used for manual checks does not allow service workers.
Decision: vite-plugin-pwa (`generateSW`, auto-update) pre-caches the app shell, CSS, JS (with the bundled locale strings) and every Anek font subset (15 files, about 2 MB). Every route falls back to the shell. The manifest and icon are static files in `public/`, so their colour values stay outside app code (the tokens-only rule). `e2e/offline.spec.ts` builds and serves the PWA, lets the worker take control, turns the network off in Chrome, reloads, and checks that the app opens, switches to Tamil and has the Tamil font loaded.
Why: A real, repeatable offline check instead of a manual one.
Alternatives: Run the service worker in dev mode (differs from production).

## D-081 — The console site map
Date: 2026-09-24 · Phase: 9 · Requirement(s): F-SUP-01, DESIGN §9 Site map symbology, §10 ConsoleSiteMap
Context: The map must show machines, trucks and people moving, with swing zones coloured by proximity state, at 30 fps or more, from 5 Hz entity updates.
Decision: `ConsoleSiteMap` lives in `packages/ui`, where its fixed drawing sizes belong. It uses a fixed 0.45 m per pixel: the map scrolls and never squashes. North is up, world +y is north, and headings run clockwise from north, as in the simulator. Rings are drawn from the thresholds each machine reports. The tier sector points at the nearest tagged person inside the rings, with the hatch only for critical. The console draws the map one update behind and glides between the last two updates on every animation frame; 68 fps was measured in the browser. A seek jumps without gliding. Selecting a machine shows its model, sensors, operator, nearby tier, warning rings and its day from the Fleet Service. There are no action buttons: "send a truck" and "voice note" stay removed (owner decision).
Why: Smooth, honest motion; one drawing vocabulary shared with the cab; tokens-only app code.
Alternatives: A canvas renderer (loses accessible machine buttons); drawing positions as they arrive (visible 5 Hz jumps).

## D-082 — Two small gateway endpoints for the console
Date: 2026-09-24 · Phase: 9 · Requirement(s): TRD §11.3 /site, /demo
Context: The console needs the loaded site's plan (zones, roads) and the list of loadable scenarios; neither was exposed.
Decision: `GET /site/layout` returns the site id, name, time zone, focus machine and layout (409 when nothing is loaded). `GET /demo/scenarios` returns each scenario's name, title (en/hi/ta), site and focus machine.
Why: The console draws from the gateway's own configuration; nothing is duplicated in the frontend.
Alternatives: Bundle the site YAML into the console (two copies that could disagree).

## D-083 — The contracts generator kept fields called `title`
Date: 2026-09-24 · Phase: 9 · Requirement(s): TRD §5 contracts
Context: `gen.mjs` strips pydantic's per-field `title` annotations. It also deleted any field actually named `title` from a model's `properties`, so `Lesson.title`, `LessonSummary.title` and `ScenarioInfo.title` had been missing from the TypeScript types.
Decision: The stripper now walks into each field's schema instead of deleting keys from the `properties` map. Contracts are regenerated; `contracts:check` passes.
Why: Types must match the API exactly (golden rule: contracts are generated, never hand-written).
Alternatives: Renaming the fields (changes the API to work around a tool bug).

## D-084 — The console frame, day summary and fleet pages
Date: 2026-09-24 · Phase: 9 · Requirement(s): F-SUP-02…05, F-FLT-07, F-FLT-08
Context: The console should work in three languages, show which data is simulated, and respect privacy.yaml.
Decision:
- **Frame:** a 64 px top bar with the five sections and the language (kept per browser), and the dashed "Demo mode · simulated data" strip on every page. The default site is the one live on the gateway.
- **Day summary:** offers the fleet's days for the site, newest first. The latest is the default (D-067).
- **Where time was lost:** leads with one sentence naming the cause, never the operators. It shows the fleet's primary suggestion with its saving range and basis.
- **Safety:** lists critical alerts with the operator's name, since they are safety-critical events (F-SUP-05), in the site's local time. Warnings are grouped by kind.
- **Team trends:** groups only, with groups under the privacy minimum hidden.
- **Fleet page:** keeps what was measured (live ingest, the simulated 10,000-machine run, the runtime benchmark) visually apart from the dashed, labelled projection to 1.6 million machines.
- **Evaluation page:** reads docs/EVAL.md at build time through a small Markdown reader that never renders HTML from the file.
Why: Supervisors see where time goes and what to do, without ranking people; no projection can pass as a measurement.
Alternatives: Operator-level tables for supervisors (breaks P-02/P-03).

## D-085 — Retrieval scoring: a lexical match must cover the question
Date: 2026-09-24 · Phase: 10 · Requirement(s): TRD §10.2, §10.4
Context: With BM25 normalised by the best score for each query, any chunk sharing a single word with an off-topic question ("the price of a new bucket") got full lexical marks. It reached the 0.55 offline bar and would have been returned as an answer.
Decision: The lexical part is the max-normalised BM25 times the share of the query's IDF weight that the text contains. Words the knowledge base never uses count at the highest IDF. The dense part and the 0.5/0.5 weights stay as in the TRD, and the offline bar stays at 0.55. This was decided from the knowledge base alone, before the first evaluation run, and nothing was tuned on the evaluation set.
Why: Off-topic questions now score 0.12–0.31 against 0.45–0.62 for real ones. Offline mode refuses rather than returns a wrong passage.
Alternatives: Raising the offline bar (tuning a threshold); a stop-word list per language (brittle in hi/ta).

## D-086 — The LLM provider in practice
Date: 2026-09-24 · Phase: 10 · Requirement(s): TRD §10.3, D-021
Context: `gemini-2.5-flash` and `-flash-lite` answer "no longer available to new users" for this key. `gemini-3.5-flash` returned empty text at small output limits (it spends tokens thinking). `gemini-3.5-flash-lite` answered JSON in about 1 s.
Decision: The default model is `gemini-3.5-flash-lite` (config `assistant.yaml`), overridable with `SHIFTMATE_LLM_MODEL`. The key is read from `GEMINI_API_KEY` into a `SecretStr`, so it never appears in logs or reprs. A 12 s timeout, a 429, a server error or a missing key falls back to offline at once. Calls run in worker threads, so the gateway's clock never waits on the network. The assistant (and its 470 MB embedder) loads on first use, so the gateway starts at once. `tests/conftest.py` blanks the key, so the suite never calls the provider.
Why: A working free-tier model today; safe key handling; offline stays the default path.
Alternatives: Pinning a retired model name; loading the embedder at start-up (slow start, slow tests).

## D-087 — Answer validation and the safety-bypass guard
Date: 2026-09-24 · Phase: 10 · Requirement(s): F-ASK-01…06, TRD §10.3
Context: The TRD asks for strict JSON, citations from the retrieved chunks, and refusal of any request to defeat a safety system.
Decision:
- **Online replies become a refusal** ("I don't know… I won't guess") if they are not the JSON object, cite a chunk that was not retrieved, or claim to be answerable without a citation.
- **The model's own "not in the manuals" sentence is kept** and shown as a refusal.
- **Bypass requests are always refused.** A keyword list in en/hi/ta (config) matches requests to bypass or defeat the seatbelt, alarms, cameras or sensors, and those are refused in both modes, even if the model answered.
- **Refusals and notes are i18n keys** (`ask.dont_know`, `ask.refuse_bypass`, `ask.offline_unknown`, `ask.offline_english`, `ask.not_indexed`), so they read in the operator's language.
- **Offline answers** are the best passage as written, in the operator's language when a translation exists, else English with a note.
Why: No invented or unsourced answers; no help defeating safety systems.
Alternatives: Trusting the model's own refusals only.

## D-088 — The knowledge base
Date: 2026-09-24 · Phase: 10 · Requirement(s): TRD §10.1
Decision: 15 team-written English files cover the TRD list:
- walkaround, seatbelt, swing radius, spotter signals and truck loading;
- idling, cold start, heat, wet ground and night work;
- refuelling, warning lights (clearly "sample indicator meanings"), emergency exit, reporting and fatigue.

The four key safety files (seatbelt, swing radius, heat, emergency exit) also have Hindi and Tamil versions with the same headings in the same order, so chunk `<id>#<n>` names the same passage in every language. Distances, times and thresholds in the text match the config (10/6/3.5 m, heat index 41, 150/240 min, 5 min stops). The cab always shows the sample-content banner.
Why: Honest content that agrees with what the machine actually does; aligned translations make citations language-independent.
Alternatives: Translating every file now (more text for native review than the demo needs).

## D-089 — Assistant evaluation method
Date: 2026-09-24 · Phase: 10 · Requirement(s): TRD §10.6, §12
Decision:
- **The question set:** 40 questions in `eval/assistant_eval.yaml`, written before the first run (30 answerable, 10 per language, each with its acceptable chunks and key facts; 10 to refuse).
- **Scoring:** citation accuracy counts a refusal as a miss. Key facts are graded by the same model with a fixed rubric, and every reply is cached by prompt hash with 4.5 s pacing. Retrieval hit@5 is reported to explain misses.
- **What is reported:** both modes, as measured. Online met every target (93.3 % citations and key facts, 100 % refusals). Offline did not (66.7 % citations, 70 % key facts, 100 % refusals), because it answers only above the 0.55 bar.
Why: Golden rule 11: report what was measured, including targets not met.
Alternatives: A separate judge model (not available on the free tier here).

## D-090 — Voice commands: the gateway names the intent, the cab acts
Date: 2026-09-24 · Phase: 11 · Requirement(s): F-ASK-01, F-ASK-04, F-REP-01, TRD §10.5, §11.2
Decision:
- **Recognition** uses the browser's Web Speech API in en-IN, hi-IN or ta-IN, with live partial words in the transcript sheet. Hold the disc for 400 ms or more and release to finish, or tap once for a 6 s window ("Tap again to stop") for gloved hands.
- **Routing:** the transcript goes to `/assistant/intent` (keyword rules, then the model when online). `planAction` (pure) turns the intent into one action. A question opens Ask Cat and reads the answer aloud. "Report…" opens a report draft from the words, which the operator checks before sending. Next task, time left, repeat, acknowledge, breaks and help are answered in speech. With no gateway the words are treated as a question.
- **No "call supervisor" intent** (D-009). Every voice action also has a big button. Where speech is missing or the microphone is blocked, a calm message says to use the buttons. The disc hides behind a P1 takeover.
Why: One routing path for every language, with the model optional, and nothing sent without the operator's check.
Alternatives: On-device keyword spotting (no Tamil or Hindi models small enough); sending audio to a cloud recognizer (not offline).

## D-091 — Checklist answers by voice
Date: 2026-09-24 · Phase: 11 · Requirement(s): F-START-04
Decision: "Answer by voice" reads the next unanswered item aloud and listens. OK, problem and all-OK words for each language live in `config/checklist.yaml` (`voice:`) and reach the cab through `/cab/config`. The longest matching phrase wins, so "not ok" is a problem and "all ok" answers the rest (after reading them back). Anything else says "didn't catch that" and changes nothing.
Why: Configurable words the team can extend without code; a misheard answer never ticks an item.
Alternatives: Routing checklist answers through the intent endpoint (slower, and needs the gateway).

## D-092 — Camera proximity runs in the cab, only distances leave the tablet
Date: 2026-09-24 · Phase: 11 · Requirement(s): F-SAFE-03, TRD §11.2
Decision:
- **The detector** is MediaPipe ObjectDetector with EfficientDet-Lite0. The model (`public/models/efficientdet_lite0.tflite`, 4.6 MB) and its WASM are vendored and precached by the PWA, so the detector works offline. It is loaded only when the camera is turned on, runs at about 10 fps and keeps only people scoring at least 0.5.
- **Distance** is a monocular estimate: d = f_px × 1.7 m / box height. f_px comes from calibration (the helper stands at 3 m, averaged over 10 frames, stored on the device) or, until then, from a 60° field of view, and the panel says "approximate". The distance is smoothed with an EMA (α 0.4). Bearing uses the rear-facing mirror rule.
- **Posting:** readings go to `/proximity/camera` at most 5 times a second as distance, bearing and confidence. Frames are never sent or stored. The edge's existing `camera_or_sim_person` beat uses them and falls back to the scripted person if the camera stops.
- All numbers are in `config/edge.yaml` `camera.detect`.
Why: Privacy and offline operation; the same proximity warnings as the machine's sensors.
Alternatives: Server-side detection (sends images); depth estimation models (too heavy for the tablet).

## D-093 — Camera accuracy protocol is recorded in the cab, never invented
Date: 2026-09-24 · Phase: 11 · Requirement(s): TRD §12
Decision: "Test accuracy" on the Safety camera panel records 20 readings at each chosen true distance (2–6 m) and sends them to `POST /eval/camera-protocol`, which appends to `data/eval/camera_protocol.jsonl`. `shiftmate eval camera` (part of `eval all`) writes the mean absolute error by distance to EVAL.md, or "Not measured yet" with the steps if there are no readings. The protocol needs a webcam and a helper, so it was not run during development, and EVAL.md says so.
Why: Golden rule 11: only measured numbers.
Alternatives: A synthetic video test (would not measure the real camera).

## D-094 — Training progress: facts, streak and habit trend
Date: 2026-09-24 · Phase: 12 · Requirement(s): F-LRN-06
Decision: `GET /training/progress` (private to the signed-in operator) returns:
- lessons finished (distinct) out of all lessons;
- days in a row with a lesson or drill, counted back from today, or from yesterday when today has none yet (so the streak survives until the operator's next pause);
- each drill as right decisions out of scenes, plus the mean stop time;
- booked instructor sessions;
- for every finished lesson, how often its habit triggers were seen in the 7 days before this week and in this week.

Condition flags (HEAT, RAIN, NIGHT, WET_GROUND) are not habits and are left out. Events come from the operator's history plus the gateway's store. Times are shown in site time. The pure helpers live in `engines/lessons.py`.
Why: "Improvement in the habits the lessons target" measured the simplest honest way, with no scores or leaderboard (D-013).
Alternatives: Before and after the completion date (too few days after a demo completion to mean anything).

## D-095 — Lesson player behaviour
Date: 2026-09-24 · Phase: 12 · Requirement(s): F-LRN-01
Decision:
- **Narrated cards** are read aloud in the operator's language and move on by themselves while playing, each staying up for max(5 s, 0.45 s a word + 1.5 s). Pause, Read again and Next are always shown.
- **The quiz** marks the right answer with its explanation (also spoken), whether or not the operator picked it.
- **Finishing** saves the result: the share of right answers (1 for a lesson without questions), the seconds taken and the language. Quiz-only lessons skip the cards.
- A catalogue picture comes from the lesson's new optional `art:` field, or its first card.
Why: Hands-free for gloved operators, with every step also a big button.
Alternatives: Advancing on the speech engine's end event (unreliable across browsers and missing voices).

## D-096 — Hazard drill timing and voice stop
Date: 2026-09-24 · Phase: 12 · Requirement(s): F-LRN-04
Decision:
- **Timing:** each scene stays up for 4 s; the verdict and the scene's description then show for 2.5 s.
- **Scoring:** STOP on a hazard is right, with its reaction time; no STOP is a miss. On a safe scene, waiting is right and STOP is "not needed".
- **Voice:** while the drill runs, speech recognition listens in the operator's language, and any of the stop words (stop, रुको, रुकें, रोको, स्टॉप, நிறுத்து, நில்லு, ஸ்டாப்) counts as STOP. It restarts after silence. Without speech support the button alone works.
- **Results** are saved once, at the end, and shown as facts.
Why: Tests decisions as well as reflexes (D-032); every language, both input modes.
Alternatives: A shorter scene time (too hard with speech-recognition latency).

## D-097 — Lesson offers in the cab
Date: 2026-09-24 · Phase: 12 · Requirement(s): F-LRN-03
Decision: A `lesson_offer` from the gateway shows as a quiet card above the current screen in Paused mode, with the lesson, its length, why it was suggested, and Start lesson / Not now. It is hidden on lesson pages. Going back to work (a `mode` or `telemetry` message saying working) or a new snapshot removes it, so an offer never survives the pause it was made for.
Why: P4 is informational and must never interrupt work.
Alternatives: A P4 row in the alerts feed (hard to act on from there).

## D-098 — Illustrations built from plan-view parts
Date: 2026-09-24 · Phase: 12 · Requirement(s): DESIGN §6, D-014
Decision: `packages/ui/src/illustrations.tsx` draws all 53 lesson, checklist and drill pictures on a 160 × 100 grid. They are composed from about 20 parts (machine, truck, person, swing ring, clock, water, sun, moon, lamp, trench edge, power line…) in the glyph style (`currentColor`, square caps). A person in danger is the only filled shape. A test checks that every `illustration`, `scene` and `art` name in config has a drawing.
Why: Consistent, light, themeable art with no copyrighted material.
Alternatives: Hand-drawn SVG files per picture (53 files to keep consistent).

## D-099 — Safety beats always play at real time
Date: 2026-09-24 · Phase: 13 · Requirement(s): F-SAFE-02, F-SAFE-01, PRD §9
Decision: A scenario beat may carry `speed: 1`. When the player reaches it, the world clock drops to 1× for that beat and then returns to the chosen speed. `worker_near` and `seatbelt` use it. The live loop also caps catch-up at `MAX_CATCH_UP_S = 1.0` of wall time per tick and ends a batch of ticks when a beat changes speed. Headless runs (tests, eval) ignore beat speeds so their event logs stay the same.
Why: At 30× the caution → danger → critical escalation and the P1 takeover were over in under a second, so judges could not see them.
Alternatives: Asking the presenter to change speed by hand before each beat (easy to forget live).

## D-100 — Voice screens open in Working mode
Date: 2026-09-24 · Phase: 13 · Requirement(s): F-CAB-01, F-REP-01, F-ASK-04
Decision: Report and Ask open over the working strip when they were started by voice (`byVoice`), and Report returns to the strip 3 s after a spoken report is sent. Tapping into them still needs Paused mode.
Why: A spoken report is the hands-free path; hiding it until the machine stops made the near-miss beat fail at speed.
Alternatives: Waiting for Paused mode (the beat stalls while the machine works).

## D-101 — Captions, end of shift and reset
Date: 2026-09-24 · Phase: 13 · Requirement(s): PRD §9
Decision: Each beat's caption (en/hi/ta, from the scenario file) shows for 10 s in a strip in the cab when captions are on in Demo control. The `end_shift` beat opens My Day. `POST /demo/reset` reloads the scenario at 1×, captions off and online, and the console has a Reset demo button. The Ask Cat index and model load when the gateway starts.
Why: The presenter needs to narrate, restart quickly between runs, and not wait 30 s for the first voice answer.
Alternatives: Restarting the gateway between runs (slow, loses the console connection).

## D-102 — End-to-end demo test drives the real stack
Date: 2026-09-24 · Phase: 13 · Requirement(s): PRD §9, NFR reliability
Decision: `e2e/ravi-shift.spec.ts` starts the real gateway (Playwright `webServer`), signs Ravi in in Tamil, runs at 30× and walks every beat with pause, speed, seek and play. Speech recognition is replaced by a fake that is set on both `SpeechRecognition` and `webkitSpeechRecognition`. It must pass twice in a row.
Why: The demo story is the product's main claim; only a full-stack test proves it keeps working.
Alternatives: Checking beats only in the headless Python run (misses the cab and console).

## D-103 — History is the same in every process
Date: 2026-09-26 · Phase: 14 · Requirement(s): TRD §7 (determinism), PRD §10
Decision: The truck dispatcher now opens newly active loading zones in sorted order. Before, it looped over a Python set of zone names and drew a random dispatch time for each, and a set of strings iterates in a different order in every process (hash randomisation). So the same seed gave slightly different histories on each run for sites with more than one loading zone (7,040 / 7,042 / 7,043 finished tasks across three runs). A new test generates four Chennai days in two processes with different `PYTHONHASHSEED` values and requires identical hashes. The data was rebuilt and `EVAL.md` regenerated.
Why: The evaluation must be reproducible from a clean clone; the old tests ran both copies in one process, so they could not see it.
Alternatives: Fixing `PYTHONHASHSEED` in the CLI (hides the problem instead of removing it).
