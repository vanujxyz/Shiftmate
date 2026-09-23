"""Rule evaluator: correct results, missing data is False, and nothing unsafe gets through."""

import pytest

from shiftmate.config_loader import get_config
from shiftmate.engines.rule_eval import RuleError, compile_rule
from shiftmate.engines.safety import CONTEXT_NAMES

NAMES = {"a", "b", "seatbelt_fastened", "travel_speed_kmh", "hydraulic_active", "x"}
SEATBELT = "not seatbelt_fastened and (travel_speed_kmh > 0.5 or hydraulic_active)"


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({"seatbelt_fastened": False, "travel_speed_kmh": 2.0, "hydraulic_active": False}, True),
        ({"seatbelt_fastened": False, "travel_speed_kmh": 0.0, "hydraulic_active": True}, True),
        ({"seatbelt_fastened": False, "travel_speed_kmh": 0.0, "hydraulic_active": False}, False),
        ({"seatbelt_fastened": True, "travel_speed_kmh": 5.0, "hydraulic_active": True}, False),
    ],
)
def test_seatbelt_rule(values, expected) -> None:
    assert compile_rule(SEATBELT, NAMES).evaluate(values) is expected


def test_comparisons_arithmetic_and_constants() -> None:
    assert compile_rule("1 < a <= 3", NAMES).evaluate({"a": 3})
    assert not compile_rule("1 < a <= 3", NAMES).evaluate({"a": 4})
    assert compile_rule("a * 2 - b / 4 == 5", NAMES).evaluate({"a": 3, "b": 4})
    assert compile_rule("-a < 0", NAMES).evaluate({"a": 1})
    assert compile_rule("x == 'wet'", NAMES).evaluate({"x": "wet"})


def test_missing_value_makes_rule_false() -> None:
    rule = compile_rule("a <= 6", NAMES)
    assert rule.evaluate({"a": None}) is False
    assert rule.evaluate({}) is False
    assert compile_rule("not a", NAMES).evaluate({"a": None}) is False


def test_division_by_zero_is_false() -> None:
    assert compile_rule("a / b > 1", NAMES).evaluate({"a": 1, "b": 0}) is False


@pytest.mark.parametrize(
    "source",
    [
        "a.real",  # attribute access
        "a.__class__",
        "abs(a)",  # function call
        "__import__('os').system('echo hi')",
        "a[0]",  # subscript
        "(lambda: 1)()",
        "[x for x in a]",
        "{'k': 1}",
        "open('secret.txt')",
        "(y := 3)",
        "f'{a}'",
        "a if b else x",
        "a ** 2",
        "a in b",
        "import os",
        "unknown_name > 1",
        "a >",
    ],
)
def test_rejects_unsafe_or_invalid(source) -> None:
    with pytest.raises(RuleError):
        compile_rule(source, NAMES)


def test_every_configured_rule_compiles() -> None:
    for rule in get_config().safety_rules.rules:
        compiled = compile_rule(rule.when, CONTEXT_NAMES)
        assert compiled.names <= CONTEXT_NAMES
