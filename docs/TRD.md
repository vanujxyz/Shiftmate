# ShiftMate — Technical Requirements Document (TRD)

Version 1.0 · Companion to `docs/PRD.md` (what/why) and `CLAUDE.md` (build process).

This document is the **source of truth for implementation**: architecture, stack, repository layout, data schemas, algorithms, thresholds, APIs, message formats, evaluation and testing. Requirement IDs (`F-…`, `P-…`) refer to the PRD.

Thresholds and weights below are **defaults**. They live in YAML config files, never hard-coded in engine logic.

---

## 1. Architecture

### 1.1 Logical layers

```
 ┌──────────────────────────── MACHINE SIDE (edge) ────────────────────────────┐
 │                                                                             │
 │  Simulator (stands in for machine sensors + site world)                     │
 │        │  1 Hz signal ticks per machine, world entities (trucks, workers)   │
 │        ▼                                                                    │
 │  Edge Gateway  (Python, FastAPI)  — one process hosts many MachineRuntimes  │
 │   MachineRuntime (per machine):                                             │
 │     signal buffer → Safety engine → Risk engine → Idle-reason engine        │
 │                   → Interval builder → Anomaly engine → Alert policy        │
 │                   → Local store (SQLite) → Outbox (summaries + events)      │
 │   Shared: Estimation model (downloaded from fleet), Lesson recommender,     │
 │           Assistant (retrieval local; LLM when online), Report parser       │
 │        │ WebSocket + REST                                                   │
 │        ▼                                                                    │
 │  Cab app (React PWA, tablet)  ←  webcam person detection runs in-browser    │
 └────────────────────────────────┬────────────────────────────────────────────┘
                                  │ batched HTTPS when internet available
                                  ▼
 ┌──────────────────────────── FLEET SIDE (cloud) ────────────────────────────┐
 │  Fleet Service (Python, FastAPI, DuckDB)                                    │
 │    ingest summaries/events · site aggregates · fleet patterns ·            │
 │    estimation model training + versioned publishing · scale stats           │
 │        │ REST + WebSocket                                                   │
 │        ▼                                                                    │
 │  Console app (React): supervisor view, live site map, fleet view,           │
 │                       demo control, evaluation results                      │
 └─────────────────────────────────────────────────────────────────────────────┘
```

**Offline definition.** The Edge Gateway is on the machine, so the cab app can always reach it. "Offline" means the Edge Gateway cannot reach the Fleet Service or the internet (LLM API, weather API). In the demo, the console toggles this with `POST /demo/network`.

### 1.2 Processes and ports

| Process | Tech | Port | Start command (from repo root) |
|---|---|---|---|
| Edge Gateway | Python/FastAPI | 8100 | `uv run --directory backend shiftmate edge` |
| Fleet Service | Python/FastAPI | 8200 | `uv run --directory backend shiftmate fleet` |
| Cab app | Vite/React | 5173 | `pnpm --filter cab dev` |
| Console app | Vite/React | 5174 | `pnpm --filter console dev` |
| Everything | concurrently | — | `pnpm dev:all` |

All four run on one laptop for the demo. Nothing requires Docker. Commands must work in Windows PowerShell and in bash.

---

## 2. Technology stack

Use the latest stable release of each package at scaffold time and commit the lockfiles (`uv.lock`, `pnpm-lock.yaml`). Do not substitute alternatives without recording a decision in `docs/DECISIONS.md`.

### Backend (Python 3.12, managed with `uv`)
- Web: `fastapi`, `uvicorn[standard]`, `pydantic` v2, `pydantic-settings`
- CLI: `typer`
- Data: `numpy`, `pandas`, `pyarrow`, `duckdb` (fleet analytics), `sqlalchemy` 2 with SQLite (edge store)
- ML: `scikit-learn` (IsolationForest), `lightgbm` (quantile regression + `pred_contrib` explanations), `joblib`
- Config: `pyyaml`
- HTTP client: `httpx`
- Assistant: `google-genai` (official Gemini SDK, behind the provider layer in `assistant/llm.py`; see D-021), `rank-bm25`, `sentence-transformers` with model `paraphrase-multilingual-MiniLM-L12-v2` (supports English, Hindi, Tamil), `langdetect` optional
- Testing: `pytest`, `pytest-asyncio`, `hypothesis` (simulator invariants)
- Lint/format: `ruff`

### Frontend (Node 20 LTS or newer, `pnpm` workspaces)
- `react` 19, `react-dom`, `react-router`, `typescript` (strict)
- Build: `vite`, `vite-plugin-pwa` (Workbox) for the cab app
- State/data: `zustand`, `@tanstack/react-query`
- i18n: `i18next`, `react-i18next` (locales `en`, `hi`, `ta`)
- Offline storage: `dexie` (IndexedDB)
- Vision: `@mediapipe/tasks-vision` (ObjectDetector, model `efficientdet_lite0` float16 — model file vendored into `apps/cab/public/models/`)
- Styling: Tailwind CSS v4 with tokens from the design system (`packages/ui/src/tokens.css`) mapped via `@theme`
- Fonts: self-hosted (offline) via `@fontsource/*` packages named in `docs/DESIGN.md`
- Charts: **no chart library.** Build the few needed charts (time-split bar, sparkline, range bar) as small SVG components in `packages/ui` following the design system.
- Icons: the set specified in `docs/DESIGN.md`; custom machine-state glyphs as SVG components.
- Speech: browser Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`, `speechSynthesis`). Target browser: Chrome or Edge.
- Testing: `vitest`, `@testing-library/react`, `@playwright/test`
- Dev: `concurrently` at the workspace root

### External services
- Google Gemini API (free tier) for the assistant and report structuring, called through one provider interface (`assistant/llm.py`). Provider from env `SHIFTMATE_LLM_PROVIDER` (only `gemini` is implemented); model from `SHIFTMATE_LLM_MODEL` (exact model name from Google AI Studio); key from `GEMINI_API_KEY`. Uses Gemini JSON output mode. On a missing key, rate limit (HTTP 429), timeout or any error, the caller falls back immediately to offline mode (D-021).
- Open-Meteo (no key) for optional live weather (`SHIFTMATE_LIVE_WEATHER=1`). Demo scenarios use scripted weather.

### Hardware target
Development and demo laptop: Windows, RTX 3050, 16 GB RAM. Keep simulator memory under ~4 GB: history data at 30-second resolution, generated in chunks, stored as Parquet.

---

## 3. Repository layout

```
shiftmate/
├── CLAUDE.md
├── README.md
├── package.json                 # root scripts: dev:all, test:all, lint:all
├── pnpm-workspace.yaml
├── .env.example
├── docs/
│   ├── PRD.md
│   ├── TRD.md
│   ├── DESIGN.md                # produced by Claude Design; required before UI work
│   ├── DECISIONS.md             # decision log (append-only)
│   └── EVAL.md                  # generated evaluation report
├── config/
│   ├── machine_profiles/
│   │   ├── excavator.yaml
│   │   ├── wheel_loader.yaml
│   │   └── dozer.yaml
│   ├── sensor_tiers.yaml
│   ├── safety_rules.yaml
│   ├── risk_model.yaml
│   ├── alert_policy.yaml
│   ├── idle_rules.yaml
│   ├── privacy.yaml
│   ├── sites/
│   │   ├── chennai_highway.yaml
│   │   ├── pune_metro.yaml
│   │   ├── pilbara_mine.yaml
│   │   └── tromso_roadworks.yaml
│   ├── lessons.yaml
│   └── checklist.yaml
├── scenarios/
│   ├── ravi_shift.yaml          # the main demo scenario
│   └── fleet_tour.yaml          # basic-tier loader + scale demo beats
├── knowledge/                   # team-authored manual content (markdown)
├── fixtures/
│   └── sample_rows.csv          # the 4 rows from the brief, verbatim
├── data/                        # generated; git-ignored
├── models/                      # trained artifacts; git-ignored
├── backend/
│   ├── pyproject.toml
│   ├── src/shiftmate/
│   │   ├── cli.py
│   │   ├── settings.py
│   │   ├── config_loader.py
│   │   ├── schema/              # pydantic models + JSON Schema export
│   │   ├── sim/                 # world, machines, operators, weather, trucks, workers, scenario player, history generator
│   │   ├── engines/             # safety, risk, idle_reason, intervals, anomaly, alerts, estimation, lessons, reports
│   │   ├── edge/                # MachineRuntime, EdgeGateway app, local store, outbox, sync
│   │   ├── fleet/               # Fleet Service app, ingest, aggregates, patterns, training, model registry, scale stats
│   │   ├── assistant/           # chunking, index, retrieval, llm client, prompts, offline answerer, intents
│   │   ├── eval/                # evaluation runners → docs/EVAL.md
│   │   └── util/                # time, units, heat index, ids
│   └── tests/
└── frontend/
    ├── apps/
    │   ├── cab/                 # operator PWA
    │   └── console/             # supervisor + site map + fleet + demo control + eval
    └── packages/
        ├── ui/                  # tokens.css, components, SVG charts, glyphs
        ├── contracts/           # TS types generated from backend JSON Schema
        └── i18n/                # en/hi/ta resource files shared by both apps
