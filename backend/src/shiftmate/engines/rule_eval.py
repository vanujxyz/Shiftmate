"""Safe evaluator for the rule expressions in `config/safety_rules.yaml` (TRD §4.4).

A rule such as `not seatbelt_fastened and (travel_speed_kmh > 0.5 or hydraulic_active)` is parsed
once with Python's `ast` module into a syntax tree, checked against a whitelist, and then
evaluated by walking that tree ourselves. Python's `eval`/`exec` are never used.

Allowed: names from an approved list, numbers, booleans, strings, `and`/`or`/`not`, comparisons
(`< <= > >= == !=`, chained), unary minus and `+ - * /`. Everything else — attribute access
(`a.b`), function calls, subscripts, lambdas, comprehensions, imports — is rejected when the rule
is compiled, so a bad rule fails at start-up rather than at run time.

Missing data: if any name used by a rule has the value `None` (the sensor is absent or has no
reading), the rule evaluates to False. A rule cannot fire on data it does not have.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any


class RuleError(ValueError):
    """The expression is not allowed, or refers to an unknown name."""


_COMPARE: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}
_BINARY: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.USub,
    ast.Compare,
    ast.BinOp,
    ast.Name,
    ast.Load,
    ast.Constant,
    *_COMPARE,
    *_BINARY,
)


class _MissingValueError(Exception):
    """Internal: a referenced value is None, so the whole rule is False."""


@dataclass(frozen=True)
class CompiledRule:
    source: str
    names: frozenset[str]
    _tree: ast.Expression

    def evaluate(self, values: Mapping[str, Any]) -> bool:
        try:
            return bool(_eval(self._tree.body, values))
        except _MissingValueError:
            return False
        except ZeroDivisionError:
            return False


def compile_rule(source: str, allowed_names: Iterable[str]) -> CompiledRule:
    """Parse and check an expression. Raises RuleError if anything is not allowed."""
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise RuleError(f"invalid rule syntax: {source!r}") from exc
    allowed = set(allowed_names)
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise RuleError(f"'{type(node).__name__}' is not allowed in rules: {source!r}")
        if isinstance(node, ast.Name):
            if node.id not in allowed:
                raise RuleError(f"unknown name '{node.id}' in rule: {source!r}")
            names.add(node.id)
        if isinstance(node, ast.Constant) and not isinstance(node.value, int | float | bool | str):
            raise RuleError(f"constant {node.value!r} is not allowed in rules: {source!r}")
    return CompiledRule(source=source, names=frozenset(names), _tree=tree)


def _eval(node: ast.AST, values: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        value = values.get(node.id)
        if value is None:
            raise _MissingValueError(node.id)
        return value
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval(v, values) for v in node.values)
        return any(_eval(v, values) for v in node.values)
    if isinstance(node, ast.UnaryOp):
        operand = _eval(node.operand, values)
        return (not operand) if isinstance(node.op, ast.Not) else -operand
    if isinstance(node, ast.BinOp):
        return _BINARY[type(node.op)](_eval(node.left, values), _eval(node.right, values))
    if isinstance(node, ast.Compare):
        left = _eval(node.left, values)
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            right = _eval(comparator, values)
            if not _COMPARE[type(op)](left, right):
                return False
            left = right
        return True
    raise RuleError(f"unexpected node {type(node).__name__}")  # unreachable after compile
