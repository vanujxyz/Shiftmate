# ShiftMate — Product Requirements Document (PRD)

Version 1.0 · Owner: Vanuj Gangrade · Context: Caterpillar hiring hackathon, problem statement "Smart Operator Assistant for CAT machinery"

This document describes **what** we are building and **why**. The Technical Requirements Document (`docs/TRD.md`) describes **how**. `CLAUDE.md` describes the build process. If this PRD and the TRD disagree about behaviour, the PRD wins on *what the user experiences*; the TRD wins on *implementation detail*.

---

## 1. Summary

ShiftMate is an operator-first, in-cab companion for Caterpillar machines. It follows an operator through the whole shift: it plans the day, keeps them safe in real working conditions, understands the reasons behind unusual machine behaviour instead of blaming the operator, helps them improve with short personalised lessons, and answers questions by voice from official manuals. It is designed so the same product could run on any of Caterpillar's ~1.6 million connected machines — any machine type, any age, any country, with or without internet.

**One-line pitch:** A companion that looks out for the operator, not one that watches them — built for every Cat operator in the world.

## 2. Problem

Construction machines are highly digitised and record rich telemetry, yet the tools available to the person in the cab remain basic. The data rarely reaches the operator in a form that helps them during the working day.

Specific problems we observed in the brief and sample data:

1. **Data does not reach the operator.** Engine hours, fuel, load cycles, idling and seatbelt status are recorded, but the operator gets no timely, useful help from them.
2. **Behaviour is judged without context.** In the sample data, rows with long idling (55–60 min), very few load cycles and an unfastened seatbelt are flagged as safety alerts. A naive system blames the operator. In reality an excavator often idles because no truck is available to load — a site logistics problem, not an operator problem. Leaving the engine running while the cab is empty, however, is a genuine safety and fuel issue. These must be told apart.
3. **Working conditions are ignored.** The brief asks for working conditions to be considered for safety and for task-time estimation. Heat, rain, ground condition, darkness and fatigue change what is safe and how long work takes.
4. **Screens can be a hazard.** The operator's eyes and hands are on the machine. Any interface that demands attention while the machine moves works against safety.
5. **One size does not fit a global fleet.** Machines differ in type, age and sensors; operators differ in language, climate and local rules.

## 3. Goals and non-goals

### Goals
- G1. Deliver all five expected outcomes of the brief as one connected experience: daily task dashboard, safety features (seatbelt, proximity, incident logging, working conditions), operator training hub, unusual behaviour detection, task time estimation.
- G2. Make the product feel like a **companion**: proactive, context-aware, coaching in tone, private to the operator first.
- G3. Design for the **real cab**: glanceable, glove-friendly, voice-first where it helps, readable in sunlight and at night, minimal interruptions.
- G4. Design for **Caterpillar's fleet scale**: any machine type, any sensor level, any language, works offline, learns across the fleet.
- G5. **Prove** it works with measured results on realistic data.

### Non-goals
- Connecting to real Caterpillar systems (Product Link, VisionLink, Cat AI Assistant, Helios) or real machine hardware.
- Automatically controlling the machine (stopping, braking, interlocks).
- Predictive maintenance, parts ordering, fleet-owner commercial tools, billing.
- Production-grade authentication, security hardening and multi-tenant administration.
- Reproducing Caterpillar's copyrighted manuals. The knowledge base is team-authored sample content that stands in for official manuals.

## 4. Users

### Primary persona — Ravi Kumar, excavator operator (Operator ID `OP1001`, machine `EXC001`)
The sample dataset's operator and machine are Ravi and his excavator.
- 9 years operating excavators; works on a highway project near Chennai.
- Most comfortable speaking Tamil, conversational in Hindi, reads basic English.
- 10-hour shifts, often 38–44 °C in summer, heavy rain during monsoon.
- Wears gloves, cab is loud and vibrates, sun glares on screens.
- Skilled with the machine, not interested in apps. Will ignore anything that nags or feels like spying.
- Wants: to finish his work safely, not be blamed for delays he didn't cause, get better and be recognised for it.

### Secondary persona — Meena Iyer, site supervisor
- Runs 12 machines and 20 trucks on the Chennai site.
- Wants: to know if the day is on track, where time is being lost, and whether anyone is at risk — without reading raw data.
- Must not become a surveillance channel against operators.

