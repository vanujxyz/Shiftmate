"""Golden rule 5: engines, the edge runtime, the fleet service, the assistant and the UI never read
ground-truth labels, operator personalities or the simulator's truth files.

Python code is checked by parsing it (so docstrings and comments that *explain* the rule are
fine, but any attribute, name or string literal used in code is caught). Frontend TypeScript is
checked line by line, skipping comments.
"""

import ast
import re
from pathlib import Path

from shiftmate.settings import REPO_ROOT

SRC = REPO_ROOT / "backend" / "src" / "shiftmate"
ALLOWED_PY = {"sim", "eval"}  # the only packages allowed to touch ground truth
ALSO_ALLOWED = {"config_loader.py"}  # loads simulator.yaml for the simulator's use
BANNED_WORDS = re.compile(r"label_|personalit|ticks_truth|truth/|idle_reason_truth", re.IGNORECASE)
BANNED_ATTRS = {"simulator", "personality", "personalities"}


def _python_files() -> list[Path]:
    files = []
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC)
        if rel.parts[0] in ALLOWED_PY or rel.name in ALSO_ALLOWED:
            continue
        files.append(path)
    return files


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = _docstring_nodes(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRS:
            found.append(f"{path.name}:{node.lineno} attribute .{node.attr}")
        elif isinstance(node, ast.Name) and BANNED_WORDS.search(node.id):
            found.append(f"{path.name}:{node.lineno} name {node.id}")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and BANNED_WORDS.search(node.value)
        ):
            found.append(f"{path.name}:{node.lineno} string {node.value!r}")
        elif (
            path.parent.name == "engines"  # engines must not depend on the simulator at all
            and isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith(("shiftmate.sim", "shiftmate.eval"))
        ):
            found.append(f"{path.name}:{node.lineno} imports {node.module}")
    return found


def test_python_outside_sim_and_eval_never_reads_ground_truth() -> None:
    files = _python_files()
    assert any(p.parent.name == "engines" for p in files)  # the scan really covers the engines
    problems = [v for path in files for v in _violations(path)]
    assert problems == []


def test_frontend_never_reads_ground_truth() -> None:
    problems = []
    for folder in ("apps", "packages"):
        for path in (REPO_ROOT / "frontend" / folder).rglob("*.ts*"):
            if "node_modules" in path.parts or path.name == "generated.ts":
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("//")[0]
                if BANNED_WORDS.search(code):
                    problems.append(f"{path.name}:{n}")
    assert problems == []


def test_guard_catches_a_violation(tmp_path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        '"""label_idle_reason is fine in a docstring."""\n'
        "def f(row, cfg):\n"
        "    x = row['label_anomaly']\n"
        "    return cfg.simulator, x\n",
        encoding="utf-8",
    )
    found = _violations(bad)
    assert len(found) == 2
