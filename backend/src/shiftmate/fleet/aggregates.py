"""Supervisor views computed from what the machines uploaded (TRD §9.2; PRD F-SUP-02…05, §8).

Every function here is pure: DataFrames and config in, a response model out. The Fleet
Service's routes fetch the rows from the store (`fleet/store.py`) and call these.

- **Site day summary** (F-SUP-02). Per machine: its tasks with progress and an on-track status.
  A task's expected duration is the planned quantity × the fleet's median minutes per unit for
  that task type on that machine type (a dozer clears ground faster than an excavator) over the
  previous `summary.baseline_days`; task type alone when there are too few. An active task is
  *behind* when the time it has taken so far is more than the time its progress should have
  taken, plus a tolerance and a few minutes of slack (fleet.yaml; D-063).
- **Where time is lost** (F-SUP-03). Idle minutes by reason across the site. The lead is the
  biggest *lost-time* reason (breaks and warm-up are needed time). Truck waits are a site issue
  (P-04): the view never names operators. The truck suggestion names the zone and the
  `window_h`-hour window with the most waiting today; its "would likely save" range is the
  quartile range of the waiting in that zone and window on today and similar recent days — the
  time one more truck there could have recovered at most (D-064).
- **Safety overview** (F-SUP-04). P1 and P2 alerts, incidents, near misses, unattended running,
  site issues, reports, and each machine's risk band. The operator is named only for the event
  kinds `privacy.yaml → supervisor_sees_operator_detail_for` lists (P-03); otherwise null.
- **Trends** (F-SUP-05). Daily site aggregates and groups by operator experience. Any day or
  group with fewer operators than `supervisor_aggregates_min_group_size` is returned as
  suppressed, without numbers (P-02). Truck waits never appear in an operator group (P-04).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.schema.config import Site
from shiftmate.schema.enums import IdleReason
from shiftmate.schema.fleet import (
    HourMinutes,
    IdleCause,
    IdleCausesResponse,
    MachineDaySummary,
    MachineRisk,
    ReportView,
    SafetyEventView,
    SafetyResponse,
    SiteSummary,
    Suggestion,
    TaskProgressView,
    TrendDay,
    TrendGroup,
    TrendsResponse,
)

IDLE_COLUMNS = {
    "idle_warmup_min": IdleReason.WARM_UP,
    "idle_break_min": IdleReason.SCHEDULED_BREAK,
    "idle_truck_wait_min": IdleReason.WAITING_FOR_TRUCK,
    "idle_unattended_min": IdleReason.UNATTENDED_RUNNING,
    "idle_habit_min": IdleReason.HABIT,
    "idle_unknown_min": IdleReason.UNKNOWN,
}
TRACK_ORDER = ["behind", "unknown", "on_track", "not_started", "done"]  # worst first


def _f(x: Any) -> float:
    return 0.0 if x is None or pd.isna(x) else float(x)


def _local(ts: pd.Series, tz: str) -> pd.Series:
    return pd.to_datetime(ts, utc=True).dt.tz_convert(tz)


def _hhmm(hour: int) -> str:
    return f"{hour % 24:02d}:00"


def risk_band(cfg: ShiftMateConfig, score: Any) -> str | None:
    if score is None or pd.isna(score):
        return None
    for band, (lo, hi) in cfg.risk_model.bands.items():
        if lo <= int(score) <= hi:
            return band.value
    return None


# --- site day summary ---------------------------------------------------------------------------


def baselines(cfg: ShiftMateConfig, done: pd.DataFrame) -> dict[tuple[str, str | None], float]:
    """Fleet median minutes per unit by (task type, machine type), and by task type alone
    (key `(task_type, None)`) as the fallback. A group needs `min_baseline_tasks` tasks."""
    out: dict[tuple[str, str | None], float] = {}
    if done.empty:
        return out
    need = cfg.fleet.summary.min_baseline_tasks
    d = done.assign(per_unit=done.actual_duration_min / done.planned_quantity)
    for task_type, g in d.groupby("task_type"):
        if len(g) >= need:
            out[(str(task_type), None)] = float(g.per_unit.median())
    for (task_type, machine_type), g in d.groupby(["task_type", "machine_type"]):
        if len(g) >= need:
            out[(str(task_type), str(machine_type))] = float(g.per_unit.median())
    return out


def site_summary(
    cfg: ShiftMateConfig,
    site: Site,
    day: date,
    machines: pd.DataFrame,
    operators: pd.DataFrame,
    tasks: pd.DataFrame,
    intervals: pd.DataFrame,
    per_unit: dict[tuple[str, str | None], float],
) -> SiteSummary:
    s = cfg.fleet.summary
    names = dict(zip(operators.operator_id, operators.name, strict=False))
    ids = list(machines.machine_id)
    for extra in list(intervals.get("machine_id", [])) + list(tasks.get("machine_id", [])):
        if extra not in ids:
            ids.append(extra)
    roster = machines.set_index("machine_id") if not machines.empty else pd.DataFrame()
    out: list[MachineDaySummary] = []
    for machine_id in ids:
        iv = intervals[intervals.machine_id == machine_id] if not intervals.empty else intervals
        tk = tasks[tasks.machine_id == machine_id] if not tasks.empty else tasks
        last_seen = pd.Timestamp(iv["timestamp"].max()).to_pydatetime() if len(iv) else None
        operator = None
        if len(iv) and iv.operator_id.notna().any():
            operator = str(iv.operator_id.mode().iloc[0])
        elif len(tk) and tk.operator_id.notna().any():
            operator = str(tk.operator_id.iloc[0])
        m = roster.loc[machine_id] if machine_id in roster.index else None
        machine_type = None if m is None else str(m.machine_type)
        views = []
        for t in tk.itertuples():
            done_qty = _f(iv.loc[iv.task_id == t.task_id, "task_progress_qty"].sum())
            if t.status == "done":
                done_qty = _f(t.done_qty) or _f(t.planned_quantity) or done_qty
            planned = _f(t.planned_quantity) or None
            expected = per_unit.get((t.task_type, machine_type), per_unit.get((t.task_type, None)))
            expected_min = round(expected * planned, 1) if expected and planned else None
            started = t.actual_start if not pd.isna(t.actual_start) else None
            worked = iv.loc[iv.task_id == t.task_id]
            if started is None and len(worked):
                started = worked.interval_start.min()
            elapsed = None
            if t.status == "done" and not pd.isna(t.actual_duration_min):
                elapsed = float(t.actual_duration_min)
            elif started is not None and last_seen is not None:
                elapsed = max(
                    0.0, (pd.Timestamp(last_seen) - pd.Timestamp(started)).total_seconds() / 60
                )
            if t.status == "done":
                track = "done"
            elif done_qty <= 0 and (elapsed is None or t.status == "scheduled"):
                track = "not_started"
            elif expected_min is None or planned is None or elapsed is None:
                track = "unknown"
            else:
                should_take = expected_min * min(done_qty / planned, 1.0)
                limit = should_take * (1 + s.behind_tolerance) + s.behind_slack_min
                track = "behind" if elapsed > limit else "on_track"
            views.append(
                TaskProgressView(
                    task_id=t.task_id,
                    task_type=t.task_type,
                    zone_id=t.zone_id,
                    planned_quantity=planned,
                    done_quantity=round(done_qty, 2),
                    unit=t.quantity_unit,
                    status=t.status,
                    progress_pct=round(100 * min(done_qty / planned, 1.0), 1) if planned else None,
                    expected_min=expected_min,
                    elapsed_min=round(elapsed, 1) if elapsed is not None else None,
                    track=track,
                )
            )
        tracks = [v.track for v in views] or ["not_started"]
        out.append(
            MachineDaySummary(
                machine_id=machine_id,
                machine_type=None if m is None else m.machine_type,
                model=None if m is None else m.model,
                sensor_tier=None if m is None else m.sensor_tier,
                operator_id=operator,
                operator_name=names.get(operator) if operator else None,
                tasks=views,
                engine_on_min=round(_f(iv.engine_on_min.sum()) if len(iv) else 0.0, 1),
                working_min=round(_f(iv.working_min.sum()) if len(iv) else 0.0, 1),
                idle_min=round(_f(iv.idling_time_min.sum()) if len(iv) else 0.0, 1),
                last_seen=last_seen,
                track=min(tracks, key=TRACK_ORDER.index),
            )
        )
    all_tasks = [t for m in out for t in m.tasks]
    return SiteSummary(
        site_id=site.site_id,
        date=day,
        timezone=site.timezone,
        machines=out,
        tasks_total=len(all_tasks),
        tasks_done=sum(t.track == "done" for t in all_tasks),
        tasks_behind=sum(t.track == "behind" for t in all_tasks),
        tasks_on_track=sum(t.track == "on_track" for t in all_tasks),
    )


# --- where time is lost -------------------------------------------------------------------------


def _zone_windows(iv: pd.DataFrame, zones: dict[str, str], tz: str, window_h: int) -> pd.DataFrame:
    """Truck-wait minutes per (local day, zone, window start hour), windows sliding by an hour."""
    if iv.empty:
        return pd.DataFrame(columns=["day", "zone_id", "start_h", "minutes"])
    d = iv[iv.idle_truck_wait_min.fillna(0) > 0].copy()
    if d.empty:
        return pd.DataFrame(columns=["day", "zone_id", "start_h", "minutes"])
    local = _local(d.interval_start, tz)
    d["day"] = local.dt.date
    d["hour"] = local.dt.hour
    d["zone_id"] = d.task_id.map(zones)
    d = d[d.zone_id.notna()]
    by_hour = d.groupby(["day", "zone_id", "hour"]).idle_truck_wait_min.sum().reset_index()
    rows = []
    for (day, zone), g in by_hour.groupby(["day", "zone_id"]):
        per = dict(zip(g.hour, g.idle_truck_wait_min, strict=False))
        for h in sorted(per):
            for start in range(h - window_h + 1, h + 1):
                total = sum(per.get(start + k, 0.0) for k in range(window_h))
                rows.append({"day": day, "zone_id": zone, "start_h": start, "minutes": total})
    return pd.DataFrame(rows).drop_duplicates(["day", "zone_id", "start_h"])


def idle_causes(
    cfg: ShiftMateConfig,
    site: Site,
    day: date,
    intervals: pd.DataFrame,
    lookback: pd.DataFrame,
    tasks: pd.DataFrame,
) -> IdleCausesResponse:
    """`intervals`: the day; `lookback`: the previous `similar_days` days; `tasks`: both."""
    c = cfg.fleet.idle_causes
    minutes = {
        reason: _f(intervals[col].sum()) if col in intervals and len(intervals) else 0.0
        for col, reason in IDLE_COLUMNS.items()
    }
    total = sum(minutes.values())
    site_reasons = set(c.site_reasons)
    causes = [
        IdleCause(
            reason=r.value,
            minutes=round(m, 1),
            share=round(m / total, 3) if total else 0.0,
            site_issue=r in site_reasons,
        )
        for r, m in sorted(minutes.items(), key=lambda kv: -kv[1])
        if m > 0
    ]
    lost = [x for x in causes if IdleReason(x.reason) in c.lost_time_reasons]
    lead = lost[0] if lost else None

    by_hour: list[HourMinutes] = []
    if len(intervals):
        hours = _local(intervals.interval_start, site.timezone).dt.hour
        g = intervals.idle_truck_wait_min.fillna(0).groupby(hours).sum()
        by_hour = [HourMinutes(hour=int(h), minutes=round(float(m), 1)) for h, m in g.items()]

    suggestions: list[Suggestion] = []
    zones = dict(zip(tasks.task_id, tasks.zone_id, strict=False)) if len(tasks) else {}
    today = _zone_windows(intervals, zones, site.timezone, c.window_h)
    if len(today):
        best = today.sort_values(["minutes", "start_h"], ascending=[False, True]).iloc[0]
        if best.minutes >= c.min_window_wait_min:
            past = _zone_windows(lookback, zones, site.timezone, c.window_h)
            similar = past[
                (past.zone_id == best.zone_id)
                & (past.start_h == best.start_h)
                & (past.minutes >= c.min_window_wait_min)
            ]
            values = [float(best.minutes), *similar.minutes.astype(float)]
            ranged = len(values) >= c.min_similar_days
            lo, hi = c.range_quantiles
            suggestions.append(
                Suggestion(
                    key="suggest.add_truck",
                    reason=IdleReason.WAITING_FOR_TRUCK.value,
                    minutes=round(minutes[IdleReason.WAITING_FOR_TRUCK], 1),
                    zone_id=str(best.zone_id),
                    window_start=_hhmm(int(best.start_h)),
                    window_end=_hhmm(int(best.start_h) + c.window_h),
                    save_min_low=round(float(np.quantile(values, lo)), 0) if ranged else None,
                    save_min_high=round(float(np.quantile(values, hi)), 0) if ranged else None,
                    basis_days=len(values),
                    lesson_id=None,
                )
            )
    active = intervals.machine_id.nunique() if len(intervals) else 0
    habit = minutes[IdleReason.HABIT]
    if active and habit / active >= c.habit_min_per_machine:
        suggestions.append(
            Suggestion(
                key="suggest.toolbox_idle",
                reason=IdleReason.HABIT.value,
                minutes=round(habit, 1),
                lesson_id=_lesson_for(cfg, IdleReason.HABIT),
            )
        )
    unattended = minutes[IdleReason.UNATTENDED_RUNNING]
    if unattended >= c.unattended_min:
        suggestions.append(
            Suggestion(
                key="suggest.shutdown_briefing",
                reason=IdleReason.UNATTENDED_RUNNING.value,
                minutes=round(unattended, 1),
                lesson_id=_lesson_for(cfg, IdleReason.UNATTENDED_RUNNING),
            )
        )
    suggestions.sort(key=lambda x: -x.minutes)
    return IdleCausesResponse(
        site_id=site.site_id,
        date=day,
        machines=int(active),
        total_idle_min=round(total, 1),
        lead=lead,
        causes=causes,
        truck_wait_by_hour=by_hour,
        suggestion=suggestions[0] if suggestions else None,
        suggestions=suggestions,
    )


def _lesson_for(cfg: ShiftMateConfig, reason: IdleReason) -> str | None:
    return next((x.id for x in cfg.lessons.lessons if reason.value in x.triggers), None)


# --- safety overview ----------------------------------------------------------------------------


def _detail_allowed(cfg: ShiftMateConfig, kind: str, priority: Any, code: Any) -> bool:
    allowed = set(cfg.privacy.supervisor_sees_operator_detail_for)
    return bool({kind, str(priority), str(code)} & allowed)


def _payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}


def safety(
    cfg: ShiftMateConfig,
    site: Site,
    day: date,
    events: pd.DataFrame,
    reports: pd.DataFrame,
    intervals: pd.DataFrame,
    operators: pd.DataFrame,
) -> SafetyResponse:
    names = dict(zip(operators.operator_id, operators.name, strict=False))

    def view(e) -> SafetyEventView:
        shown = _detail_allowed(cfg, e.type, e.priority, e.code) and e.type != "site_issue"
        op = e.operator_id if shown and isinstance(e.operator_id, str) else None
        p = _payload(e.payload)
        detail = {
            k: p[k] for k in ("phase", "minutes", "duration_s", "zone_id", "severity") if k in p
        }
        return SafetyEventView(
            event_id=e.event_id,
            ts=pd.Timestamp(e.ts).to_pydatetime(),
            type=e.type,
            priority=e.priority if isinstance(e.priority, str) else None,
            code=e.code if isinstance(e.code, str) else None,
            machine_id=e.machine_id,
            operator_id=op,
            operator_name=names.get(op) if op else None,
            detail=detail,
        )

    rows = list(events.itertuples()) if len(events) else []
    raised = [e for e in rows if e.type == "alert" and _payload(e.payload).get("phase") == "raised"]
    p1 = [view(e) for e in raised if e.priority == "P1"]
    p2 = [view(e) for e in raised if e.priority == "P2"]
    p2_counts: dict[str, int] = {}
    for v in p2:
        p2_counts[v.code or "?"] = p2_counts.get(v.code or "?", 0) + 1

    report_views = []
    for r in reports.itertuples() if len(reports) else []:
        shown = _detail_allowed(cfg, r.type, None, None)
        report_views.append(
            ReportView(
                report_id=r.report_id,
                ts=pd.Timestamp(r.ts).to_pydatetime(),
                type=r.type,
                severity=r.severity if isinstance(r.severity, str) else None,
                summary_en=r.summary_en if isinstance(r.summary_en, str) else None,
                machine_id=r.machine_id,
                operator_id=r.operator_id if shown and isinstance(r.operator_id, str) else None,
            )
        )

    risk = []
    if len(intervals):
        for machine_id, g in intervals.sort_values("timestamp").groupby("machine_id"):
            bands = g.risk_score_max.map(lambda s: risk_band(cfg, s))
            last = g.iloc[-1]
            risk.append(
                MachineRisk(
                    machine_id=str(machine_id),
                    band=risk_band(cfg, last.risk_score_max),
                    score=None if pd.isna(last.risk_score_max) else int(last.risk_score_max),
                    amber_min=round(_f(g.interval_minutes[bands == "amber"].sum()), 1),
                    red_min=round(_f(g.interval_minutes[bands == "red"].sum()), 1),
                )
            )
    return SafetyResponse(
        site_id=site.site_id,
        date=day,
        p1=p1,
        p2=p2,
        p2_counts=p2_counts,
        incidents=[view(e) for e in rows if e.type == "incident"],
        near_misses=[view(e) for e in rows if e.type == "near_miss"],
        unattended=[
            view(e) for e in rows if e.type == "idle_segment" and e.code == "UNATTENDED_RUNNING"
        ],
        site_issues=[view(e) for e in rows if e.type == "site_issue"],
        reports=report_views,
        risk=risk,
    )


# --- trends -------------------------------------------------------------------------------------


def _per_hour(num: float, engine_min: float) -> float | None:
    return round(num / (engine_min / 60), 2) if engine_min > 0 else None


def trends(
    cfg: ShiftMateConfig,
    site: Site,
    days: int,
    intervals: pd.DataFrame,
    events: pd.DataFrame,
    operators: pd.DataFrame,
) -> TrendsResponse:
    minimum = cfg.privacy.supervisor_aggregates_min_group_size
    daily: list[TrendDay] = []
    if len(intervals):
        iv = intervals.assign(day=_local(intervals["timestamp"], site.timezone).dt.date)
        ev = events.assign(day=_local(events.ts, site.timezone).dt.date) if len(events) else events
        for day, g in iv.groupby("day"):
            ops = int(g.operator_id.nunique())
            if ops < minimum:
                daily.append(TrendDay(day=day, operators=ops, suppressed=True))
                continue
            e = ev[ev.day == day] if len(ev) else ev
            raised = (
                e[
                    (e.type == "alert")
                    & e.payload.map(lambda p: _payload(p).get("phase") == "raised")
                ]
                if len(e)
                else e
            )
            cycles = _f(g.load_cycles.sum())
            daily.append(
                TrendDay(
                    day=day,
                    operators=ops,
                    suppressed=False,
                    idle_min_by_reason={
                        r.value: round(_f(g[col].sum()), 1) for col, r in IDLE_COLUMNS.items()
                    },
                    truck_wait_min=round(_f(g.idle_truck_wait_min.sum()), 1),
                    p1=int(_f(g.p1_alert_count.sum())),
                    p2=int((raised.priority == "P2").sum()) if len(raised) else 0,
                    near_misses=int(_f(g.near_miss_count.sum())),
                    incidents=int(_f(g.incident_count.sum())),
                    fuel_per_load_cycle_l=round(_f(g.fuel_used_l.sum()) / cycles, 2)
                    if cycles
                    else None,
                    seatbelt_unfastened_s_per_h=_per_hour(
                        _f(g.seatbelt_unfastened_working_s.sum()), _f(g.engine_on_min.sum())
                    ),
                )
            )
    groups: list[TrendGroup] = []
    exp = dict(zip(operators.operator_id, operators.experience_years, strict=False))
    for lo, hi in cfg.fleet.trends.experience_bands:
        label = f"{lo:g}–{hi:g} years"
        if not len(intervals):
            groups.append(TrendGroup(group=label, operators=0, suppressed=True))
            continue
        years = intervals.operator_id.map(exp)
        g = intervals[(years >= lo) & (years < hi)]
        ops = int(g.operator_id.nunique())
        if ops < minimum:
            groups.append(TrendGroup(group=label, operators=ops, suppressed=True))
            continue
        engine = _f(g.engine_on_min.sum())
        cycles = _f(g.load_cycles.sum())
        groups.append(
            TrendGroup(
                group=label,
                operators=ops,
                suppressed=False,
                habit_idle_min_per_h=_per_hour(_f(g.idle_habit_min.sum()), engine),
                seatbelt_unfastened_s_per_h=_per_hour(
                    _f(g.seatbelt_unfastened_working_s.sum()), engine
                ),
                fuel_per_load_cycle_l=round(_f(g.fuel_used_l.sum()) / cycles, 2)
                if cycles
                else None,
                p1_per_100h=round(100 * _f(g.p1_alert_count.sum()) / (engine / 60), 2)
                if engine
                else None,
            )
        )
    return TrendsResponse(
        site_id=site.site_id,
        days=days,
        min_group_size=minimum,
        daily=daily,
        by_experience=groups,
    )


def day_window(day: date, days: int) -> tuple[date, date]:
    """The `days` local days ending with `day`: (first, last)."""
    return day - timedelta(days=days - 1), day


def as_date(value: datetime | None, tz: str) -> date | None:
    if value is None:
        return None
    return pd.Timestamp(value).tz_convert(tz).date()