### Tertiary lens — Caterpillar fleet
- Wants: a product that scales to ~1.6 million connected machines of many types and ages, supports dealers and training, and strengthens safety culture.

## 5. Product principles
Every design and implementation decision is checked against these.

1. **Operator first.** Every feature is designed from the operator's seat. Supervisor and fleet features exist to make the operator's day better.
2. **Companion, not monitor.** Feedback goes to the operator first, in a coaching tone. Supervisors see aggregates and site-level causes, not minute-by-minute tracking. Safety-critical events are the exception and are shared.
3. **Eyes on the work.** While the machine is working, the interface shows only what can be understood at a glance. Everything else waits for a natural pause.
4. **Context before judgement.** Never flag behaviour without first checking the likely reason.
5. **Conditions change decisions.** Weather, ground, darkness and fatigue must visibly change safety thresholds and time estimates.
6. **Works everywhere.** Any machine type, any sensor level, any language, with or without internet.
7. **Honest intelligence.** Estimates show ranges and reasons. The assistant cites its sources and says when it does not know. Every model has measured results.

## 6. Feature requirements

Priority: **Must** = required for the demo and the brief; **Should** = strongly expected, part of the planned build; **Could** = include if everything else is complete and polished.

Each requirement has an ID used in the TRD, tests and commit messages.

### 6.1 Sign-in and profile (module: Start)
| ID | Requirement | Priority |
|---|---|---|
| F-START-01 | Operator signs in on any machine using an operator badge (QR code or 4-digit PIN in the demo). | Must |
| F-START-02 | Operator chooses interface and voice language: English, Hindi, Tamil. Choice is remembered in their profile. | Must |
| F-START-03 | The operator's profile (skills, training history, progress, language) follows the operator to any machine. | Must |
| F-START-04 | A short pre-start walkaround checklist (6–8 items) can be completed by tapping or by voice ("done", "problem"). Items flagged as a problem create a report. | Should |

### 6.2 My Shift — daily task dashboard
| ID | Requirement | Priority |
|---|---|---|
| F-SHIFT-01 | Show today's scheduled tasks in order: task type, location/zone, planned quantity, scheduled start. | Must |
| F-SHIFT-02 | Each task shows an estimated duration as a range (e.g. "2 h 10 m – 2 h 40 m") and a most-likely value. | Must |
| F-SHIFT-03 | Each estimate shows the top reasons in plain language (e.g. "Wet ground adds time", "Your experience saves time"). | Must |
| F-SHIFT-04 | Live progress for the active task (quantity done vs planned) and an updated remaining-time estimate. | Must |
| F-SHIFT-05 | Today's working conditions summary: temperature/heat index, rain, ground condition, daylight or night. | Must |
| F-SHIFT-06 | Suggested break times based on heat and continuous operation. | Should |

### 6.3 Safety Guard
| ID | Requirement | Priority |
|---|---|---|
| F-SAFE-01 | Seatbelt: if the machine moves or works with the seatbelt unfastened, raise a critical alert immediately. | Must |
| F-SAFE-02 | Proximity: detect people near the machine and warn in tiers (caution, danger, critical) based on distance and the machine's swing/travel zone. | Must |
| F-SAFE-03 | Live camera proximity demo: a webcam detects a real person and estimates distance, feeding the same proximity warnings. | Must |
| F-SAFE-04 | Working-conditions risk level: a live Green / Amber / Red risk level combining heat index, rain, ground, visibility, darkness, fatigue, proximity and seatbelt. | Must |
| F-SAFE-05 | Conditions tighten safety: at Amber and Red, proximity warning distances increase and break reminders become more frequent. | Must |
| F-SAFE-06 | Fatigue: warn after long continuous operation without a break; thresholds shorten in high heat. | Must |
| F-SAFE-07 | Engine running with nobody in the seat ("unattended running") is detected and treated as a safety event. | Must |
| F-SAFE-08 | Alert discipline: only one interrupting alert at a time; low-priority messages wait until the machine is paused; repeated alerts are suppressed for a cooldown period. | Must |
| F-SAFE-09 | Critical alerts are spoken aloud in the operator's language and must be acknowledged. | Must |