```

---

## 4. Configuration files (schemas and defaults)

All config is loaded and validated at start-up by `config_loader.py` into pydantic models. Invalid config must fail fast with a clear message.

### 4.1 Machine profiles — `config/machine_profiles/excavator.yaml`
```yaml
machine_type: excavator
display_name: {en: "Excavator", hi: "एक्सकेवेटर", ta: "அகழ்வு இயந்திரம்"}
id_prefix: EXC
example_models: ["Cat 320", "Cat 323", "Cat 336"]
load_cycle_definition: "one haul truck fully loaded"
passes_per_load: {min: 4, max: 7}
seconds_per_pass: {mean: 24, sd: 4}
fuel_lph: {idle: 3.2, working: 15.0, travel: 9.0}
rpm: {idle: 950, working: 1800}
max_travel_speed_kmh: 5.5
warm_up: {coolant_ready_c: 60, max_minutes_normal: 5, max_minutes_below_0c: 15}
idle:
  segment_min_seconds: 60          # idle shorter than this is ignored
  habit_threshold_minutes: 5       # unexplained seated idle longer than this → Habit
  unattended_seat_empty_seconds: 120
proximity_m: {caution: 10.0, danger: 6.0, critical: 3.5}   # swing radius based
unsafe:
  speed_near_person_kmh: 3.0       # moving faster than this with person within caution distance
  continuous_operation_warn_min: 150
  continuous_operation_limit_min: 240
task_types: [trenching, truck_loading, backfilling, site_clearing]
```
`wheel_loader.yaml`: id_prefix `WHL`, models "Cat 950 GC"/"Cat 966", load cycle "one haul truck fully loaded", passes 3–5, seconds_per_pass mean 38, fuel idle 2.8 / working 13 / travel 11, max speed 38 km/h, proximity caution 12 / danger 7 / critical 4, task_types [truck_loading, stockpile_moving, site_clearing].
`dozer.yaml`: id_prefix `DOZ`, models "Cat D6"/"Cat D8", load cycle "one push cycle", seconds per push mean 55, fuel idle 3.5 / working 22 / travel 14, max speed 10 km/h, proximity caution 12 / danger 7 / critical 4, task_types [grading, site_clearing, backfilling]. Dozer tasks are not truck-dependent.

### 4.2 Sensor tiers — `config/sensor_tiers.yaml`
```yaml
tiers:
  basic:      # exactly the brief's sample columns + GPS
    signals: [engine_on, engine_hours, fuel_rate, hydraulic_active, travel_speed_kmh, seatbelt_fastened, gps]
  standard:
    inherits: basic
    signals: [seat_occupied, engine_rpm, coolant_temp_c]
  advanced:
    inherits: standard
    signals: [proximity_m, truck_in_loading_zone]
feature_availability:
  seatbelt_alert: [basic, standard, advanced]
  unattended_running: [standard, advanced]        # needs seat_occupied
  warm_up_by_coolant: [standard, advanced]        # basic uses time-based warm-up
  proximity_sensor: [advanced]                    # camera add-on available for any tier
  truck_presence: [advanced]                      # others use site dispatch log (lower confidence)
```
The UI must show which features are active for the current machine and label reduced-confidence results.

### 4.3 Sites — `config/sites/chennai_highway.yaml`
```yaml
site_id: CHN-HWY-01
name: "Chennai Outer Ring Road — Package 3"
country: IN
timezone: Asia/Kolkata
locale_default: ta
languages: [ta, hi, en]
units: metric
climate:                      # used by weather generator
  month_profiles: {5: {temp_mean_c: 36, temp_amp_c: 6, rh_mean: 62, rain_prob: 0.08}, 10: {temp_mean_c: 30, temp_amp_c: 4, rh_mean: 80, rain_prob: 0.45}}
shift: {start: "07:00", end: "17:00", breaks: [{start: "10:30", minutes: 15}, {start: "13:00", minutes: 30}, {start: "15:30", minutes: 15}]}
layout:                       # metres, local x/y; used by simulator and site map
  size: {w: 400, h: 260}
  zones:
    - {id: DIG-A, type: dig, polygon: [[40,40],[160,40],[160,120],[40,120]]}
    - {id: LOAD-A, type: loading, polygon: [[170,60],[210,60],[210,100],[170,100]]}
    - {id: HAUL, type: haul_road, polyline: [[210,80],[380,80],[380,220]]}
    - {id: STOCK-1, type: stockpile, polygon: [[250,160],[330,160],[330,230],[250,230]]}
    - {id: REST, type: break_area, polygon: [[20,200],[70,200],[70,240],[20,240]]}
trucks: {count: 20, dispatch_mean_interval_min: 6.0, shortage_windows: []}
workers: {count: 14}
safety_overrides: {}          # per-site threshold overrides (F-FLT-06)
```
Other sites: `pune_metro.yaml` (PNQ-MET-01, moderate climate, hi/en), `pilbara_mine.yaml` (PIL-MIN-01, Australia, extreme heat/dust, en, low visibility events), `tromso_roadworks.yaml` (TRO-RD-01, Norway, sub-zero, long darkness, en, frozen ground → long warm-ups).

### 4.4 Safety rules — `config/safety_rules.yaml`
Declarative rules evaluated each tick by the Safety engine. Each rule: `id, when (expression over the signal window), priority, message_key, cooldown_s, requires_signals`.
```yaml
rules:
  - id: SEATBELT_MOVING
    when: "not seatbelt_fastened and (travel_speed_kmh > 0.5 or hydraulic_active)"
    sustain_s: 2
    priority: P1
    message_key: alert.seatbelt_moving
    cooldown_s: 60
    requires_signals: [seatbelt_fastened]
  - id: PROXIMITY_CAUTION
    when: "proximity_m <= caution_m"
    priority: P3
  - id: PROXIMITY_DANGER
    when: "proximity_m <= danger_m"
    priority: P2
  - id: PROXIMITY_CRITICAL
    when: "proximity_m <= critical_m"
    priority: P1
  - id: SPEED_NEAR_PERSON
    when: "proximity_m <= caution_m and travel_speed_kmh > speed_near_person_kmh"
    priority: P1
  - id: UNATTENDED_RUNNING
    when: "engine_on and not seat_occupied"
    sustain_s: 120
    priority: P2
    requires_signals: [seat_occupied]
  - id: FATIGUE_WARN
    when: "continuous_operation_min >= fatigue_warn_min"
    priority: P3
  - id: FATIGUE_LIMIT
    when: "continuous_operation_min >= fatigue_limit_min"
    priority: P2
  - id: HEAT_NO_BREAK
    when: "heat_index_c >= 41 and minutes_since_break >= 60"
    priority: P2
