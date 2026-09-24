"""What the edge REST endpoints compute: shift plan, insights, profile, slots (TRD §9.1).

- **Shift** (F-SHIFT-01..06): today's tasks in order, each with a p10–p50–p90 estimate and its
  top reasons (for the conditions forecast at the task's start), live remaining time for the
  active task, likely finish, current conditions, and break suggestions (scheduled breaks still
  ahead, plus a "take a water break now" when it is hot and there has been no break for an hour).
- **My Day** (F-INS-06/07/08, private to the signed-in operator): the day as a time split, idle
  segments with reasons and evidence, fuel per load vs the operator's usual, anything unusual,
  at most two coaching ideas and up to two specific things that went well. Week view: one summary
  per day from the machine's stored intervals.
- **Profile** (F-START-03): experience, skill index per task type, lesson and drill history.
- **Instructor slots** (F-LRN-05): a deterministic schedule at the site's training centre.
- **Training progress** (F-LRN-06): lessons finished, streak, drill facts, bookings, habit trends.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, time, timedelta
from typing import Any

import numpy as np

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.edge.live import LiveSite
from shiftmate.edge.resources import EdgeResources
from shiftmate.edge.runtime import MachineRuntime
from shiftmate.edge.store import EdgeStore
from shiftmate.engines.estimation import Estimate, predict, remaining
from shiftmate.engines.lessons import TriggerEvent, habit_codes, habit_counts, streak_days
from shiftmate.schema.api import (
    BookingView,
    CompletionView,
    Conditions,
    DrillView,
    EstimateReason,
    FuelMetrics,
    HabitTrend,
    IdleSegmentView,
    InsightNote,
    InsightsResponse,
    OperatorProfile,
    ShiftResponse,
    ShiftTask,
    SuggestedBreak,
    TaskEstimate,
    TimeSplitSegment,
    TrainingProgress,
)
from shiftmate.schema.enums import IdleReason, Language, SensorTier, TaskStatus
from shiftmate.schema.reference import Operator


def _estimate_model(e: Estimate, is_remaining: bool = False) -> TaskEstimate:
    return TaskEstimate(
        p10=round(e.p10, 1),
        p50=round(e.p50, 1),
        p90=round(e.p90, 1),
        reasons=[
            EstimateReason(key=r.key, feature=r.feature, minutes=round(r.minutes, 1))
            for r in e.reasons
        ],
        low_confidence=e.low_confidence,
        remaining=is_remaining,
    )


def conditions_model(c: dict[str, Any], site: LiveSite) -> Conditions:
    s = site.state
    fmt = lambda m: (datetime.combine(s.day, time(0, 0)) + timedelta(minutes=m)).strftime("%H:%M")  # noqa: E731
    return Conditions(
        ambient_temp_c=round(float(c["ambient_temp_c"]), 1),
        relative_humidity_pct=round(float(c["relative_humidity_pct"]), 0),
        heat_index_c=round(float(c["heat_index_c"]), 1),
        precipitation_mm_h=round(float(c["precipitation_mm_h"]), 1),
        wind_kmh=round(float(c["wind_kmh"]), 0),
        visibility_m=round(float(c["visibility_m"]), 0),
        is_night=bool(c["is_night"]),
        ground_condition=c["ground_condition"],
        sunrise=fmt(s.weather.sunrise_min) if 0 < s.weather.sunrise_min < 1440 else None,
        sunset=fmt(s.weather.sunset_min) if 0 < s.weather.sunset_min < 1440 else None,
    )


def task_row(
    cfg: ShiftMateConfig,
    res: EdgeResources,
    site: LiveSite,
    operator: dict[str, Any] | None,
    pt,
    when: datetime,
) -> tuple[dict[str, Any], bool]:
    """Estimation features for a task starting at `when` (and whether confidence is low)."""
    agent = site.world.agents[site.focus_id]
    machine = agent.machine
    c = site.forecast(when)
    op_id = operator["operator_id"] if operator else pt.task.operator_id
    skill, days = res.skill_index(op_id, pt.task.task_type, cfg.estimation.skill_window_days)
    truck = cfg.profiles[machine.machine_type].tasks[pt.task.task_type].truck_dependent
    row = {
        "task_type": pt.task.task_type,
        "machine_type": machine.machine_type.value,
        "model": machine.model,
        "planned_quantity": pt.task.planned_quantity,
        "quantity_unit": pt.task.quantity_unit.value,
        "operator_experience_years": operator["experience_years"] if operator else 5.0,
        "operator_skill_index": skill,
        "ground_condition": str(c["ground_condition"]),
        "heat_index_c": float(c["heat_index_c"]),
        "precipitation_mm_h": float(c["precipitation_mm_h"]),
        "is_night": float(bool(c["is_night"])),
        "site_id": site.site.site_id,
        "expected_truck_interval_min": site.site.trucks.dispatch_mean_interval_min
        if truck
        else 0.0,
        "hour_of_day": when.hour,
    }
    low = (
        machine.sensor_tier == SensorTier.BASIC
        or days < cfg.estimation.min_similar_days_for_confidence
    )
    return row, low


def build_shift(cfg: ShiftMateConfig, res: EdgeResources, site: LiveSite) -> ShiftResponse:
    rt = site.runtime
    agent = site.world.agents[site.focus_id]
    now = site.now
    operator = res.operator_row(
        rt.operator_id or (agent.plan.operator_id if agent.plan else "") or ""
    )
    planned = agent.plan.tasks if agent.plan else []
    rows, lows, index = [], [], []
    for i, pt in enumerate(planned):
        if pt.task.status == TaskStatus.DONE:
            continue
        when = (
            max(pt.task.scheduled_start, now)
            if pt.task.actual_start is None
            else pt.task.actual_start
        )
        row, low = task_row(cfg, res, site, operator, pt, when)
        rows.append(row)
        lows.append(low)
        index.append(i)
    estimates: dict[int, Estimate] = {}
    if res.estimation is not None and rows:
        for i, e in zip(index, predict(res.estimation, rows, cfg.estimation, lows), strict=True):
            estimates[i] = e
    tasks: list[ShiftTask] = []
    left = np.zeros(3)
    for i, pt in enumerate(planned):
        est = estimates.get(i)
        is_remaining = False
        if est is not None and pt.task.status == TaskStatus.ACTIVE:
            est = remaining(
                est, pt.task.planned_quantity, pt.progress, pt.work_seconds / 60, cfg.estimation
            )
            is_remaining = True
        if est is not None:
            left += [est.p10, est.p50, est.p90]
        tasks.append(
            ShiftTask(
                task=pt.task,
                estimate=_estimate_model(est, is_remaining) if est is not None else None,
                progress_qty=round(pt.progress, 2),
                zone_decal=pt.task.zone_id,
            )
        )
    likely = (
        TaskEstimate(
            p10=round(left[0], 1), p50=round(left[1], 1), p90=round(left[2], 1), reasons=[]
        )
        if left.any()
        else None
    )
    conditions = site.world.conditions(now)
    breaks: list[SuggestedBreak] = []
    minutes_since = rt.last_step.state.minutes_since_break if rt.last_step else 0.0
    if (
        float(conditions["heat_index_c"]) >= cfg.risk_model.heat_fatigue_override.heat_index_gte
        and minutes_since >= 60
    ):
        breaks.append(
            SuggestedBreak(at=now.strftime("%H:%M"), minutes=15, reason_key="shift.break_heat")
        )
    for b in site.site.shift.breaks:
        start = site.local(b.start)
        if start > now:
            breaks.append(
                SuggestedBreak(
                    at=b.start.strftime("%H:%M"),
                    minutes=b.minutes,
                    reason_key="shift.break_scheduled",
                )
            )
    return ShiftResponse(
        date=site.scenario.date.isoformat(),
        operator_id=rt.operator_id or "",
        machine_id=site.focus_id,
        conditions=conditions_model(conditions, site),
        tasks=tasks,
        likely_finish=likely,
        breaks=breaks,
    )


def build_profile(
    cfg: ShiftMateConfig,
    res: EdgeResources,
    store: EdgeStore,
    operator_id: str,
    language: Language | None = None,
) -> OperatorProfile | None:
    row = res.operator_row(operator_id)
    if row is None:
        return None
    certs = [c for c in str(row.get("certifications", "")).split(",") if c]
    operator = Operator(
        operator_id=row["operator_id"],
        name=row["name"],
        preferred_language=row["preferred_language"],
        experience_years=row["experience_years"],
        home_site_id=row["home_site_id"],
        certifications=certs,
    )
    skills: dict[str, float] = {}
    for machine_type in certs:
        for task_type in cfg.profiles[machine_type].task_types:
            value, days = res.skill_index(operator_id, task_type, cfg.estimation.skill_window_days)
            if days:
                skills[task_type] = round(value, 2)
    completions = store.list_completions(operator_id)
    return OperatorProfile(
        operator=operator,
        language=language or operator.preferred_language,
        skill_index=skills,
        lessons_completed=len({c["lesson_id"] for c in completions}),
        drills_done=len(store.list_drills(operator_id)),
        recent_lessons=[c["lesson_id"] for c in completions[-5:]],
    )


def _idle_reason_at(rt: MachineRuntime, start: datetime, end: datetime) -> str:
    """Reason of the idle segment overlapping [start, end) the most ('working' if none: <60 s)."""
    best, best_overlap = None, 0.0
    candidates = list(rt.idle_today)
    open_seg = rt.pipeline.idle.peek(end)
    if open_seg is not None:
        candidates.append(open_seg)
    for seg in candidates:
        overlap = (min(end, seg.end) - max(start, seg.start)).total_seconds()
        if overlap > best_overlap:
            best, best_overlap = seg.reason.value, overlap
    return best or "working"


def build_insights(
    cfg: ShiftMateConfig,
    res: EdgeResources,
    site: LiveSite,
    store: EdgeStore,
    operator_id: str,
    range_: str = "shift",
) -> InsightsResponse:
    rt = site.runtime
    split: list[TimeSplitSegment] = []
    for kind, start, end in rt.timeline:
        k = _idle_reason_at(rt, start, end) if kind == "idle" else kind
        minutes = (end - start).total_seconds() / 60
        if split and split[-1].kind == k and split[-1].end == start:
            split[-1].end = end
            split[-1].minutes = round(split[-1].minutes + minutes, 2)
        else:
            split.append(TimeSplitSegment(kind=k, start=start, end=end, minutes=round(minutes, 2)))
    totals: dict[str, float] = {}
    for s in split:
        totals[s.kind] = round(totals.get(s.kind, 0.0) + s.minutes, 1)
    segments = [
        IdleSegmentView(
            start=s.start,
            end=s.end,
            minutes=round(s.duration_s / 60, 1),
            reason=s.reason,
            confidence=s.confidence,
            evidence=s.evidence,
            fuel_l=round(s.fuel_l, 2),
        )
        for s in rt.idle_today
    ]
    intervals = rt.intervals_today
    fuel = sum(r.fuel_used_l for r in intervals)
    loads = sum(r.load_cycles for r in intervals)
    idle_fuel = sum(s.fuel_l for s in rt.idle_today)
    task_types = Counter(r.task_type for r in intervals if r.task_type)
    main_task = task_types.most_common(1)[0][0] if task_types else None
    base = res.baseline_for(
        operator_id, rt.machine.machine_type.value, main_task, site.site.site_id
    )
    usual = base.get("fuel_per_load_cycle_l", (None, None))[0]
    fuel_metrics = FuelMetrics(
        fuel_l=round(fuel, 1),
        idle_fuel_l=round(idle_fuel, 1),
        fuel_per_load_l=round(fuel / loads, 2) if loads else None,
        usual_fuel_per_load_l=round(usual, 2) if usual else None,
        loads=int(loads),
    )
    coaching: list[InsightNote] = []
    habit_min = sum(s.duration_s for s in rt.idle_today if s.reason == IdleReason.HABIT) / 60
    empty_min = (
        sum(s.duration_s for s in rt.idle_today if s.reason == IdleReason.UNATTENDED_RUNNING) / 60
    )
    if empty_min >= 2:
        coaching.append(
            InsightNote(
                key="insight.idea_shutdown",
                values={"minutes": round(empty_min)},
                lesson_id="L-SHUTDOWN",
            )
        )
    if habit_min >= 5 and len(coaching) < 2:
        coaching.append(
            InsightNote(
                key="insight.idea_short_stops",
                values={"minutes": round(habit_min)},
                lesson_id="L-IDLE-FUEL",
            )
        )
    for a in rt.anomalies_today:
        if len(coaching) >= 2 or not a["explanations"]:
            continue
        top = a["explanations"][0]
        coaching.append(
            InsightNote(
                key=top["message_key"],
                values={"value": round(top["value"] or 0, 2), "usual": round(top["usual"] or 0, 2)},
            )
        )
    positives: list[InsightNote] = []
    planned = site.world.agents[site.focus_id].plan
    for pt in planned.tasks if planned else []:
        if pt.task.status == TaskStatus.DONE:
            positives.append(
                InsightNote(
                    key="insight.good_task_done",
                    values={
                        "done": round(pt.progress),
                        "planned": round(pt.task.planned_quantity),
                        "unit": pt.task.quantity_unit.value,
                        "task_type": pt.task.task_type,
                    },
                )
            )
            break
    if (
        fuel_metrics.fuel_per_load_l
        and fuel_metrics.usual_fuel_per_load_l
        and fuel_metrics.fuel_per_load_l < fuel_metrics.usual_fuel_per_load_l
    ):
        positives.append(
            InsightNote(
                key="insight.good_fuel_per_load",
                values={
                    "value": fuel_metrics.fuel_per_load_l,
                    "usual": fuel_metrics.usual_fuel_per_load_l,
                },
            )
        )
    belt_off = sum(r.seatbelt_unfastened_working_s or 0 for r in intervals)
    if intervals and belt_off == 0 and len(positives) < 2:
        positives.append(InsightNote(key="insight.good_seatbelt"))
    days: list[dict[str, Any]] = []
    if range_ == "week":
        hist = res.history_intervals
        if not hist.empty:
            mine = hist[hist.operator_id == operator_id].copy()
            tz = site.world.tz
            mine["day"] = mine["timestamp"].dt.tz_convert(tz).dt.date
            for day in sorted(mine["day"].unique())[-6:]:
                g = mine[mine["day"] == day]
                days.append(_day_summary(str(day), g.to_dict("records")))
        days.append(
            _day_summary(site.scenario.date.isoformat(), [r.model_dump() for r in intervals])
        )
    return InsightsResponse(
        operator_id=operator_id,
        range="week" if range_ == "week" else "shift",
        totals_min=totals,
        time_split=split,
        idle_segments=segments,
        fuel=fuel_metrics,
        anomalies=rt.anomalies_today,
        coaching=coaching[:2],
        positives=positives[:2],
        days=days,
    )


def _day_summary(day: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    fuel = sum(r["fuel_used_l"] for r in rows)
    loads = sum(r["load_cycles"] for r in rows)
    return {
        "day": day,
        "engine_on_min": round(sum(r["engine_on_min"] or 0 for r in rows), 0),
        "working_min": round(sum(r["working_min"] or 0 for r in rows), 0),
        "truck_wait_min": round(sum(r["idle_truck_wait_min"] or 0 for r in rows), 0),
        "short_stops_min": round(sum(r["idle_habit_min"] or 0 for r in rows), 0),
        "loads": int(loads),
        "fuel_per_load_l": round(fuel / loads, 2) if loads else None,
    }


def training_slots(cfg: ShiftMateConfig, site_id: str, start_day: datetime) -> list[dict[str, Any]]:
    """Two instructor sessions a day for the next 10 days (deterministic, generic names)."""
    site = cfg.sites[site_id]
    topics = [lesson for lesson in cfg.lessons.lessons if lesson.format.value != "drill"]
    out = []
    for d in range(1, 11):
        day = (start_day + timedelta(days=d)).date()
        for n, hour in enumerate((9, 14)):
            lesson = topics[(d * 2 + n) % len(topics)]
            start = datetime.combine(day, time(hour, 0), tzinfo=start_day.tzinfo)
            out.append(
                {
                    "slot_id": f"SLOT-{site_id}-{day:%Y%m%d}-{n + 1}",
                    "dealer_centre": site.training_centre,
                    "site_id": site_id,
                    "start": start.isoformat(),
                    "topic": lesson.id,
                    "topic_title": lesson.title.model_dump(),
                    "seats_left": 6,
                }
            )
    return out


def build_progress(
    cfg: ShiftMateConfig, res: EdgeResources, store: EdgeStore, site: LiveSite, operator_id: str
) -> TrainingProgress:
    """Training progress (F-LRN-06): lessons finished, streak, drill facts over time, bookings,
    and how often each finished lesson's habits were seen last week and this week."""
    now = site.now

    def local(ts: str) -> datetime:  # the store keeps UTC; the cab shows site time
        return datetime.fromisoformat(ts).astimezone(now.tzinfo)

    completions = store.list_completions(operator_id)
    drills = store.list_drills(operator_id)
    days = [local(c["ts"]).date() for c in completions] + [local(d["ts"]).date() for d in drills]

    events: list[TriggerEvent] = []
    hist = res.history_events
    if not hist.empty:
        for r in hist[hist.operator_id == operator_id].itertuples():
            events.append(TriggerEvent(r.ts.to_pydatetime(), r.code))
    for e in store.list_events(operator_id=operator_id, since=now - timedelta(days=14)):
        events.append(TriggerEvent(datetime.fromisoformat(e["ts"]), e["code"] or ""))
    habits = []
    for lesson_id in dict.fromkeys(c["lesson_id"] for c in completions):
        codes = habit_codes(cfg.lessons, lesson_id)
        if codes:
            previous, this = habit_counts(events, codes, now)
            habits.append(
                HabitTrend(lesson_id=lesson_id, codes=codes, previous_week=previous, this_week=this)
            )

    slots = {s["slot_id"]: s for s in store.list_slots(site.site.site_id)}
    bookings = []
    for b in store.list_bookings(operator_id):
        slot = slots.get(b["slot_id"], {})
        bookings.append(
            BookingView(
                booking_id=b["booking_id"],
                slot_id=b["slot_id"],
                dealer_centre=slot.get("dealer_centre"),
                start=slot.get("start"),
                topic=slot.get("topic"),
                status=b["status"],
            )
        )
    bookings.sort(key=lambda b: (b.start is None, b.start or now))

    return TrainingProgress(
        operator_id=operator_id,
        lessons_done=len({c["lesson_id"] for c in completions}),
        lessons_total=len(cfg.lessons.lessons),
        streak_days=streak_days(days, now.date()),
        completed=[
            CompletionView(
                lesson_id=c["lesson_id"],
                ts=local(c["ts"]),
                score=c["score"],
                duration_s=c["duration_s"],
            )
            for c in completions
        ],
        drills=[
            DrillView(
                drill_id=d["drill_id"],
                ts=local(d["ts"]),
                correct=d["data"]["correct"],
                total=d["data"]["total"],
                mean_reaction_ms=d["data"].get("mean_reaction_ms"),
            )
            for d in drills
        ],
        bookings=bookings,
        habits=habits,
    )
