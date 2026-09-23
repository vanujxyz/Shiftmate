"""Write sections of `docs/EVAL.md` (TRD §12).

Each evaluation owns one section between `<!-- BEGIN name -->` and `<!-- END name -->` markers,
so `shiftmate eval idle` can refresh its section without touching the others. Sections are kept
in a fixed order. Numbers are always computed, never typed in (golden rule 11).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from shiftmate.settings import REPO_ROOT

EVAL_PATH = REPO_ROOT / "docs" / "EVAL.md"
ORDER = ["data", "idle", "anomaly", "estimation", "assistant", "camera", "scale"]
HEADER = """# ShiftMate — Evaluation results

Measured results, reported as they are, including targets that were not met (golden rule 11).
All numbers come from `shiftmate eval …` on simulated data (see `data/history/SUMMARY.md`);
nothing here is typed in by hand. Test data are history days 36–42, which no model saw during
training, tuning or early stopping.
"""


def write_section(name: str, markdown: str, path: Path = EVAL_PATH) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else HEADER
    block = f"<!-- BEGIN {name} -->\n{markdown.strip()}\n<!-- END {name} -->"
    pattern = re.compile(rf"<!-- BEGIN {name} -->.*?<!-- END {name} -->", re.DOTALL)
    if pattern.search(text):
        text = pattern.sub(lambda _: block, text)
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    # keep sections in the fixed order
    sections = {
        m.group(1): m.group(0)
        for m in re.finditer(r"<!-- BEGIN (\w+) -->.*?<!-- END \1 -->", text, re.DOTALL)
    }
    head = re.split(r"<!-- BEGIN \w+ -->", text, maxsplit=1)[0].rstrip()
    ordered = [sections[k] for k in ORDER if k in sections]
    ordered += [v for k, v in sections.items() if k not in ORDER]
    path.write_text(head + "\n\n" + "\n\n".join(ordered) + "\n", encoding="utf-8")


def md_table(df: pd.DataFrame, floatfmt: str = "{:.2f}") -> str:
    """A small Markdown table (no extra dependency)."""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append(floatfmt.format(v) if pd.notna(v) else "–")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def pct(x: float) -> str:
    return f"{100 * x:.1f} %" if pd.notna(x) else "–"


def verdict(value: float, target: float, higher_is_better: bool = True) -> str:
    ok = value >= target if higher_is_better else value <= target
    return "met" if ok else "**not met**"
