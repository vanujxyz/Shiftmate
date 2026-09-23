"""Safety engine: evaluates `safety_rules.yaml` every tick (TRD §4.4, §6.2).

For each rule:
1. **Tier check.** If the machine lacks a signal in `requires_signals` (e.g. no seat sensor on a
   basic machine), the rule is disabled and listed as such in the machine's capabilities. A
   camera can add `proximity_m` to any tier at run time.
2. **Condition.** The rule's expression is evaluated by `rule_eval` over the tick signals, the
   Risk engine's effective thresholds, profile values and runtime values.
3. **Sustain.** The condition must hold for `sustain_s` before the rule fires. A tick holds for
   its period `dt`, so at 1 s ticks a 2 s sustain needs two true ticks, at 30 s ticks one.
4. **Raise.** When a rule becomes active it is *raised* (a new alert candidate), unless the same
   rule was raised less than `cooldown_s` ago (default from the alert policy). Level rules raise
   once per activation; edge rules (risk band) only when the condition switches on.
5. **Clear.** When an active rule's condition stops, it is *cleared*.
The Alert policy (alerts.py) decides what the operator actually sees.
Pure: no clock reads, no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shiftmate.engines.rule_eval import CompiledRule, compile_rule
from shiftmate.schema.config import SafetyRule, SafetyRulesConfig
from shiftmate.schema.enums import Priority

# Every name a rule may use (validated when rules are compiled).
TICK_NAMES = (
    "engine_on",
    "hydraulic_active",
    "travel_speed_kmh",
    "seatbelt_fastened",
    "seat_occupied",
    "engine_rpm",
    "coolant_temp_c",
    "proximity_m",
    "truck_in_loading_zone",
    "heat_index_c",
    "precipitation_mm_h",
    "visibility_m",
    "is_night",
)
THRESHOLD_NAMES = ("caution_m", "danger_m", "critical_m", "fatigue_warn_min", "fatigue_limit_min")
PROFILE_NAMES = ("speed_near_person_kmh",)
RUNTIME_NAMES = (
    "continuous_operation_min",
    "minutes_since_break",
    "risk_band_rank",
    "proximity_age_s",
)
CONTEXT_NAMES = frozenset(TICK_NAMES + THRESHOLD_NAMES + PROFILE_NAMES + RUNTIME_NAMES)


@dataclass(frozen=True)
class RaisedAlert:
    rule_id: str
    priority: Priority
    message_key: str
    category: str
    raised_at: datetime


@dataclass
class SafetyOutput:
    raised: list[RaisedAlert] = field(default_factory=list)
    cleared: list[str] = field(default_factory=list)
    active: set[str] = field(default_factory=set)


@dataclass
class _RuleState:
    true_since: datetime | None = None
    active: bool = False
    last_raised: datetime | None = None


def compile_rules(config: SafetyRulesConfig) -> dict[str, CompiledRule]:
    return {rule.id: compile_rule(rule.when, CONTEXT_NAMES) for rule in config.rules}


class SafetyEngine:
    def __init__(
        self,
        config: SafetyRulesConfig,
        available_signals: Iterable[str],
        default_cooldown_s: float,
    ) -> None:
        self.rules: list[SafetyRule] = list(config.rules)
        self.compiled = compile_rules(config)
        self.default_cooldown_s = default_cooldown_s
        self.base_signals = set(available_signals)
        self.state = {rule.id: _RuleState() for rule in self.rules}

    def enabled(self, rule: SafetyRule, extra_signals: Iterable[str] = ()) -> bool:
        signals = self.base_signals | set(extra_signals)
        return all(s in signals for s in rule.requires_signals)

    def capabilities(self, extra_signals: Iterable[str] = ()) -> dict[str, bool]:
        """Rule id → enabled on this machine (shown in `/machines/{id}`)."""
        return {rule.id: self.enabled(rule, extra_signals) for rule in self.rules}

    def update(
        self,
        ts: datetime,
        dt: float,
        context: Mapping[str, Any],
        extra_signals: Iterable[str] = (),
    ) -> SafetyOutput:
        out = SafetyOutput()
        extra = set(extra_signals)
        for rule in self.rules:
            st = self.state[rule.id]
            condition = self.enabled(rule, extra) and self.compiled[rule.id].evaluate(context)
            if not condition:
                if st.active:
                    out.cleared.append(rule.id)
                st.true_since = None
                st.active = False
                continue
            if st.true_since is None:
                st.true_since = ts
            held = (ts - st.true_since).total_seconds() + dt
            if held + 1e-9 < rule.sustain_s:
                continue
            if not st.active:
                st.active = True
                cooldown = (
                    rule.cooldown_s if rule.cooldown_s is not None else self.default_cooldown_s
                )
                if rule.trigger == "edge":
                    cooldown = 0.0
                cooling = (
                    st.last_raised is not None and (ts - st.last_raised).total_seconds() < cooldown
                )
                if not cooling:
                    st.last_raised = ts
                    out.raised.append(
                        RaisedAlert(rule.id, rule.priority, rule.message_key, rule.category, ts)
                    )
            out.active.add(rule.id)
        return out
