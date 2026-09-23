"""The knowledge base: team-written markdown in `knowledge/` (TRD §10.1, §10.2).

Each English file `<id>.md` starts with front matter `{id, title: {en, hi, ta}, machine_types,
section}`; key safety files also have `<id>.hi.md` / `<id>.ta.md` with the same `##` headings in
the same order. Chunks are cut at `##` headings; a section longer than `max_words` is split into
windows of `max_words` with `overlap_words` of overlap. Chunk `<id>#<n>` is the same passage in
every language, so a Tamil question can cite the English chunk and a Tamil answer can show the
Tamil text. Pure apart from reading the files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from shiftmate.schema.config import ChunkConfig

LANGS = ("en", "hi", "ta")
_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass
class Chunk:
    chunk_id: str  # "<file_id>#<n>", n from 1
    file_id: str
    title: dict[str, str]
    section: str
    machine_types: list[str]
    heading: dict[str, str] = field(default_factory=dict)  # per language
    text: dict[str, str] = field(default_factory=dict)  # per language

    def for_language(self, language: str) -> tuple[str, str, bool]:
        """(heading, text, translated) in `language`, else English."""
        if language in self.text:
            return self.heading.get(language, ""), self.text[language], language != "en"
        return self.heading.get("en", ""), self.text["en"], False

    def to_json(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "file_id": self.file_id,
            "title": self.title,
            "section": self.section,
            "machine_types": self.machine_types,
            "heading": self.heading,
            "text": self.text,
        }

    @classmethod
    def from_json(cls, d: dict[str, object]) -> Chunk:
        return cls(**d)  # type: ignore[arg-type]


def split_front_matter(raw: str) -> tuple[dict[str, object], str]:
    m = _FRONT.match(raw.replace("\r\n", "\n"))
    if not m:
        raise ValueError("missing front matter")
    meta = yaml.safe_load(m.group(1)) or {}
    return meta, m.group(2)


def sections(body: str) -> list[tuple[str, str]]:
    """(`##` heading, text) pairs in order; the `#` title line and text before the first `##` are
    not a section."""
    out: list[tuple[str, str]] = []
    heading: str | None = None
    lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if heading is not None:
                out.append((heading, " ".join(x.strip() for x in lines if x.strip())))
            heading, lines = line[3:].strip(), []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        out.append((heading, " ".join(x.strip() for x in lines if x.strip())))
    return out


def windows(text: str, max_words: int, overlap: int) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]
    step = max(1, max_words - overlap)
    return [" ".join(words[i : i + max_words]) for i in range(0, len(words) - overlap, step)]


def load_knowledge(directory: Path, cfg: ChunkConfig) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(directory.glob("*.md")):
        if path.name.count(".") > 1 or path.name.lower() == "readme.md":
            continue  # translations are read with their English file
        meta, body = split_front_matter(path.read_text(encoding="utf-8"))
        file_id = str(meta["id"])
        if path.stem != file_id:
            raise ValueError(f"{path.name}: id {file_id!r} must match the file name")
        per_lang: dict[str, list[tuple[str, str]]] = {"en": sections(body)}
        for lang in ("hi", "ta"):
            tr = path.with_name(f"{file_id}.{lang}.md")
            if tr.exists():
                tmeta, tbody = split_front_matter(tr.read_text(encoding="utf-8"))
                if tmeta.get("id") != file_id:
                    raise ValueError(f"{tr.name}: id must be {file_id!r}")
                per_lang[lang] = sections(tbody)
                if len(per_lang[lang]) != len(per_lang["en"]):
                    raise ValueError(f"{tr.name}: needs the same {len(per_lang['en'])} sections")
        n = 0
        for i, (heading, text) in enumerate(per_lang["en"]):
            parts = windows(text, cfg.max_words, cfg.overlap_words)
            for j, part in enumerate(parts):
                n += 1
                c = Chunk(
                    chunk_id=f"{file_id}#{n}",
                    file_id=file_id,
                    title=dict(meta["title"]),  # type: ignore[arg-type]
                    section=str(meta.get("section", "")),
                    machine_types=list(meta.get("machine_types", ["all"])),  # type: ignore[arg-type]
                    heading={"en": heading},
                    text={"en": part},
                )
                # a translated section is attached whole to the first window of its section
                for lang in ("hi", "ta"):
                    if lang in per_lang and j == 0:
                        c.heading[lang], c.text[lang] = per_lang[lang][i]
                chunks.append(c)
    return chunks
