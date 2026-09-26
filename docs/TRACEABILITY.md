# ShiftMate — requirement traceability

Every functional requirement in `docs/PRD.md` §6 is listed here with the code that builds it, the tests that check it and the demo beat that shows it (beat ids come from `scenarios/ravi_shift.yaml`; "fleet_tour" is `scenarios/fleet_tour.yaml`). Written in milestone 18.

Path shorthand: `be/` = `backend/src/shiftmate/`, `bt/` = `backend/tests/`, `cab/` = `frontend/apps/cab/src/`, `con/` = `frontend/apps/console/src/`, `ui/` = `frontend/packages/ui/src/`. Tests are written `file::test_name`; a frontend test file name alone means the requirement is covered by several cases in that file.

Summary: 62 requirements (58 Must, 4 Should). All 62 are built and tested. One Must has a measurement still open: F-SAFE-03's camera distance accuracy. `EVAL.md` reports the one session on disk (20 readings at 6 m, error 1.85 m), but that session was recorded during a live camera check on 2026-09-24 and may not be a proper protocol run. The full protocol (2–6 m, with a helper) still has to be done. The live camera path itself works and is unit-tested.

## 6.1 Start of shift

| ID | Pri | Code | Tests | Demo beat |
|---|---|---|---|---|
| F-START-01 | Must | `be/edge/app.py` (`/session/sign-in`), `be/edge/services.py`; `cab/screens/Start.tsx`, `cab/screens/BadgeScanner.tsx` (jsQR) | `bt/test_edge_api.py::test_sign_in_rules`; `cab/screens/screens12.test.tsx`; `e2e/ravi-shift.spec.ts` | sign_in |
| F-START-02 | Must | `cab/screens/Start.tsx`, `frontend/packages/i18n`; language stored in the operator profile (`be/edge/store.py`) | `bt/test_edge_api.py::test_profile_and_shift`; `i18n/completeness.test.ts`; `e2e/ravi-shift.spec.ts` (Tamil) | sign_in |
| F-START-03 | Must | `be/edge/services.py` (profile), `be/schema/api.py` | `bt/test_edge_api.py::test_profile_and_shift`, `::test_training_progress` | sign_in |
| F-START-04 | Should | `config/checklist.yaml`; `cab/screens/Start.tsx` (walkaround, tap or voice "done"/"problem") | `bt/test_edge_api.py::test_checklist_problem_creates_report`; `cab/voice/voice.test.tsx` | sign_in |

## 6.2 My Shift

| ID | Pri | Code | Tests | Demo beat |
|---|---|---|---|---|
| F-SHIFT-01 | Must | `be/edge/services.py` (shift plan), `cab/screens/MyShift.tsx`, `ui/tasks.tsx` | `bt/test_edge_api.py::test_profile_and_shift`; `cab/screens/screens12.test.tsx` | my_shift |
| F-SHIFT-02 | Must | `be/engines/estimation.py` (LightGBM quantiles), `be/fleet/training.py`, `ui/tasks.tsx` (range bar) | `bt/test_ml.py::test_predictions_are_ordered_ranges_with_reasons`; `ui/components.test.tsx` | my_shift |
| F-SHIFT-03 | Must | `be/engines/estimation.py` (reasons), `config/estimation.yaml` | `bt/test_ml.py::test_predictions_are_ordered_ranges_with_reasons` | my_shift ("wet ground adds time") |
| F-SHIFT-04 | Must | `be/engines/estimation.py` (remaining time), `be/edge/runtime.py`, `cab/screens/MyShift.tsx` | `bt/test_ml.py::test_remaining_time_blends_model_and_observed_rate` | truck_delay, heat (remaining time extends) |
| F-SHIFT-05 | Must | `be/util/heat_index.py`, `be/util/solar.py`, `be/sim/weather.py`, `cab/screens/MyShift.tsx` | `bt/test_sim.py::test_heat_index_matches_scenario_values`, `::test_polar_night_and_tropical_day` | my_shift, heat |
| F-SHIFT-06 | Should | site break plan (`config/sites/*.yaml`), `HEAT_NO_BREAK` / `FATIGUE_*` rules in `config/safety_rules.yaml`, `cab/screens/MyShift.tsx` | `bt/test_safety.py::test_heat_no_break`; `bt/test_machine_state.py::test_skipped_break_keeps_counting` | skip_break, heat |