### 6.4 Quick Report — incident and near-miss logging
| ID | Requirement | Priority |
|---|---|---|
| F-REP-01 | Operator can report an incident or near-miss by speaking; the transcript is converted into a structured report (type, severity, short description). | Must |
| F-REP-02 | Time, machine, operator, location zone, task and weather are filled in automatically. | Must |
| F-REP-03 | Operator confirms or edits the report with large buttons before saving. | Must |
| F-REP-04 | Reports work offline and sync later. | Must |
| F-REP-05 | Recent reports list for the operator. | Should |

### 6.5 Smart Insights — unusual behaviour detection
| ID | Requirement | Priority |
|---|---|---|
| F-INS-01 | Detect idle periods (engine on, no productive work). | Must |
| F-INS-02 | Classify each idle period by likely reason: Warm-up, Scheduled break, Waiting for truck, Unattended running, Habit (unexplained idle while seated), Unknown. Each classification has a confidence and the evidence used. | Must |
| F-INS-03 | Respond differently by reason: Waiting for truck → reported to supervisor as a site issue and offered to operator as a learning moment, never as blame; Unattended running → safety reminder; Habit → gentle coaching; Warm-up and Break → no action. | Must |
| F-INS-04 | Detect unsafe operation patterns: moving with seatbelt unfastened, high travel speed near people, operating too long without a break, operating in extreme heat without breaks. | Must |
| F-INS-05 | Detect statistically unusual intervals compared with that operator's and machine's own normal (e.g. unusually high fuel per load cycle, unusually low productivity). | Must |
| F-INS-06 | Show fuel impact in plain terms: fuel per load cycle today vs the operator's usual, litres used while idle. | Must |
| F-INS-07 | "My Day" view for the operator: time split into working, waiting, warm-up, breaks and idle; top 1–2 coaching points; things that went well. | Must |
| F-INS-08 | Operator sees their detailed insights privately; supervisors see only site-level aggregates (see §8). | Must |

### 6.6 Learn & Grow — operator training hub
| ID | Requirement | Priority |
|---|---|---|
| F-LRN-01 | A catalogue of short lessons (1–3 minutes) in three formats: narrated illustrated step cards, quizzes, and hazard drills. All available in English, Hindi and Tamil. | Must |
| F-LRN-02 | Lessons are recommended based on detected behaviours (e.g. unattended running → "Shut down before you step out"). | Must |
| F-LRN-03 | Lessons are offered only during natural pauses (machine idle, waiting for truck, break), never while working. | Must |
| F-LRN-04 | Hazard drill: a simple simulation in which hazards appear (worker entering swing zone, truck reversing, ground edge) and the operator taps or says "stop"; reaction time and correct decisions are scored. | Must |
| F-LRN-05 | Instructor booking: view available sessions at the local Cat dealer training centre and book one. | Must |
| F-LRN-06 | Personal progress: lessons completed, drill scores over time, streaks, and improvement in the habits the lessons target. | Must |

### 6.7 Ask Cat — voice assistant
| ID | Requirement | Priority |
|---|---|---|
| F-ASK-01 | Operator asks questions by voice or text in English, Hindi or Tamil and hears/sees the answer in the same language. | Must |
| F-ASK-02 | Answers come only from the knowledge base (manual content) and show which section they came from. | Must |
| F-ASK-03 | If the knowledge base does not contain the answer, the assistant says so plainly and suggests who to ask. It never invents machine instructions. | Must |
| F-ASK-04 | Voice commands for common actions: "next task", "report a problem", "start break", "how long left", "repeat". | Must |
| F-ASK-05 | Offline mode: without internet, the assistant returns the most relevant manual section directly, clearly labelled as an offline answer, or says it cannot answer offline. | Must |
| F-ASK-06 | The assistant refuses requests to bypass safety systems. | Must |

### 6.8 Cab experience (applies to all operator screens)
| ID | Requirement | Priority |
|---|---|---|
| F-CAB-01 | Two modes: **Working mode** (machine moving/working) shows only a glanceable status strip, the active task and alerts; **Paused mode** (idle ≥ 30 s or engine off) unlocks the full interface. | Must |
| F-CAB-02 | Touch targets usable with work gloves; high contrast readable in direct sunlight; a night theme for dark conditions. | Must |
| F-CAB-03 | Persistent status: risk level, seatbelt, proximity state, connectivity, sync state. | Must |
| F-CAB-04 | Works without internet; shows clearly what is waiting to sync. | Must |
| F-CAB-05 | All text available in English, Hindi and Tamil. | Must |