```
Expressions are evaluated with a small safe evaluator (whitelisted names and operators, implemented in `engines/rule_eval.py`; **never** Python `eval`). `caution_m`, `danger_m`, `critical_m`, `fatigue_warn_min`, `fatigue_limit_min` are computed by the Risk engine (§6.3), which scales profile values by risk band.

### 4.5 Risk model — `config/risk_model.yaml`
```yaml
components:
  heat_index_c: [{lt: 32, points: 0}, {lt: 40, points: 10}, {lt: 52, points: 25}, {gte: 52, points: 40}]
  precipitation_mm_h: [{lt: 0.5, points: 0}, {lt: 4, points: 10}, {gte: 4, points: 20}]
  ground_condition: {dry: 0, rocky: 5, wet: 8, muddy: 15, frozen: 20}
  is_night: {true: 10, false: 0}
  visibility_m: [{lt: 200, points: 15}, {lt: 1000, points: 5}, {gte: 1000, points: 0}]
  continuous_operation_min: [{lt: 120, points: 0}, {lt: 180, points: 10}, {lt: 240, points: 20}, {gte: 240, points: 30}]
  proximity_state: {clear: 0, caution: 10, danger: 25, critical: 35}
  seatbelt_unfastened_while_working: {true: 25, false: 0}
  near_miss_last_24h: {per_event: 5, max: 15}
bands: {green: [0, 39], amber: [40, 69], red: [70, 100]}
threshold_scaling:          # multiplies profile proximity distances; divides fatigue minutes
  green: {proximity: 1.0, fatigue: 1.0}
  amber: {proximity: 1.25, fatigue: 1.2}
  red:   {proximity: 1.5, fatigue: 1.5}
heat_fatigue_override: {heat_index_gte: 41, fatigue_divisor: 1.5}
```
Score = min(100, sum of component points). Hysteresis: a band change down requires the score to stay below the band floor for 120 s.

### 4.6 Alert policy — `config/alert_policy.yaml`
```yaml
priorities:
  P1: {presentation: takeover, sound: critical_tone, speak: true, requires_ack: true, escalate_after_s: 20}
  P2: {presentation: banner,   sound: urgent_tone,   speak: true, requires_ack: true}
  P3: {presentation: strip,    sound: none,          speak: false, requires_ack: false, deliver_when: paused}
  P4: {presentation: feed,     sound: none,          speak: false, requires_ack: false, deliver_when: paused}
max_interrupting_alerts: 1       # P1/P2 on screen at once; higher priority pre-empts, lower queues
default_cooldown_s: 300
dedupe_window_s: 30
paused_definition: {idle_seconds: 30}
supervisor_share: [P1, P2]       # plus incidents, near-misses (P-03)
```

### 4.7 Idle rules — `config/idle_rules.yaml`
Ordered; first match wins (§6.4 explains the algorithm).
```yaml
order: [SCHEDULED_BREAK, WARM_UP, UNATTENDED_RUNNING, WAITING_FOR_TRUCK, HABIT, UNKNOWN]
responses:
  WARM_UP:            {operator: none, supervisor: none}
  SCHEDULED_BREAK:    {operator: none, supervisor: none}
  WAITING_FOR_TRUCK:  {operator: offer_lesson, supervisor: site_issue_truck_supply}
  UNATTENDED_RUNNING: {operator: safety_reminder_on_return, supervisor: safety_event, lesson: L-SHUTDOWN}
  HABIT:              {operator: coach_after_segment, supervisor: aggregate_only, lesson: L-IDLE-FUEL}
  UNKNOWN:            {operator: none, supervisor: aggregate_only}
```

### 4.8 Privacy — `config/privacy.yaml`
```yaml
supervisor_sees_operator_detail_for: [P1, P2, incident, near_miss, UNATTENDED_RUNNING]
supervisor_aggregates_min_group_size: 3   # trends only for groups of ≥3 operators
truck_wait_attribution: site
fleet_upload: [interval_summaries, task_summaries, events_shared]   # never raw ticks
```

### 4.9 Lessons — `config/lessons.yaml`
Twelve lessons. Each entry:
```yaml
- id: L-SHUTDOWN
  title: {en: "Shut down before you step out", hi: "...", ta: "..."}
  format: narrated_cards        # narrated_cards | quiz | drill
  duration_s: 90
  triggers: [UNATTENDED_RUNNING]
  cards:                        # 3–6 cards: text + illustration id (SVG in packages/ui/illustrations)
    - {text: {en: "...", hi: "...", ta: "..."}, illustration: cab-exit-idle}
  quiz: [{q: {...}, options: [{...}], answer: 1}]