## 6.3 Safety

| ID | Pri | Code | Tests | Demo beat |
|---|---|---|---|---|
| F-SAFE-01 | Must | `config/safety_rules.yaml` (`SEATBELT_MOVING`), `be/engines/safety.py`, `be/engines/rule_eval.py` | `bt/test_safety.py::test_seatbelt_needs_two_seconds_at_1hz`; `bt/test_rule_eval.py::test_seatbelt_rule`; `bt/test_headless.py::test_seatbelt_p1` | seatbelt |
| F-SAFE-02 | Must | `PROXIMITY_*` rules, `be/engines/safety.py`, `config/machine_profiles/*.yaml` (zones) | `bt/test_safety.py::test_proximity_tiers_escalate_along_the_demo_path`; `bt/test_headless.py::test_worker_near_escalates_caution_danger_critical` | worker_near |
| F-SAFE-03 | Must | `cab/camera/CameraPanel.tsx`, `cab/camera/runtime.ts` (MediaPipe), `cab/camera/geometry.ts`; `/proximity/camera` in `be/edge/app.py`; `be/eval/camera.py` | `cab/camera/camera.test.ts`; `bt/test_edge_live.py::test_fresh_camera_reading_overrides_the_sensor`; `bt/test_camera_eval.py` | worker_near (camera on). Accuracy protocol still to run properly (see summary) |
| F-SAFE-04 | Must | `be/engines/risk.py`, `config/risk_model.yaml`, `ui/rail.tsx` | `bt/test_risk.py` (all 9 cases) | heat |
| F-SAFE-05 | Must | `be/engines/risk.py` (thresholds by band), `be/engines/safety.py` | `bt/test_risk.py::test_thresholds_tighten_with_band_and_heat`; `bt/test_safety.py::test_wider_thresholds_catch_further_people` | heat |
| F-SAFE-06 | Must | `FATIGUE_WARN` / `FATIGUE_LIMIT`, `be/engines/machine_state.py` (continuous operation) | `bt/test_machine_state.py` (break/reset cases); `bt/test_risk.py::test_thresholds_tighten_with_band_and_heat` | skip_break, heat |
| F-SAFE-07 | Must | `UNATTENDED_RUNNING` rule, `be/engines/idle_reason.py` | `bt/test_safety.py::test_unattended_disabled_on_basic_and_needs_120s`; `bt/test_headless.py::test_step_out_unattended_running` | step_out |
| F-SAFE-08 | Must | `be/engines/alerts.py`, `config/alert_policy.yaml`, `cab/shell/AlertLayer.tsx` | `bt/test_alerts.py::test_never_more_than_one_interrupting_alert`, `::test_dedupe_within_30_seconds`, `::test_p3_held_while_working_and_delivered_when_paused`; `cab/shell/mode.test.tsx` | worker_near, seatbelt |
| F-SAFE-09 | Must | `cab/live/audio.ts`, `cab/live/effects.ts` (speech synthesis), `ui/alerts.tsx` (acknowledge) | `cab/live/effects.test.ts`; `bt/test_edge_api.py::test_alert_ack`; `bt/test_alerts.py::test_unacknowledged_p1_escalates_after_20s_and_is_shared` | worker_near, seatbelt (spoken in Tamil) |

## 6.4 Reports

| ID | Pri | Code | Tests | Demo beat |
|---|---|---|---|---|
| F-REP-01 | Must | `cab/screens/Report.tsx`, `cab/voice/recognizer.ts`, `be/engines/reports.py` (offline parser), `be/assistant/service.py` (online parser) | `bt/test_insight_engines.py::test_offline_report_parser`; `bt/test_assistant.py::test_spoken_report_online_and_its_fallback`; `e2e/ravi-shift.spec.ts` | near_miss |
| F-REP-02 | Must | `be/engines/reports.py` (auto-fill), `be/edge/services.py` | `bt/test_insight_engines.py::test_auto_fill_finds_zone_from_position`; `bt/test_edge_api.py::test_report_without_context_is_filled_on_arrival` | near_miss |
| F-REP-03 | Must | `cab/screens/Report.tsx` (confirm/edit) | `cab/screens/screens12.test.tsx`; `bt/test_edge_api.py::test_reports_parse_save_list` | near_miss |
| F-REP-04 | Must | `cab/offline/db.ts`, `cab/offline/reports.ts` (Dexie), `be/edge/sync.py` (outbox) | `cab/offline/offline.test.ts`; `bt/test_headless.py::test_offline_outbox_grows_then_drains`; `e2e/offline.spec.ts` | offline, online |
| F-REP-05 | Should | `cab/screens/Report.tsx` (recent list) | `bt/test_edge_api.py::test_reports_parse_save_list` | near_miss |