### 6.9 Supervisor console
| ID | Requirement | Priority |
|---|---|---|
| F-SUP-01 | Live site map: machines, trucks and workers moving; machine swing zones coloured by proximity state. | Must |
| F-SUP-02 | Site day summary: task progress across machines, on-track/behind indicators. | Must |
| F-SUP-03 | Where time is lost: idle time by reason across the site (e.g. "3 h 20 m waiting for trucks today"), with a plain-language suggestion. | Must |
| F-SUP-04 | Safety overview: incidents, near-misses, critical alerts, current risk levels per machine. | Must |
| F-SUP-05 | Team trends shown as aggregates; individual operator detail only for safety-critical events. | Must |

### 6.10 Fleet scale (designed for ~1.6 million machines)
| ID | Requirement | Priority |
|---|---|---|
| F-FLT-01 | Machine profiles: excavator, wheel loader and dozer supported through configuration, each with its own definition of a load cycle, normal ranges, safety zones and thresholds. Adding a type means adding a profile, not changing code. | Must |
| F-FLT-02 | Sensor tiers: the product works on basic machines (only the sample columns), standard machines and advanced machines, turning features on or off and lowering confidence where data is missing. | Must |
| F-FLT-03 | Edge-first: all safety and behaviour logic runs on the machine side; only summaries and important events are sent to the fleet service. | Must |
| F-FLT-04 | Personal baselines: "normal" is learned per machine type, operator, task type and site. | Must |
| F-FLT-05 | Fleet learning: patterns learned across all machines (e.g. how much wet ground slows trenching) improve estimates for every operator; only summaries are shared. | Must |
| F-FLT-06 | Localisation: language, units and site safety rules configurable per site/country. | Must |
| F-FLT-07 | Scale demonstration: simulate thousands of machines sending summaries to the fleet service and show throughput, per-machine footprint and a calculated projection for 1.6 million machines. | Must |
| F-FLT-08 | Fleet overview screen: sites across countries, machine types, sensor tiers, and fleet-learned patterns. | Should |

## 7. Data requirements (product view)

The brief's sample table is the base schema and is kept exactly: `Timestamp, Machine ID, Operator ID, Engine Hours, Fuel Used (L), Load Cycles, Idling Time (min), Seatbelt Status, Safety Alert Triggered`. We were told we may extend it with any columns we deem necessary. Every added column must serve a named requirement:

| Added data | Serves |
|---|---|
| Tasks (type, quantity, schedule, actual duration) | My Shift, Time estimation |
| Environment (temperature, humidity, heat index, rain, wind, visibility, night, ground condition) | Safety risk level, Time estimation |
| Operator state (seat occupancy, continuous operation, experience, training history, language) | Fatigue, Idle reasons, Training, Estimation |
| Machine behaviour (RPM, travel speed, coolant temperature, proximity distances) | Unsafe patterns, Warm-up detection, Proximity |
| Site logistics (truck present in loading zone, truck waits) | Idle reasons ("Waiting for truck") |
| Events (alerts, incidents, near-misses, idle segments) | Incident logging, Insights, Supervisor |
| Machine metadata (type, model year, sensor tier, site) | Fleet scale, Profiles |

Interpretation assumptions (to confirm with mentors; recorded in `docs/DECISIONS.md`):
- A **load cycle** for an excavator or wheel loader means **one haul truck fully loaded**; for a dozer, one push cycle. This matches the sample magnitudes (≈10–12 per two hours).
- Each interval record **summarises the period since the previous record** for that machine.
- **Safety Alert Triggered = Yes** if any critical or urgent alert occurred in the interval. In the sample, it coincides with an unfastened seatbelt.
- The sample rows are illustrative; their fuel and engine-hour figures are not internally consistent, so they are kept as fixtures and validated against the schema, not the physics of the simulator.

## 8. Privacy and trust requirements
- P-01. Operator-level insights (idle habits, fuel efficiency, lesson history) are visible in the cab only to the signed-in operator.
- P-02. The supervisor console shows site-level aggregates and anonymised trends by default.
- P-03. Safety-critical events (critical alerts, incidents, near-misses, unattended running) are shared with the supervisor with operator ID, because safety overrides privacy.
- P-04. "Waiting for truck" idle time is always attributed to the site, never to the operator.
- P-05. Fleet learning uses only task summaries and aggregated statistics; no raw per-second data or personal details leave the machine.
- P-06. Privacy rules are configurable per site/country.