```
Required lesson IDs: `L-SHUTDOWN`, `L-IDLE-FUEL`, `L-SEATBELT`, `L-SWING-ZONE`, `L-SPOTTER-SIGNALS`, `L-HEAT-STRESS`, `L-WET-GROUND`, `L-NIGHT-WORK`, `L-TRUCK-LOADING-FLOW`, `L-WALKAROUND`, `L-FATIGUE`, `D-HAZARD-DRILL-1` (format `drill`).
Trigger vocabulary: idle reasons, safety rule IDs, anomaly feature codes, and condition flags (`HEAT`, `RAIN`, `NIGHT`, `WET_GROUND`).
Hindi and Tamil text must be real translations written carefully, not transliteration.

### 4.10 Checklist — `config/checklist.yaml`
Seven walkaround items (tracks/tyres, leaks, lights and horn, mirrors and camera, seatbelt condition, fire extinguisher, area clear of people), each with en/hi/ta text.

---

## 5. Data model

All schemas are pydantic models in `backend/src/shiftmate/schema/` and exported to JSON Schema (`shiftmate schema export`), from which `frontend/packages/contracts` generates TypeScript types (`json-schema-to-typescript`). Timestamps are ISO 8601 with timezone offset. Units are metric and encoded in field names.

### 5.1 Reference tables

**machines**
| field | type | notes |
|---|---|---|
| machine_id | str | `EXC001` style: profile `id_prefix` + 3 digits |
| machine_type | enum | excavator, wheel_loader, dozer |
| model | str | from profile `example_models` |
| model_year | int | 2010–2026 |
| sensor_tier | enum | basic, standard, advanced |
| site_id | str | |
| engine_hours_start | float | starting hour meter |

**operators**
| field | type | notes |
|---|---|---|
| operator_id | str | `OP1001` … |
| name | str | realistic names matching site country |
| preferred_language | enum | en, hi, ta |
| experience_years | float | |
| home_site_id | str | |
| certifications | list[str] | machine types certified |
| personality | object | **simulator only, never visible to engines** (§7.3) |

**tasks**
| field | type | notes |
|---|---|---|
| task_id | str | `T-<site>-<yyyymmdd>-<n>` |
| site_id, machine_id, operator_id | str | |
| task_type | enum | from profile |
| zone_id | str | site layout zone |
| planned_quantity | float | |
| quantity_unit | enum | loads, m, m2, m3 |
| scheduled_start | datetime | |
| actual_start, actual_end | datetime | null until done |
| actual_duration_min | float | label for estimation |
| status | enum | scheduled, active, done |
| conditions_at_start | object | ground_condition, heat_index_c, precipitation_mm_h, is_night |

### 5.2 Signal tick (1 Hz live; 30 s in stored history)
`SignalTick`: `ts, machine_id, operator_id|null, engine_on, engine_hours, fuel_rate_lph, hydraulic_active, travel_speed_kmh, seatbelt_fastened, gps {x_m, y_m}, heading_deg, seat_occupied?, engine_rpm?, coolant_temp_c?, proximity_m?, proximity_source? (sensor|camera), truck_in_loading_zone?, ambient_temp_c, relative_humidity_pct, heat_index_c, precipitation_mm_h, wind_kmh, visibility_m, is_night, ground_condition, task_id|null, task_progress_qty`.
Fields marked `?` are `null` when the machine's sensor tier lacks them.

### 5.3 Interval record — extends the brief's sample schema
Built by the Interval builder every 15 minutes of machine time and at task boundaries. **The first nine columns are the brief's columns with the exact semantics documented in the PRD §7.** CSV/Parquet exports use the brief's original header text for the first nine columns (`Timestamp`, `Machine ID`, `Operator ID`, `Engine Hours`, `Fuel Used (L)`, `Load Cycles`, `Idling Time (min)`, `Seatbelt Status`, `Safety Alert Triggered`) and snake_case for the rest.

| field | type | notes |
|---|---|---|
| timestamp | datetime | interval end |
| machine_id | str | |
| operator_id | str | |
| engine_hours | float | hour meter at interval end, 1 decimal |
| fuel_used_l | float | during interval, 1 decimal |
| load_cycles | int | during interval (profile definition) |
| idling_time_min | int | during interval |
| seatbelt_status | enum | `Fastened` / `Unfastened` at interval end |
| safety_alert_triggered | enum | `Yes` if any P1/P2 alert in interval |
| interval_start | datetime | |
| interval_minutes | float | |
| site_id, machine_type, sensor_tier, task_id | str | |
| engine_on_min, working_min, travel_min | float | |
| seat_occupied_min | float? | |
| seatbelt_unfastened_working_s | int | |
| avg_engine_rpm | float? | |
| max_travel_speed_kmh | float | |
| truck_present_min | float? | |
| truck_wait_min | float | from sensor or dispatch log |
| min_proximity_m | float? | |
| proximity_caution_count, proximity_danger_count, proximity_critical_count | int | |
| ambient_temp_c, relative_humidity_pct, heat_index_c, precipitation_mm, wind_kmh, visibility_m | float | interval mean (precip = total) |
| is_night | bool | majority of interval |
| ground_condition | enum | dry, wet, muddy, rocky, frozen |
| continuous_operation_min | float | at interval end |
| coolant_temp_c | float? | interval min |
| incident_count, near_miss_count | int | |
| idle_warmup_min, idle_break_min, idle_truck_wait_min, idle_unattended_min, idle_habit_min, idle_unknown_min | float | from Idle-reason engine (predicted) |
| fuel_per_load_cycle_l | float? | derived; null if load_cycles = 0 |
| risk_score_max | int | |
| label_* | various | **ground truth, simulator output only** (§7.4) |

### 5.4 Events
`Event`: `event_id (uuid7), ts, machine_id, operator_id, site_id, type, priority (P1–P4|null), code, payload (object), shared_with_supervisor (bool), synced (bool)`.
`type` ∈ `alert, alert_ack, alert_cleared, idle_segment, anomaly, incident, near_miss, lesson_offered, lesson_completed, drill_result, booking, checklist, risk_band_change, connectivity`.

`IdleSegment` payload: `start, end, duration_s, reason, confidence (0–1), evidence: [str codes], fuel_l, response_taken`.

### 5.5 Training
`lesson_completions (operator_id, lesson_id, ts, score, duration_s, language)`, `drill_results (operator_id, drill_id, ts, hazards: [{hazard_id, reaction_ms, correct}], score)`, `bookings (booking_id, operator_id, slot_id, status)`, `training_slots (slot_id, dealer_centre, site_id, start, topic, seats_left)` — slots generated per site ("Cat dealer training centre — Chennai", generic naming, no real dealer names).

### 5.6 Fixtures
`fixtures/sample_rows.csv` contains the brief's four rows verbatim. A test asserts they parse into `IntervalRecord` (with extension fields null). They are **not** used to calibrate the simulator physics (PRD §7).

---

## 6. Engines (edge, per MachineRuntime)

Every engine is a pure, deterministic class with `update(tick|interval, state) -> outputs`, no I/O, fully unit-tested. Engines read only fields available in the machine's sensor tier and never read `label_*` or operator `personality`.

### 6.1 Machine state
Derived each tick: `ENGINE_OFF`, `IDLE` (engine on, not hydraulic_active, speed < 0.5 km/h), `WORKING` (hydraulic_active), `TRAVELLING` (speed ≥ 0.5 and not hydraulic_active). **Paused mode** for the UI = `IDLE` for ≥ 30 s or `ENGINE_OFF`. `continuous_operation_min` resets after ≥ 10 min in a break or engine off. Idle while waiting for a truck (or any other non-break idle) does **not** reset it (D-006).

### 6.2 Safety engine
Evaluates `safety_rules.yaml` each tick with `sustain_s` debouncing and per-rule cooldown. Rules whose `requires_signals` are missing for the tier are disabled and listed in `/machines/{id}` capabilities. Emits `alert` candidates to the Alert policy.

### 6.3 Risk engine
Computes the risk score and band each tick (§4.5), applies hysteresis, publishes `risk_update` when score changes by ≥ 3 or band changes, and publishes effective thresholds (`caution_m`, `danger_m`, `critical_m`, `fatigue_warn_min`, `fatigue_limit_min`) used by the Safety engine. Returns top contributing components for the UI ("Heat +25, Fatigue +10").

### 6.4 Idle-reason engine
1. **Segmentation.** An idle segment starts when state becomes `IDLE` and ends when state leaves `IDLE`. Segments shorter than `segment_min_seconds` are discarded. Classification is provisional while the segment is open (updated every 10 s) and final when it closes.
2. **Classification (first match in `idle_rules.yaml` order):**
   - `SCHEDULED_BREAK`: segment overlaps a scheduled break window by ≥ 50%. Evidence `in_break_window`.
   - `WARM_UP`: segment starts within 2 min of engine start AND (standard/advanced: `coolant_temp_c < coolant_ready_c`; basic: duration ≤ `max_minutes_normal`, or ≤ `max_minutes_below_0c` when ambient < 0 °C). Evidence `after_engine_start`, `coolant_cold` / `time_based`.
   - `UNATTENDED_RUNNING` (standard/advanced only): `seat_occupied == false` for ≥ `unattended_seat_empty_seconds` within the segment. Evidence `seat_empty`.
   - `WAITING_FOR_TRUCK`: task is truck-dependent (`truck_loading`) AND seat occupied (or unknown on basic) AND (advanced: `truck_in_loading_zone == false` for ≥ 70% of segment; standard/basic: site dispatch log shows no truck assigned to the loading zone for ≥ 70% of segment). Evidence `no_truck_sensor` or `no_truck_dispatch_log`. Confidence 0.95 advanced, 0.8 standard, 0.7 basic.
   - `HABIT`: seat occupied (or unknown on basic), not truck-limited, duration ≥ `habit_threshold_minutes`. Confidence 0.85 standard/advanced, 0.6 basic.
   - `UNKNOWN`: anything else.
3. **Fuel:** `fuel_l = idle fuel rate × duration` (from ticks).
4. **Response** per `idle_rules.yaml` `responses` (creates events, lesson offers, supervisor items).

The **site dispatch log** is produced by the simulator's truck dispatcher and exposed to the edge as a site feed (`truck_dispatch` messages on the site channel). It represents the site's truck management system.

### 6.5 Interval builder
Aggregates ticks into `IntervalRecord` (§5.3) every 15 machine-minutes and at task start/end; computes derived fields; hands the record to the Anomaly engine, local store and outbox.

### 6.6 Anomaly engine (F-INS-04, F-INS-05)
- **Features per interval:** `idle_ratio = idling_time_min / engine_on_min`, `fuel_per_load_cycle_l`, `fuel_lph = fuel_used_l / engine_on_h`, `load_cycles_per_working_h`, `seatbelt_unfastened_working_s`, `max_travel_speed_kmh`, `proximity_danger_count + proximity_critical_count`, `idle_habit_min`, `idle_unattended_min`, `avg_engine_rpm` (null-safe; features missing for the tier are dropped).
- **Personal baselines:** robust z-score per feature against the trailing 14 days of the same `(operator_id, machine_type, task_type)`; fall back to `(machine_type, task_type, site_id)` when fewer than 20 intervals exist. `z = (x − median) / (1.4826 × MAD + ε)`.
- **Model:** one `IsolationForest` per `(machine_type, sensor_tier)` trained on baseline-normalised feature vectors from the training period (`n_estimators=200`, `contamination=0.05`, `random_state=7`). Stored under `models/anomaly/<type>_<tier>.joblib`.
- **Decision:** an interval is anomalous if (IsolationForest score is in the top 5% for its group AND at least one |z| ≥ 3) OR any hard rule from §4.4 fired with P1 in the interval.
- **Explanation:** up to three features with the largest |z|, mapped to message keys (e.g. `insight.fuel_per_load_high` → "Fuel per truck was 2.1 L, about 3× your usual").
- **Output:** `anomaly` event with `features, z_scores, if_score, explanation_keys`.

### 6.7 Estimation (F-SHIFT-02/03/04, F-FLT-05)
- **Training (fleet side):** LightGBM regressors with `objective=quantile`, `alpha ∈ {0.1, 0.5, 0.9}`, target `log(actual_duration_min)`. Features: `task_type` (categorical), `machine_type` (categorical), `model` (categorical), `planned_quantity`, `quantity_unit` (categorical), `operator_experience_years`, `operator_skill_index` (operator's trailing 30-day median of actual/expected ratio for that task type; 1.0 if no history), `ground_condition` (categorical), `heat_index_c`, `precipitation_mm_h`, `is_night`, `site_id` (categorical), `expected_truck_interval_min` (truck-dependent tasks), `hour_of_day`. Params: `num_leaves=31, learning_rate=0.05, n_estimators=600, min_data_in_leaf=20`, early stopping on a validation split. Enforce p10 ≤ p50 ≤ p90 after prediction (sort).
- **Split:** time-based. Train on days 1–32, validate on 33–35, test on 36–42 (history of 42 days).
- **Publishing:** fleet stores artefacts in `models/estimation/<version>/` with `manifest.json` (version, trained_at, metrics, feature list). Edge downloads the latest version when online (`GET /models/estimation/latest`) and keeps using the cached version offline.
- **Explanations:** `pred_contrib=True` on the p50 model; take the three contributions with largest absolute value, group one-hot/categorical contributions back to the source feature, map to message keys with direction (`reason.wet_ground_slower`, `reason.experience_faster`, `reason.truck_supply_slower`, `reason.heat_slower`, `reason.night_slower`, `reason.quantity_large`). Show minutes where meaningful: contribution in log space converted to minutes relative to p50.
- **Live remaining time:** for the active task, `observed_rate = qty_done / elapsed_min`; `model_rate = planned_qty / p50`. Blend `rate = w·observed + (1−w)·model`, `w = min(0.8, progress_fraction)`. Remaining p50 = `(planned − done) / rate`; p10/p90 scaled by the original p10/p50 and p90/p50 ratios. Conditions changes (e.g. heat band change) trigger re-prediction for remaining quantity.
- **Fleet patterns** (F-FLT-05): the fleet service computes and exposes interpretable multipliers from the test-period data, e.g. median actual/expected ratio by `(task_type, ground_condition)` and by heat band, with counts. Used in explanations ("Across 60 machines, wet ground adds about 20% to trenching").

### 6.8 Alert policy
Implements §4.6: priority queue, single interrupting alert, pre-emption, cooldown, dedupe, paused-only delivery for P3/P4, escalation of unacknowledged P1 (repeat tone + louder voice + supervisor share). Emits `alert`, `alert_cleared` messages; records `alert_ack` events.

### 6.9 Lesson recommender
Maintains per operator a trigger count from events in the last 7 days. Recommends up to 3 lessons whose `triggers` match, ordered by trigger count × recency, excluding lessons completed in the last 3 days. Offers a lesson (P4 `lesson_offered`) only when Paused mode starts and the expected pause is ≥ 90 s (waiting for truck, scheduled break, engine off). Condition triggers (`HEAT`, `RAIN`, `NIGHT`, `WET_GROUND`) come from the risk components at shift start.

### 6.10 Report parser (F-REP-01..04)
- Online: send transcript to the LLM with a structured-output prompt returning JSON `{type: incident|near_miss|equipment_problem, severity: low|medium|high, summary_en, summary_local, people_involved: bool, injury: bool}`; validate with pydantic; on validation failure, fall back to offline.
- Offline: keyword classifier (en/hi/ta keyword lists in `assistant/keywords/`) for type and severity; summary = transcript.
- Auto-fill from runtime state: ts, machine, operator, site, zone (from gps), task, weather snapshot, risk score.
- Saved as event; queued in outbox.

---

## 7. Simulator

Package `shiftmate.sim`. Deterministic given a seed. Two modes share the same world model:
- **History mode:** `shiftmate sim generate --days 42 --seed 7` → writes Parquet to `data/history/` (`machines`, `operators`, `tasks`, `ticks_30s` partitioned by site/day, `intervals`, `events`, `labels`) and a DuckDB file for the fleet service.
- **Live mode:** the Edge Gateway runs the world clock at a configurable speed (1×–60×), emitting 1 Hz ticks per machine; a scenario player can script events (§8).

### 7.1 Fleet composition (history)
- 4 sites (config), 60 machines: 30 excavators, 18 wheel loaders, 12 dozers; distributed Chennai 24, Pune 14, Pilbara 14, Tromsø 8.
- Sensor tiers by model year: < 2016 basic, 2016–2021 standard, ≥ 2022 advanced (with 10% random downgrade to simulate missing retrofits).
- 80 operators with site-appropriate names; `OP1001` Ravi Kumar (ta, 9.0 years) assigned to `EXC001` (Cat 320, 2023, advanced) at Chennai; `EXC001` engine_hours_start 1520.0.
- Month: history covers 42 days ending the day before the demo date; Chennai month profile chooses May (hot) for days 1–21 and October (monsoon) for days 22–42 to create condition variety.

### 7.2 World mechanics
- **Weather:** hourly temperature = mean + amplitude·sin(daily cycle peaking 15:00) + AR(1) noise; humidity inversely correlated; rain as a Markov chain (dry/rain) with site probabilities; heat index via the Rothfusz regression (converted °C↔°F, with the standard low-temperature adjustment); ground condition transitions: rain → wet (≥ 2 mm in 2 h) → muddy (≥ 10 mm in 6 h), dries after 6 h dry and heat; Tromsø below 0 °C → frozen; Pilbara rocky baseline; visibility drops with rain and Pilbara dust events; night from site sunrise/sunset (simplified by latitude and date).
- **Trucks:** a dispatcher sends trucks to each loading zone with exponential inter-arrival (`dispatch_mean_interval_min`), plus random **shortage windows** (1–2 per site-week, 20–90 min, interval × 3). Trucks travel along the haul road polyline; a truck in the loading zone waits until loaded. The dispatcher writes the **dispatch log** (truck assigned/arrived/departed per zone).
- **Workers:** move between zones along random waypoints; some walk near machines; a per-site probability of entering swing radius creates proximity events.
- **Machine behaviour:** state machine per task: warm-up after engine start (coolant rises ~8 °C/min from ambient, slower below 0 °C) → work cycles (passes per load, pass time distribution) with idle when no truck → breaks per shift schedule → travel between zones. Fuel rate by state from profile; engine hours integrate engine-on time. Load cycles and quantity progress follow the task type (loads, m, m², m³ with profile productivity rates).
- **Productivity & durations:** base productivity per `(task_type, machine_type)`, multiplied by: ground (wet 0.85, muddy 0.7, frozen 0.8, rocky 0.9), heat (heat index > 40 → 0.9, > 46 → 0.8), night 0.9, operator skill (0.8–1.2 from experience + personality), plus lognormal noise (σ 0.08). Truck-dependent tasks additionally lose time to truck waits. `actual_duration_min` is the emergent result, not a formula output.

### 7.3 Operator personalities (simulator-only, never exposed)
Each operator has traits in [0, 1]: `idle_habit`, `seatbelt_skipper`, `steps_out_engine_on`, `speeds_near_people`, `skips_breaks`, `skill`. About 15% of operators have one elevated trait (> 0.6). Traits drive behaviour probabilities (e.g. `idle_habit` adds unexplained seated idle segments of 5–20 min; `steps_out_engine_on` leaves the seat with engine running for 2–10 min).

### 7.4 Ground-truth labels
The simulator writes labels alongside data (never read by engines): per idle segment `label_idle_reason`; per interval `label_anomaly` (bool) and `label_anomaly_type` ∈ {habit_idle, unattended, seatbelt, speed_near_person, fuel_abnormal, low_productivity, none}; a small number of injected `fuel_abnormal` intervals (fuel rate × 1.6–2.2, 0.5% of intervals) and `low_productivity` intervals.

### 7.5 Invariants (property tests with `hypothesis` + direct checks)
- Engine hours are non-decreasing per machine; increase equals engine-on time (±0.01 h).
- Fuel used equals Σ(state rate × time) within 2% noise.
- `idling_time_min ≤ engine_on_min ≤ interval_minutes`.
- `seatbelt_status` at interval end equals the last tick value.
- `safety_alert_triggered == "Yes"` iff a P1/P2 alert occurred in the interval.
- No proximity values on machines whose tier lacks the sensor (unless camera source).
- Same seed ⇒ identical outputs (hash compare).

### 7.6 Scale mode (F-FLT-07)
`shiftmate sim scale --machines 10000 --sim-minutes 60 --speed max` synthesises interval summaries and events for N machines (profile/tier/site mix as §7.1, lightweight statistical generator, no per-tick physics) and posts them to the Fleet Service in batches of 500. Also `shiftmate bench runtime --machines 200 --sim-minutes 30` runs 200 full MachineRuntimes and reports per-machine CPU time per tick, memory (tracemalloc), and bytes uploaded per machine per hour. Results go to `docs/EVAL.md` and `/scale/stats`. The 1.6 M projection is computed as: `uplink_bytes_per_machine_per_day × 1.6e6`, `summaries_per_day × 1.6e6 / 86400` (records/s) — labelled "projection".

---

## 8. Scenarios

YAML files in `scenarios/` drive the live mode deterministically. Schema:
```yaml
name: ravi_shift
site_id: CHN-HWY-01
date: "2026-09-24"
start: "06:58"
seed: 11
focus_machine: EXC001
operator: OP1001
language: ta
background_machines: 11          # other machines on the site run normally
tasks: [...]                     # three tasks for EXC001 (truck_loading 18 loads @ LOAD-A; trenching 60 m @ DIG-A; backfilling 120 m3 @ DIG-A)
weather_script:                  # overrides generator
  - {at: "06:58", temp_c: 29, rh: 78, precip_mm_h: 0, ground: wet}
  - {at: "10:45", temp_c: 34, rh: 62}      # heat index ≈ 43 (D-005)
  - {at: "11:00", temp_c: 35, rh: 60}      # heat index ≈ 45 (D-005)
