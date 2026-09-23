"""Mark a milestone done in docs/PROGRESS.md and set the next step (used at milestone ends).

Usage: python scripts/progress_mark.py <done milestone number> "<next step text>"
"""

import sys
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "docs" / "PROGRESS.md"
done = int(sys.argv[1])
next_step = sys.argv[2]
text = path.read_text(encoding="utf-8")
start = text.index(f"### Milestone {done} ")
end = text.index(f"### Milestone {done + 1} ") if f"### Milestone {done + 1} " in text else text.index("## C.")
block = text[start:end].replace("- [ ]", "- [x]").replace("Status: not started", "Status: done")
block = block.replace("Status: in progress", "Status: done")
text = text[:start] + block + text[end:]
lines = text.split("\n")
for i, line in enumerate(lines):
    if line.startswith("**Next step:**"):
        lines[i] = f"**Next step:** {next_step}"
        break
path.write_text("\n".join(lines), encoding="utf-8")
print(f"milestone {done} marked done")
