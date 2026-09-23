"""Voice command matcher (TRD §10.5; PRD F-ASK-04).

The utterance is lower-cased and stripped of punctuation. Every intent has phrases in English,
Hindi and Tamil (`assistant/keywords/intents.yaml`); phrases from all languages are tried,
because operators mix languages in one sentence. The longest matching phrase wins, so "report a
problem" beats "problem". No match means the utterance is a question for the assistant.
Pure: no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from shiftmate.schema.config import IntentsConfig

_PUNCT = re.compile(r"[^\w\s'-]", re.UNICODE)


@dataclass(frozen=True)
class IntentMatch:
    intent: str  # an intent name, or "question"
    matched: str | None


def normalise(text: str) -> str:
    return " ".join(_PUNCT.sub(" ", text.lower()).split())


def match_intent(utterance: str, config: IntentsConfig) -> IntentMatch:
    text = f" {normalise(utterance)} "
    best: tuple[int, str, str] | None = None
    for intent, per_language in config.intents.items():
        for phrases in per_language.values():
            for phrase in phrases:
                p = normalise(phrase)
                # Latin phrases match whole words; Hindi/Tamil phrases match anywhere in the text.
                found = bool(p) and (f" {p} " in text or (not p.isascii() and p in text))
                if found and (best is None or len(p) > best[0]):
                    best = (len(p), intent, phrase)
    if best is None:
        return IntentMatch("question", None)
    return IntentMatch(best[1], best[2])