beats:
  - {id: sign_in,     at: "07:00", action: await_operator_sign_in}
  - {id: cold_start,  at: "07:02", action: engine_start, params: {coolant_c: 32}}
  - {id: my_shift,    at: "07:15", action: note, params: {caption: "Estimates reflect wet ground"}}
  - {id: truck_delay, at: "08:10", action: truck_shortage, params: {zone: LOAD-A, minutes: 18}}
  - {id: worker_near, at: "09:30", action: camera_or_sim_person, params: {path: [[14,0],[8,0],[5,0],[3,0]], seconds_per_step: 4}}
  - {id: seatbelt,    at: "10:20", action: set_signal, params: {seatbelt_fastened: false, while: working, seconds: 20}}
  - {id: skip_break,  at: "10:30", action: skip_scheduled_break, params: {caption: "Ravi keeps working to catch up after the truck delay"}}   # D-006
  - {id: heat,        at: "11:00", action: note, params: {caption: "Heat index 45 °C"}}
  - {id: step_out,    at: "11:40", action: operator_leaves_seat, params: {minutes: 6, engine_on: true}}
  - {id: near_miss,   at: "12:10", action: await_voice_report}
  - {id: offline,     at: "13:00", action: set_network, params: {online: false}}
  - {id: online,      at: "13:08", action: set_network, params: {online: true}}
  - {id: end_shift,   at: "14:00", action: end_shift_summary}