## 6.5 Insights

| ID | Pri | Code | Tests | Demo beat |
|---|---|---|---|---|
| F-INS-01 | Must | `be/engines/machine_state.py`, `be/engines/idle_reason.py` | `bt/test_idle_reason.py::test_short_idle_is_ignored`; `bt/test_history_replay.py::test_idling_within_engine_on_within_interval` | cold_start |
| F-INS-02 | Must | `be/engines/idle_reason.py`, `config/idle_rules.yaml`; eval `be/eval/idle.py` | `bt/test_idle_reason.py` (13 cases); `bt/test_sim.py::test_every_idle_reason_occurs` | cold_start, truck_delay, step_out |
| F-INS-03 | Must | `be/edge/runtime.py` (response by reason), `be/engines/lessons.py`, `be/fleet/aggregates.py` (site issue) | `bt/test_headless.py::test_truck_delay_is_a_site_issue_not_the_operator`, `::test_cold_start_warm_up_segment`; `bt/test_idle_reason.py::test_habit` | truck_delay, step_out |
| F-INS-04 | Must | `SEATBELT_MOVING`, `SPEED_NEAR_PERSON`, `FATIGUE_*`, `HEAT_NO_BREAK` in `config/safety_rules.yaml` | `bt/test_safety.py` (11 cases) | seatbelt, skip_break, heat |
| F-INS-05 | Must | `be/engines/anomaly.py` (IsolationForest + median/MAD), `config/anomaly.yaml`; eval `be/eval/anomaly.py` | `bt/test_insight_engines.py::test_z_scores_explanations_and_decision`, `::test_personal_baseline_and_fallback` | end_shift |
| F-INS-06 | Must | `be/engines/intervals.py` (fuel per cycle, idle litres), `ui/insights.tsx` | `bt/test_insight_engines.py::test_interval_features`; `bt/test_idle_reason.py::test_fuel_and_provisional_updates_at_1hz` | end_shift |
| F-INS-07 | Must | `cab/screens/MyDay.tsx`, `ui/insights.tsx` (time-split bar) | `cab/screens/screens12.test.tsx`; `cab/shell/demo.test.tsx` (end_shift opens My Day) | end_shift |
| F-INS-08 | Must | `config/privacy.yaml`, `be/fleet/aggregates.py`, `be/edge/sync.py` (upload filter) | `bt/test_edge_api.py::test_insights_are_private`; `bt/test_headless.py::test_uploads_respect_privacy`; `bt/test_fleet.py::test_private_events_never_enter_the_fleet` | end_shift, truck_delay |

## 6.6 Learning

| ID | Pri | Code | Tests | Demo beat |
|---|---|---|---|---|
| F-LRN-01 | Must | `config/lessons.yaml`, `cab/screens/learn/LessonPlayer.tsx`, `ui/illustrations.tsx`, `ui/learn.tsx` | `cab/screens/learn/learn.test.tsx`; `ui/illustrations.test.ts`; `bt/test_config.py::test_lessons_and_checklist_have_three_languages` | truck_delay (lesson offer) |
| F-LRN-02 | Must | `be/engines/lessons.py` (recommender) | `bt/test_insight_engines.py::test_recommend_by_count_and_recency_skipping_recent_completions`; `bt/test_edge_api.py::test_lessons` | step_out (recommends L-SHUTDOWN) |
| F-LRN-03 | Must | `be/engines/lessons.py` (offers only in long pauses), `cab/screens/learn/Offer.tsx` | `bt/test_insight_engines.py::test_lessons_offered_only_in_long_pauses`; `cab/screens/learn/learn.test.tsx` | truck_delay |
| F-LRN-04 | Must | `cab/screens/learn/Drill.tsx` (5 hazards, tap or "stop"), `be/edge/services.py` (scores) | `bt/test_edge_api.py::test_drills`; `cab/screens/learn/learn.test.tsx` | end_shift (drill score) |
| F-LRN-05 | Must | `cab/screens/learn/Booking.tsx`, `/training/slots` + booking in `be/edge/app.py` | `bt/test_edge_api.py::test_training_slots_and_booking` | paused-mode tour |
| F-LRN-06 | Must | `be/engines/lessons.py` (`streak_days`, `habit_counts`), `be/edge/services.py::build_progress`, `cab/screens/learn/Progress.tsx` | `bt/test_edge_api.py::test_training_progress`; `bt/test_insight_engines.py::test_training_progress_helpers` | end_shift |

