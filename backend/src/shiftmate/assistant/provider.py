"""The edge's assistant, built on first use (loading the embedding model takes a few seconds, so the
gateway starts at once and the first question pays for it). Without an index it still answers,
with "the manual is not loaded on this machine yet"; without a key it answers offline."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from shiftmate.assistant.index import KnowledgeIndex, SentenceEmbedder
from shiftmate.assistant.llm import LlmClient, make_client
from shiftmate.assistant.service import Assistant
from shiftmate.config_loader import ShiftMateConfig
from shiftmate.settings import Settings

log = logging.getLogger("shiftmate.assistant")


def index_dir(cfg: ShiftMateConfig, models_dir: Path) -> Path:
    return models_dir / cfg.assistant.index_dir


def llm_from_settings(cfg: ShiftMateConfig, settings: Settings) -> LlmClient | None:
    return make_client(
        settings.llm_provider,
        settings.gemini_api_key.get_secret_value(),
        settings.llm_model,
        cfg.assistant.llm,
    )


class AssistantProvider:
    def __init__(self, cfg: ShiftMateConfig, models_dir: Path, llm: LlmClient | None) -> None:
        self.cfg = cfg
        self.models_dir = models_dir
        self.llm = llm
        self._assistant: Assistant | None = None
        self._lock = threading.Lock()

    def get(self) -> Assistant:
        with self._lock:
            if self._assistant is None:
                self._assistant = self._build()
            return self._assistant

    def _build(self) -> Assistant:
        a = self.cfg.assistant
        index: KnowledgeIndex | None = None
        folder = index_dir(self.cfg, self.models_dir)
        if (folder / "chunks.json").exists():
            try:
                embedder = SentenceEmbedder(self.models_dir / a.embedding_dir)
                index = KnowledgeIndex.load(folder, embedder, a.retrieval)
            except Exception as exc:  # a broken index must not take the gateway down
                log.warning("assistant index not loaded: %s", exc)
        return Assistant(index, self.llm, a, self.cfg.intents, self.cfg.report_keywords)
