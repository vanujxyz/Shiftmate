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
