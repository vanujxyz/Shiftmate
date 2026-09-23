"""Hybrid retrieval over the knowledge base (TRD §10.2).

Every chunk is indexed once per language it is written in (English always; Hindi and Tamil for
the key safety files). A query is scored against every indexed text by
`bm25_weight · lexical + dense_weight · max(0, cosine)` with multilingual sentence embeddings,
where `lexical` is BM25 divided by the best BM25 for this query, times the share of the query's
IDF weight that the text contains (words the knowledge base never uses get the highest IDF). The
second factor keeps a query that shares one word with a chunk ("the price of a new bucket") from
scoring like a real match just because it is the best of a bad set (D-085). A chunk's score is its
best language's score, and the top `top_k` chunks that apply to the machine type are returned.
Indic scripts are tokenised on whitespace and punctuation (vowel signs stay inside their word).
The index is built by `shiftmate assistant index` into `models/assistant/` and loaded by the
edge, so it works with no network.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import numpy as np
from rank_bm25 import BM25Okapi

from shiftmate.assistant.knowledge import Chunk
from shiftmate.schema.config import RetrievalConfig

_SPLIT = re.compile(r"[\s\.,;:!?\"'()\[\]{}।॥…–—\-/·*#`]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _SPLIT.split(text.lower()) if t]


class Embedder(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray:
        """One L2-normalised row per text."""
        ...


class SentenceEmbedder:
    """The multilingual MiniLM, loaded from a local folder (no network at run time)."""

    def __init__(self, path: Path) -> None:
        from sentence_transformers import SentenceTransformer

        if not path.exists():
            raise FileNotFoundError(f"embedding model not found at {path}")
        self.model = SentenceTransformer(str(path), device="cpu")

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False),
            dtype=np.float32,
        )


def doc_text(c: Chunk, lang: str) -> str:
    return f"{c.title.get(lang, c.title['en'])}. {c.heading.get(lang, '')}. {c.text[lang]}"


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    bm25: float
    dense: float
    language: str  # the language of the best-matching text


class KnowledgeIndex:
    def __init__(
        self,
        chunks: list[Chunk],
        docs: list[tuple[int, str]],
        vectors: np.ndarray,
        embedder: Embedder,
        cfg: RetrievalConfig,
    ) -> None:
        self.chunks = chunks
        self.docs = docs  # (chunk index, language)
        self.vectors = vectors
        self.embedder = embedder
        self.cfg = cfg
        tokens = [tokenize(doc_text(chunks[i], lang)) for i, lang in docs]
        self.bm25 = BM25Okapi(tokens)
        self.doc_terms = [set(t) for t in tokens]
        self.max_idf = max(self.bm25.idf.values()) if self.bm25.idf else 1.0
        self.by_id = {c.chunk_id: c for c in chunks}

    def coverage(self, query_terms: list[str]) -> np.ndarray:
        """Per text: the share of the query's IDF weight whose terms the text contains."""
        weights = {t: max(self.bm25.idf.get(t, self.max_idf), 0.0) for t in set(query_terms)}
        total = sum(weights.values())
        if total <= 0:
            return np.zeros(len(self.docs))
        return np.array(
            [sum(w for t, w in weights.items() if t in terms) / total for terms in self.doc_terms]
        )

    # --- build and load ---------------------------------------------------------------------
    @classmethod
    def build(cls, chunks: list[Chunk], embedder: Embedder, cfg: RetrievalConfig) -> KnowledgeIndex:
        docs = [(i, lang) for i, c in enumerate(chunks) for lang in c.text]
        vectors = embedder.encode([doc_text(chunks[i], lang) for i, lang in docs])
        return cls(chunks, docs, vectors, embedder, cfg)

    def save(self, directory: Path, model_name: str) -> dict[str, object]:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "chunks.json").write_text(
            json.dumps([c.to_json() for c in self.chunks], ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        np.save(directory / "vectors.npy", self.vectors)
        meta = {
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "embedding_model": model_name,
            "chunks": len(self.chunks),
            "texts": len(self.docs),
            "docs": self.docs,
        }
        (directory / "index.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return {k: v for k, v in meta.items() if k != "docs"}

    @classmethod
    def load(cls, directory: Path, embedder: Embedder, cfg: RetrievalConfig) -> KnowledgeIndex:
        chunks = [
            Chunk.from_json(d)
            for d in json.loads((directory / "chunks.json").read_text(encoding="utf-8"))
        ]
        meta = json.loads((directory / "index.json").read_text(encoding="utf-8"))
        docs = [(int(i), str(lang)) for i, lang in meta["docs"]]
        vectors = np.load(directory / "vectors.npy")
        return cls(chunks, docs, vectors, embedder, cfg)

    # --- search -----------------------------------------------------------------------------
    def search(
        self, query: str, machine_type: str | None = None, k: int | None = None
    ) -> list[Hit]:
        k = k or self.cfg.top_k
        terms = tokenize(query)
        raw = np.asarray(self.bm25.get_scores(terms), dtype=np.float64)
        top = float(raw.max()) if raw.size else 0.0
        bm = (raw / top if top > 0 else np.zeros_like(raw)) * self.coverage(terms)
        q = self.embedder.encode([query])[0]
        dense = np.clip(self.vectors @ q, 0.0, 1.0)
        combined = self.cfg.bm25_weight * bm + self.cfg.dense_weight * dense
        best: dict[int, Hit] = {}
        for d, (ci, lang) in enumerate(self.docs):
            c = self.chunks[ci]
            if (
                machine_type
                and "all" not in c.machine_types
                and machine_type not in c.machine_types
            ):
                continue
            h = Hit(c, float(combined[d]), float(bm[d]), float(dense[d]), lang)
            if ci not in best or h.score > best[ci].score:
                best[ci] = h
        return sorted(best.values(), key=lambda h: -h.score)[:k]