```
`camera_or_sim_person`: if a live camera feed is active for the machine, the beat waits for camera proximity readings (up to 30 s) and otherwise falls back to the scripted simulated path. The console can **seek** to any beat: the player fast-forwards the world deterministically to that beat's time.

`fleet_tour.yaml`: switches focus to `WHL014` (Cat 950 GC, 2013, basic tier) at `PIL-MIN-01`, shows reduced capabilities and time-based idle classification, then triggers `sim scale` for 10,000 machines.

---

## 9. APIs

JSON over HTTP; WebSocket messages use the envelope `{ "type": str, "seq": int, "ts": iso, "machine_id": str|null, "site_id": str|null, "payload": object }`. Errors: `{ "error": { "code": str, "message": str } }` with appropriate status codes. All request/response bodies are pydantic models exported to `packages/contracts`.

### 9.1 Edge Gateway (`:8100`)
| Method & path | Purpose |
|---|---|
| GET `/health` | status, sim clock, network state |
| GET `/machines` · GET `/machines/{id}` | machine info + tier + active capabilities list |
| POST `/session/sign-in` `{operator_id, machine_id, pin, language}` | returns operator profile, capabilities, shift |
| POST `/session/sign-out` | |
| GET `/operators/{id}/profile` | profile, skill index, progress |
| GET `/operators/{id}/shift?date=` | tasks with `{p10, p50, p90, reasons[]}` and conditions |
| GET `/tasks/{id}/estimate` | current estimate incl. live remaining |
| POST `/checklist` | submit walkaround results |
| POST `/alerts/{event_id}/ack` | acknowledge |
| POST `/reports/parse` `{transcript, language}` | returns structured draft (online or offline parser, flag which) |
| POST `/reports` | save confirmed report |
| GET `/reports?operator_id=` | recent reports |
| GET `/insights/{operator_id}?range=shift|week` | time split, idle segments with reasons, fuel metrics vs baseline, anomalies with explanations, coaching points, positives |
| GET `/lessons` · GET `/lessons/{id}?lang=` · GET `/lessons/recommended?operator_id=` | |
| POST `/lessons/{id}/complete` `{operator_id, score, duration_s}` | |
| POST `/drills/results` | |
| GET `/training/slots?site_id=` · POST `/training/bookings` | instructor booking |
| POST `/assistant/ask` `{question, language, machine_id, operator_id}` | `{answer, citations: [{chunk_id, title, section}], answerable, mode: online|offline, language}` |
| POST `/assistant/intent` `{utterance, language}` | `{intent, slots}` for voice commands |
| POST `/proximity/camera` `{machine_id, distance_m, confidence, ts}` | camera proximity readings (≤ 5 Hz) |
| GET `/sync/status` | outbox size, last sync, network |
| WS `/ws/cab/{machine_id}` | cab channel |
| WS `/ws/site/{site_id}` | site entities for the map (5 Hz) + dispatch log |
| Demo control: POST `/demo/scenario/load {name}`, `/demo/play`, `/demo/pause`, `/demo/speed {x}`, `/demo/seek {beat_id}`, `/demo/network {online}`, GET `/demo/state` | |

**Cab WS message types:** `telemetry` (1 Hz: state, speed, seatbelt, proximity, heat index, task progress), `mode` (working|paused), `risk_update`, `alert`, `alert_cleared`, `idle_segment` (provisional/final), `insight`, `task_progress`, `estimate_update`, `lesson_offer`, `connectivity`, `sync`, `scenario_caption` (demo only; hidden unless console enables captions).

**Site WS message types:** `entities` (machines, trucks, workers with x/y/heading/state; machine proximity tier), `dispatch` (truck assigned/arrived/departed), `site_event` (P1/P2, incidents).

### 9.2 Fleet Service (`:8200`)
| Method & path | Purpose |
|---|---|
| POST `/ingest/intervals` (batch ≤ 500) · POST `/ingest/events` (batch) | idempotent by record id |
| GET `/sites` · GET `/sites/{id}/summary?date=` | progress, on-track status per machine |
| GET `/sites/{id}/idle-causes?date=` | idle minutes by reason with site-issue suggestions |
| GET `/sites/{id}/safety?date=` | incidents, near-misses, P1/P2, current risk bands |
| GET `/sites/{id}/trends?days=14` | aggregates respecting `privacy.yaml` |
| GET `/fleet/overview` | sites, machines by type/tier, active counts |
| GET `/fleet/patterns` | condition multipliers with counts |
| GET `/models/estimation/latest` · GET `/models/estimation/{version}/files/{name}` | model manifest + artefacts |
| GET `/scale/stats` | ingest rate, totals, bench results, 1.6 M projection |
| WS `/ws/fleet` | live ingest counters, site events |

### 9.3 Sync
The edge outbox stores unsynced intervals, shared events, reports and task summaries in SQLite. When online, a background task posts batches every 5 s (sim time-independent, wall clock) with retry and exponential back-off; records are marked synced on 2xx. `connectivity` and `sync` messages keep the cab UI updated.

---

## 10. Assistant

### 10.1 Knowledge base
`knowledge/` holds **team-authored** markdown (no copying of Caterpillar manuals or other copyrighted text). Each file has front matter `{id, title: {en, hi, ta}, machine_types: [...], section}` and is written in English; key safety files also have Hindi and Tamil versions (`*.hi.md`, `*.ta.md`). Required files (≈15): walkaround inspection; seatbelt and ROPS; swing radius and exclusion zones; spotter hand signals; truck loading procedure; idling and shutdown; cold-start warm-up; heat stress and hydration; working on wet/muddy ground; night operation and lights; refuelling safety; warning lights and what to do (generic, clearly labelled as sample indicator meanings); emergency stop and exit; reporting incidents and near-misses; fatigue. A banner in the UI and README states: "Sample manual content written for this prototype. A production system would use official Cat Operation & Maintenance Manuals."

### 10.2 Index and retrieval
- Chunk by heading, ≤ 350 words, 50-word overlap; chunk id `<file_id>#<n>`.
- Hybrid retrieval: BM25 (tokenised, lower-cased; Indic scripts tokenised by whitespace + punctuation) and dense embeddings (`paraphrase-multilingual-MiniLM-L12-v2`, cosine). Score = 0.5·norm_bm25 + 0.5·cosine; top-k 5; filter by `machine_types` containing the current machine type or `all`.
- Index built by `shiftmate assistant index` into `models/assistant/` and loaded at edge start-up (works offline).