## 6.7 Ask Cat

| ID | Pri | Code | Tests | Demo beat |
|---|---|---|---|---|
| F-ASK-01 | Must | `cab/screens/Ask.tsx`, `cab/voice/*`, `be/assistant/index.py` (multilingual retrieval), `knowledge/*.md` (+ `.hi`/`.ta`) | `bt/test_assistant.py::test_retrieval_finds_the_passage_in_any_written_language`; `cab/screens/ask.test.tsx` | offline (question asked by voice) |
| F-ASK-02 | Must | `be/assistant/service.py` (citations validated), `be/assistant/prompts/answer_system.md` | `bt/test_assistant.py::test_online_answer_with_valid_citations`, `::test_invalid_online_replies_become_refusals` | offline |
| F-ASK-03 | Must | `be/assistant/service.py` (refusal + who to ask) | `bt/test_assistant.py::test_the_model_saying_it_does_not_know_is_kept`, `::test_offline_refuses_below_the_score_bar`; `EVAL.md` assistant section | offline |
| F-ASK-04 | Must | `be/engines/intents.py`, `be/assistant/keywords/intents.yaml`, `cab/voice/commands.ts` | `bt/test_assistant.py::test_intents_try_the_rules_first_then_the_model`; `cab/voice/voice.test.tsx` | near_miss ("report a problem") |
| F-ASK-05 | Must | `be/assistant/service.py` (offline mode, score ≥ 0.55) | `bt/test_assistant.py::test_no_key_means_offline_by_design`, `::test_provider_trouble_falls_back_to_offline_at_once`, `::test_offline_falls_back_to_english_with_a_note` | offline |
| F-ASK-06 | Must | `be/assistant/service.py` (bypass guard) | `bt/test_assistant.py::test_safety_bypass_is_refused_in_both_modes` | offline |

## 6.8 Cab app

| ID | Pri | Code | Tests | Demo beat |
|---|---|---|---|---|
| F-CAB-01 | Must | `be/engines/machine_state.py` (paused after 30 s), `cab/shell/CabShell.tsx` | `bt/test_machine_state.py::test_paused_after_30s_idle_and_working_on_movement`; `cab/shell/mode.test.tsx` | every beat (mode switches) |
| F-CAB-02 | Must | `ui/tokens.css` (day, night, sunlight themes; 68–120 px glove targets), `ui/controls.tsx` | `ui/tokens.test.ts` (contrast); `e2e/kitchen-sink.spec.ts` | kitchen sink |
| F-CAB-03 | Must | `ui/rail.tsx`, `cab/shell/railProps.ts` | `cab/shell/railProps.test.ts` | every beat |
| F-CAB-04 | Must | PWA pre-cache (`frontend/apps/cab/vite.config.ts`), `cab/offline/*`, sync chip in the rail | `cab/offline/offline.test.ts`; `e2e/offline.spec.ts`; `bt/test_edge_live.py::test_network_toggle_reaches_the_cab` | offline, online |
| F-CAB-05 | Must | `frontend/packages/i18n` (en/hi/ta), `scripts/i18n/*.yaml` | `i18n/completeness.test.ts`; `bt/test_config.py::test_every_message_key_is_translated`; `cab/text.test.ts` | sign_in (Tamil) |

## 6.9 Supervisor console

