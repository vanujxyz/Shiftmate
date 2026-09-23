# Milestone 2 — Config and schemas

## What was built
Every rule, threshold, distance, site, machine type, lesson and checklist item now lives in plain YAML files under `config/`, and the backend checks them all when it starts: a typo, a missing translation, an unknown lesson trigger or an impossible distance stops it with a message naming the file. The shared data shapes (machines, operators, tasks, sensor ticks, the brief's interval rows, events, training records) are defined once in Python and turned into TypeScript types for the apps.

Main files:
- `config/`: 3 machine profiles, sensor tiers, 4 sites (Chennai, Pune, Pilbara, Tromsø), 12 safety rules, risk model, alert policy, idle rules, privacy, anomaly, estimation, 12 lessons (en/hi/ta with quizzes; one hazard drill with 7 scenes), 7-item checklist.
- `backend/src/shiftmate/assistant/keywords/intents.yaml`: voice command phrases in three languages.
- `backend/src/shiftmate/schema/`: `enums.py`, `config.py`, `reference.py`, `signals.py`, `intervals.py`, `events.py`, `training.py`.
- `backend/src/shiftmate/config_loader.py` and `shiftmate config validate`.
- Locale files: alert texts (title / action / spoken line), idle reasons, insight explanations, estimate reasons.
- `frontend/packages/contracts/src/generated.ts`: 69 TypeScript types.
- `docs/TRANSLATIONS_REVIEW.md`: 228 strings per language to review (UI and config text).

## How to test (PowerShell, repo folder)
```
uv run --directory backend shiftmate config validate
```
Expected: `Config is valid.` then 3 profiles, 4 sites (60 machines), 12 safety rules (P1 3, P2 6, P3 3), 12 lessons, 7 checklist items, 9 voice intents.

Try breaking it: open `config\risk_model.yaml`, change `bands: {green: [0, 39], ...` to `[0, 38]`, run the command again. It prints `Config is NOT valid.` naming `risk_model.yaml` ("risk bands must be contiguous"). Undo the change.

```
pnpm test:all      # backend 24 passed; frontend 13 passed; "Contracts are up to date."
pnpm lint:all      # no errors
pnpm i18n:review   # rewrites docs/TRANSLATIONS_REVIEW.md
```

## Tests run
Backend pytest 24/24 (10 config tests incl. four "bad config fails fast" cases, 7 schema tests incl. the four sample rows parsing with null extensions, 7 smoke). Vitest 13/13. Contracts check OK. Ruff, ESLint, tsc clean.

## Decisions
D-027 labels in a separate table · D-028 extra config files/fields · D-029 schema additions (proximity bearing, record id) · D-030 idle confidences · D-031 site layouts, climates, fleets · D-032 lesson content choices · D-033 alert text structure.

## Downloads
`yaml` (npm, dev only, for the translation review script).

## Known issues
- Hindi and Tamil are careful drafts; none is marked reviewed yet.
- Safety rule expressions are only checked for syntax when the rule evaluator arrives (milestone 4).