### 10.3 Online answering
Call the LLM provider layer (`assistant/llm.py`; Gemini, model from `SHIFTMATE_LLM_MODEL`, JSON output mode, max output tokens 600, `temperature` 0). System prompt (store in `assistant/prompts/answer_system.md`) requires:
- Answer only from the provided sources; cite chunk ids used.
- If the sources do not contain the answer, set `answerable=false` and say so plainly, suggesting the supervisor or dealer.
- Never give instructions to bypass, disable or defeat safety systems (seatbelt switches, interlocks, alarms, cameras); refuse and restate the safety reason.
- Reply in the requested language, short sentences, maximum 5 steps.
- Output strict JSON `{answer, citations: [chunk_id], answerable}`.
Post-validation: parse JSON; every citation must be among the retrieved chunk ids; if parsing fails or citations are empty while `answerable=true`, return a refusal. Timeout 12 s, rate limit (429) or missing key → fall back to offline mode immediately; the UI shows the offline label.

### 10.4 Offline answering
If the network is off, the API key is missing, or the call fails: if the top chunk's combined score ≥ 0.55, return that chunk's text (in the requested language if a translated file exists, else English with a note), labelled `mode: offline`; otherwise refuse with an offline message.

### 10.5 Intents (voice commands)
Rule-based matcher first (keyword lists per language in `assistant/keywords/intents.yaml`): `next_task`, `time_left`, `report_problem`, `start_break`, `end_break`, `repeat_last`, `ack_alert`, `open_lessons`, `help`. If no match and online, LLM classification into the same intents or `question`; offline default `question`.

### 10.6 Assistant evaluation set
`backend/src/shiftmate/eval/assistant_eval.yaml`: 40 questions — 30 answerable (10 en, 10 hi, 10 ta; each with expected chunk ids and key facts) and 10 unanswerable (e.g. engine torque specs, prices, legal questions, bypass requests). Metrics: citation accuracy, key-fact coverage (LLM-as-judge with a fixed rubric prompt + manual spot-check list), refusal accuracy. The runner spaces calls to stay under the free-tier per-minute limit and caches every LLM response (answers and judge) on disk, keyed by prompt hash, so re-runs do not spend the daily quota. Without a key, only offline results are reported.

