"""Merge new UI strings into the en/hi/ta locale files.

Usage: python scripts/i18n_merge.py scripts/i18n/<file>.yaml

The YAML maps dotted keys to their three languages:
    reason.ground_wet_slower: {en: "Wet ground adds time", hi: "…", ta: "…"}
A key set to `null` is removed from all three files. Existing keys are overwritten, so the YAML
files in scripts/i18n/ are the reviewable source of each batch of strings.
"""

import json
import sys
from pathlib import Path

import yaml

LOCALES = Path(__file__).resolve().parents[1] / "frontend" / "packages" / "i18n" / "src" / "locales"


def set_path(tree: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    node = tree
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    if value is None:
        node.pop(parts[-1], None)
    else:
        node[parts[-1]] = value


def main(path: str) -> None:
    additions = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    for lang in ("en", "hi", "ta"):
        file = LOCALES / f"{lang}.json"
        data = json.loads(file.read_text(encoding="utf-8"))
        for key, texts in additions.items():
            set_path(data, key, None if texts is None else texts[lang])
        file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"merged {len(additions)} keys into {LOCALES}")


if __name__ == "__main__":
    main(sys.argv[1])
