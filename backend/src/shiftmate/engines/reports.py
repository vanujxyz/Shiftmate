"""Quick Report: offline parser and auto-fill (TRD §6.10; PRD F-REP-01..04).

Offline parsing (no network, no LLM): the spoken transcript is matched against keyword lists in
English, Hindi and Tamil (`assistant/keywords/reports.yaml`):
- type: near miss words first, then incident words, then equipment words (so "I almost hit a
  worker" is a near miss); nothing matched → near miss;
- severity: high if an injury/fire word appears, medium if a person, damage or near-miss word
  appears, else low;
- people involved / injury: any matching word.
The summary is the transcript itself (offline mode cannot translate). The operator always
confirms or edits the draft before it is saved (F-REP-03). The online LLM path (milestone 14)
fills the same `ReportDraft`, and falls back to this parser on any failure.

Auto-fill: time, machine, operator, site, zone (from the GPS position), task, a weather
snapshot and the risk score come from the machine's current state, never from the operator.
Pure: no I/O; keywords and state are passed in.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from shiftmate.schema.config import Layout, ReportKeywords
from shiftmate.schema.enums import Language, ReportType, Severity
from shiftmate.schema.events import ReportDraft
from shiftmate.util.geo import zone_at

TYPE_ORDER = (ReportType.NEAR_MISS, ReportType.INCIDENT, ReportType.EQUIPMENT_PROBLEM)


def _any(text: str, words: list[str]) -> bool:
    return any(w.lower() in text for w in words)


def _words(table: Mapping[Language, list[str]]) -> list[str]:
    """Match words from every language: operators mix languages in one sentence."""
    return [w for words in table.values() for w in words]


def parse_offline(transcript: str, language: Language, kw: ReportKeywords) -> ReportDraft:
    text = f" {transcript.lower().strip()} "
    report_type = next(
        (t for t in TYPE_ORDER if _any(text, _words(kw.type[t]))), ReportType.NEAR_MISS
    )
    if _any(text, _words(kw.severity["high"])):
        severity = Severity.HIGH
    elif _any(text, _words(kw.severity["medium"])) or report_type == ReportType.NEAR_MISS:
        severity = Severity.MEDIUM
    else:
        severity = Severity.LOW
    clean = transcript.strip()
    return ReportDraft(
        type=report_type,
        severity=severity,
        summary_en=clean,
        summary_local=clean,
        people_involved=_any(text, _words(kw.people)),
        injury=_any(text, _words(kw.injury)),
        parser="offline",
    )


class ReportContext(BaseModel):
    """Everything filled in automatically (F-REP-02)."""

    ts: datetime
    machine_id: str
    operator_id: str | None
    site_id: str
    zone_id: str | None
    task_id: str | None
    weather: dict[str, Any]
    risk_score: int | None
    language: Language


def auto_fill(
    *,
    ts: datetime,
    machine_id: str,
    operator_id: str | None,
    site_id: str,
    layout: Layout,
    x_m: float,
    y_m: float,
    task_id: str | None,
    weather: Mapping[str, Any],
    risk_score: int | None,
    language: Language,
) -> ReportContext:
    zone = zone_at(layout, x_m, y_m)
    return ReportContext(
        ts=ts,
        machine_id=machine_id,
        operator_id=operator_id,
        site_id=site_id,
        zone_id=zone.id if zone else None,
        task_id=task_id,
        weather=dict(weather),
        risk_score=risk_score,
        language=language,
    )