| ID | Pri | Code | Tests | Demo beat |
|---|---|---|---|---|
| F-SUP-01 | Must | `con/screens/SiteMap.tsx`, `ui/sitemap.tsx` (SVG, 5 Hz with interpolation), `con/live/site.ts`, `/ws/site` | `bt/test_edge_live.py::test_site_socket_entities`; `con/live/site.test.ts` | worker_near |
| F-SUP-02 | Must | `be/fleet/aggregates.py` (site summary), `con/screens/Supervisor.tsx` | `bt/test_fleet.py::test_summary_on_track_and_behind` | truck_delay |
| F-SUP-03 | Must | `be/fleet/aggregates.py` (idle causes + suggestion) | `bt/test_fleet.py::test_idle_causes_never_name_operators`, `::test_truck_suggestion_names_zone_window_and_basis` | truck_delay |
| F-SUP-04 | Must | `be/fleet/aggregates.py` (safety), `con/screens/Supervisor.tsx` | `bt/test_fleet.py::test_safety_names_operators_only_where_allowed`, `::test_ws_fleet_counts_ingest_and_shows_p1` | seatbelt, near_miss |
| F-SUP-05 | Must | `config/privacy.yaml`, `be/fleet/aggregates.py` (trends) | `bt/test_fleet.py::test_trends_hide_small_groups` | end_shift |

## 6.10 Fleet and scale

| ID | Pri | Code | Tests | Demo beat |
|---|---|---|---|---|
| F-FLT-01 | Must | `config/machine_profiles/{excavator,wheel_loader,dozer}.yaml`, `be/schema/config.py` | `bt/test_config.py::test_all_configs_load`; `bt/test_sim.py::test_fleet_fixed_machines_and_ravi` | fleet_tour |
| F-FLT-02 | Must | `config/sensor_tiers.yaml`, feature gating in `be/engines/*` | `bt/test_config.py::test_sensor_tier_inheritance`; `bt/test_idle_reason.py::test_unattended_cannot_be_seen_on_basic`; `bt/test_insight_engines.py::test_basic_tier_features_are_dropped_not_faked` | fleet_tour (basic-tier loader) |
| F-FLT-03 | Must | `be/edge/runtime.py` (all logic on the edge), `be/edge/sync.py` (summaries only) | `bt/test_headless.py::test_uploads_respect_privacy`; `bt/test_fleet_scale.py::test_edge_uploads_reach_the_supervisor` | offline, online |
| F-FLT-04 | Must | `be/engines/anomaly.py` (personal baselines), `be/fleet/training.py` | `bt/test_insight_engines.py::test_personal_baseline_and_fallback`; `bt/test_ml.py::test_vectorised_baselines_match_the_reference_implementation` | end_shift |
| F-FLT-05 | Must | `be/fleet/patterns.py`, `be/fleet/training.py` (model registry) | `bt/test_ml.py::test_fleet_patterns_need_enough_tasks_and_machines`; `bt/test_fleet.py::test_model_registry` | my_shift, fleet_tour |
| F-FLT-06 | Must | `config/sites/*.yaml` (locale, languages, units, timezone, breaks), site rules in `config/safety_rules.yaml` | `bt/test_config.py::test_all_configs_load`; `bt/test_sim.py::test_tromso_winter_is_frozen_and_dark` | fleet_tour |
| F-FLT-07 | Must | `be/fleet/scale.py`, `be/sim/scale.py`, `be/sim/bench.py`, `/scale/stats` | `bt/test_fleet_scale.py::test_scale_run_streams_synthetic_machines`, `::test_projection_is_linear_and_labelled`, `::test_bench_runtime_small` | fleet_tour (10,000 machines, 1.6 M projection) |
| F-FLT-08 | Should | `con/screens/Fleet.tsx`, `/fleet/overview` in `be/fleet/app.py` | `bt/test_fleet.py::test_sites_and_overview`; `con/App.test.tsx` | fleet_tour |

## Cross-cutting checks

| Rule | Where it is enforced |
|---|---|
| Engines never read ground truth | `bt/test_ground_truth_guard.py` (Python and frontend) |
| Safety rules never use `eval` | `be/engines/rule_eval.py` (AST whitelist); `bt/test_rule_eval.py::test_rejects_unsafe_or_invalid` |
| Deterministic demo | `bt/test_headless.py::test_determinism`; `bt/test_sim.py::test_same_seed_same_world`; `e2e/ravi-shift.spec.ts` passes twice in a row |
| Design tokens only in app code | `ui/tokens.test.ts` (no hex or font literals outside `packages/ui`) |
| Contracts match the backend | `pnpm contracts:check` (part of `pnpm test:all`) |
| Metrics are measured, never typed in | `be/eval/*` writes `docs/EVAL.md`; `bt/test_ml.py::test_eval_sections_are_replaced_in_order` |