## 9. The demo story (what judges will see)

A scripted, reproducible scenario, "Ravi's shift", runs in the simulator with play/pause/speed controls. The cab app and the supervisor console run side by side. Beats, in order:

1. **07:00 Start.** Ravi signs in with his badge on EXC001, chooses Tamil. Pre-start checklist by voice.
2. **07:05 Cold start.** Engine idles to warm up → classified *Warm-up*, no nagging.
3. **07:15 My Shift.** Three tasks with ranges; rain forecast → "Wet ground adds about 20 minutes".
4. **08:10 Truck delay.** No truck for 18 minutes → *Waiting for truck*. Ravi is not blamed; Meena's console shows a truck shortage; Ravi is offered a 2-minute lesson while he waits.
5. **09:30 Worker in swing zone.** A real person walks in front of the webcam → caution, then danger, then critical; spoken alert in Tamil.
6. **10:20 Seatbelt.** Ravi unbuckles while moving → critical alert, acknowledged.
7. **11:00 Heat.** Heat index climbs to 45 °C → risk Amber, break suggested, proximity distances widen, remaining time extends.
8. **11:40 Steps out.** Engine left running with the cab empty for 6 minutes → *Unattended running*, safety reminder, lesson recommended.
9. **12:10 Near-miss report.** Ravi speaks a near-miss report; fields fill automatically; he confirms.
10. **13:00 Internet lost.** Console toggles internet off → assistant gives an offline manual answer; reports queue; internet back → everything syncs.
11. **14:00 End of shift.** Ravi's private "My Day": time split, fuel per load cycle vs his usual, one coaching point, one thing he did well, drill score.
12. **Fleet.** Switch to a wheel loader at an Australian mine with basic sensors → fewer features, lower confidence, still working. Scale demo: thousands of simulated machines streaming to the fleet service with a projection for 1.6 million.

## 10. Success metrics

### Product quality (measured on held-out simulated data; targets, reported honestly whatever the result)
- Idle-reason classification accuracy ≥ 90% on advanced-sensor machines, ≥ 75% on basic machines.
- Unusual behaviour detection precision and recall ≥ 0.80 against injected ground-truth events.
- Task time estimate: median absolute error ≤ 12% of actual duration; 75–85% of actual durations fall inside the predicted range.
- Assistant: ≥ 85% of answerable questions answered correctly with a correct citation; ≥ 90% of unanswerable questions correctly refused.
- Camera proximity: distance estimate within ±1 m at 2–6 m in a calibrated setup.

### Experience
- In Working mode, no screen requires reading more than one line to understand.
- No more than one interrupting alert on screen at any time.

### Hackathon
- All five expected outcomes visibly demonstrated within the scripted demo.
- Every technical choice can be justified by the team in Q&A.

## 11. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Synthetic data looks fake | Mechanism-based simulator (trucks arrive via a dispatch process, weather follows daily cycles, operators have personalities); invariant tests; injected events with ground truth. |
| Live demo fails | Scenario is deterministic and seekable; demo runs fully locally; backup video recorded; offline assistant mode. |
| Browser speech recognition quality varies by language | Every voice action has a tap alternative; transcripts are shown for confirmation. |
| Operators perceive monitoring | Privacy rules §8, coaching tone, site attribution for truck waits. |
| Alert fatigue | Alert policy with priorities, single interrupting alert, cooldowns, pause-only delivery for low priority. |
| Over-claiming scale | Scale shown as simulation plus calculation, clearly labelled. |

## 12. Out of scope (explicit)
Real Caterpillar system integration; real hardware and sensors; machine control; predictive maintenance; parts and commerce; production auth/security; custom speech model training; 3D machine simulator; real GPS; reproduction of Caterpillar manuals or trademarks beyond descriptive references.

## 13. Glossary
- **Load cycle** — one haul truck fully loaded (excavator, wheel loader); one push cycle (dozer).
- **Idle** — engine on, no productive hydraulic work and no travel.
- **Heat index** — "feels like" temperature combining air temperature and humidity.
- **Sensor tier** — how much data a machine can report: basic, standard, advanced.
- **Edge** — software running on or next to the machine, working without internet.
- **Fleet service** — central service that receives summaries from many machines.