---

## 11. Frontend

### 11.1 Design system dependency
UI work begins only after `docs/DESIGN.md` and `frontend/packages/ui/src/tokens.css` exist (produced from the Claude Design brief). All colours, type, spacing, radii, elevation, motion and iconography come from tokens; **no hex values or font names in app code**. Safety semantics (P1–P4, risk bands, proximity tiers) map to dedicated semantic tokens defined in `DESIGN.md`.

### 11.2 Cab app (`apps/cab`) — tablet landscape, reference viewport 1280×800, must also work at 1024×768
Routes:
- `/start` — badge (QR via camera or PIN pad), language select, checklist.
- `/` (My Shift) — conditions summary, task list with range bars and reasons, active task progress, suggested breaks.
- `/safety` — risk level with contributing factors, active thresholds, recent alerts, camera proximity panel (enable camera, calibrate, live distance).
- `/report` — voice capture → transcript → structured draft → confirm/edit → saved; recent reports.
- `/insights` — "My Day": time-split bar, idle segments with reason chips and evidence, fuel per load vs usual (sparkline), coaching point, positives; week view.
- `/learn` — recommended lessons, catalogue, lesson player (narrated cards with speech synthesis, quiz), hazard drill (canvas), instructor booking, progress.
- `/ask` — push-to-talk and text input, answers with source chips, offline label.
Persistent elements: status rail (risk band, seatbelt, proximity, connectivity/sync, current mode), alert layer (takeover for P1, banner for P2, strip for P3), push-to-talk button reachable from every screen.
**Working mode** (from `mode` messages): navigation collapses; only status rail, active task line and alerts visible; voice commands remain available; lessons and insights hidden. **Paused mode** restores full navigation.
Offline: PWA pre-caches app shell, fonts, illustrations, lesson content, MediaPipe model and locale files; Dexie stores profile, shift, lessons, pending reports and last insights.
Speech: `SpeechRecognition.lang` = `en-IN` | `hi-IN` | `ta-IN`; show live transcript; every voice action has an equivalent large button. `speechSynthesis` voice selected by language with graceful fallback to English and on-screen text.
Camera proximity: MediaPipe ObjectDetector on the webcam at ~10 fps, `category == "person"`, score ≥ 0.5; distance `d = (f_px × 1.7 m) / bbox_height_px` using the largest person box; calibration: user stands at 3.0 m, `f_px = bbox_height_px × 3.0 / 1.7`, stored per device; smooth with an exponential moving average (α 0.4); post to `/proximity/camera` at ≤ 5 Hz. The camera feed shows the box and distance; this is the monocular estimate approach from Caterpillar's 2025 challenge.

### 11.3 Console app (`apps/console`) — desktop ≥ 1440 px wide
Routes: `/site/:siteId` (live site map + machine list + site events), `/supervisor/:siteId` (day summary, idle causes, safety overview, trends), `/fleet` (overview, patterns, scale demo with live ingest counter and projection), `/demo` (scenario load/play/pause/speed/seek beats, network toggle, captions toggle, camera status), `/eval` (renders `docs/EVAL.md` metrics).
Site map: SVG, site layout polygons from config, entities from `/ws/site`, machines drawn with swing-radius rings coloured by proximity tier, trucks with state, workers as dots; smooth interpolation between 5 Hz updates; click a machine for details (respecting privacy rules).

### 11.4 i18n
All user-facing strings in `packages/i18n/{en,hi,ta}.json` with namespaced keys (`alert.*`, `reason.*`, `insight.*`, `idle.*`, `ui.*`). Numbers and times formatted with `Intl` for the locale. Devanagari and Tamil must render with a font that supports them (from `DESIGN.md`). No string concatenation for sentences; use interpolation.

---

## 12. Evaluation (`shiftmate eval all` → `docs/EVAL.md`)

| Component | Data | Metrics | Target |
|---|---|---|---|
| Idle reasons | test days 36–42, all idle segments | accuracy, per-class precision/recall, confusion matrix, by sensor tier | ≥ 0.90 advanced, ≥ 0.75 basic |
| Anomaly | test days intervals vs `label_anomaly` | precision, recall, F1 overall and per type, by tier | P, R ≥ 0.80 |
| Estimation | test tasks | MAE (min), MAPE, p10–p90 coverage, per task type; top fleet patterns | MAPE ≤ 12%, coverage 75–85% |
| Assistant | eval set §10.6 | citation accuracy, key-fact coverage, refusal accuracy, per language, online vs offline | ≥ 0.85 / ≥ 0.90 refusals |
| Camera proximity | manual protocol: person at 2, 3, 4, 5, 6 m, 20 readings each | mean abs error by distance | ≤ 1.0 m |
| Scale | bench + scale run | per-machine CPU/tick, memory, uplink bytes/day, ingest records/s, 1.6 M projection | report |

`EVAL.md` reports actual results honestly with the date, seed and data sizes, including any target not met.

---

## 13. Testing

- **Backend unit tests** for every engine with hand-built tick sequences, including one test per idle reason and per sensor tier, alert policy pre-emption/cooldown, risk hysteresis, rule evaluator safety (rejects non-whitelisted expressions).
- **Simulator invariants** (§7.5) and determinism.
- **Contract tests:** JSON Schema export matches committed `packages/contracts` types (CI-style script `pnpm contracts:check`).
- **API tests** with FastAPI `TestClient` for all endpoints.
- **Frontend unit tests** (vitest) for alert layer behaviour, mode switching, i18n completeness (every key present in en/hi/ta).
- **End-to-end** (Playwright): run `ravi_shift` at 30× with simulated person path; assert each beat produces the expected UI state (e.g. idle chip "Waiting for truck" appears, P1 takeover shows for seatbelt, offline label on assistant answer, sync count returns to 0).
- Commands: `pnpm test:all` runs `uv run pytest` and `pnpm -r test` and Playwright.

---

## 14. Environment variables (`.env.example`)
```
SHIFTMATE_LLM_PROVIDER=gemini
GEMINI_API_KEY=
# exact model name from Google AI Studio
SHIFTMATE_LLM_MODEL=
SHIFTMATE_EDGE_PORT=8100
SHIFTMATE_FLEET_PORT=8200
SHIFTMATE_FLEET_URL=http://localhost:8200
SHIFTMATE_EDGE_URL=http://localhost:8100
SHIFTMATE_DATA_DIR=./data
SHIFTMATE_MODELS_DIR=./models
SHIFTMATE_SEED=7
SHIFTMATE_LIVE_WEATHER=0
VITE_EDGE_URL=http://localhost:8100
VITE_FLEET_URL=http://localhost:8200
```
The app must run fully without `GEMINI_API_KEY` (assistant and report parsing use offline modes and the UI says so).

---

## 15. Non-functional requirements
- **Latency:** safety tick → alert on cab screen ≤ 300 ms locally; camera frame → proximity alert ≤ 500 ms.
- **Determinism:** same scenario + seed ⇒ identical sequence of alerts and classifications.
- **Accessibility:** WCAG AA contrast minimum in day theme and higher in sunlight theme (per `DESIGN.md`); all actions reachable by touch and voice; reduced-motion respected.
- **Robustness:** WebSocket auto-reconnect with back-off; UI shows stale-data state after 3 s without telemetry.
- **Security basics:** CORS restricted to the two app origins; no secrets in frontend; rule evaluator sandboxed.
- **Performance:** cab app initial load ≤ 3 s on the demo laptop; site map ≥ 30 fps with 12 machines, 20 trucks, 14 workers.
