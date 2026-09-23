"""Ask Cat: answers from the knowledge base only, online or offline (TRD §10.3–10.5; F-ASK-01…06).

Online (a key is configured and the provider answers): the top chunks go to the LLM with the
system prompt in `prompts/answer_system.md`. The reply is checked: it must be the JSON asked
for, every citation must be one of the retrieved chunks, and an "answerable" reply must cite at
least one. Anything else becomes a refusal. Offline (no key, 429, timeout, server error), the
best chunk is returned as written, in the operator's language when a translation exists, but only
if it scores at least `offline_min_score`; otherwise the assistant says it does not know.
Requests to defeat a safety system are always refused, whatever the sources or the model say.

The same provider layer classifies voice commands that the keyword rules miss, and turns a spoken
report into a structured draft (F-REP-01), each with the offline path as its fallback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shiftmate.assistant.index import Hit, KnowledgeIndex
from shiftmate.assistant.llm import LlmBadOutputError, LlmClient, LlmUnavailableError
from shiftmate.engines.intents import match_intent, normalise
from shiftmate.engines.reports import parse_offline
from shiftmate.schema.api import AskResponse, Citation, IntentResponse
from shiftmate.schema.config import INTENT_NAMES, AssistantConfig, IntentsConfig, ReportKeywords
from shiftmate.schema.enums import Language, ReportType, Severity
from shiftmate.schema.events import ReportDraft

PROMPTS = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def citation(hit_chunk: Any, language: str) -> Citation:
    c = hit_chunk
    return Citation(
        chunk_id=c.chunk_id,
        title=c.title.get(language, c.title["en"]),
        section=c.heading.get(language, c.heading["en"]),
    )


class Assistant:
    def __init__(
        self,
        index: KnowledgeIndex | None,
        llm: LlmClient | None,
        cfg: AssistantConfig,
        intents: IntentsConfig,
        report_keywords: ReportKeywords,
    ) -> None:
        self.index = index
        self.llm = llm
        self.cfg = cfg
        self.intents = intents
        self.report_keywords = report_keywords
        self._answer_system = load_prompt("answer_system")
        self._report_system = load_prompt("report_system")
        self._intent_system = load_prompt("intent_system")
        self._bypass = [normalise(k) for words in cfg.bypass_keywords.values() for k in words]

    # --- answers ----------------------------------------------------------------------------
    def is_bypass(self, question: str) -> bool:
        q = f" {normalise(question)} "
        return any(k and k in q for k in self._bypass)

    def ask(
        self, question: str, language: Language, machine_type: str | None = None
    ) -> AskResponse:
        lang = language.value if isinstance(language, Language) else str(language)
        if self.index is None:
            return self._refuse(lang, "offline", "ask.not_indexed")
        hits = self.index.search(question, machine_type)
        if self.llm is not None:
            try:
                return self._online(question, lang, hits)
            except LlmUnavailableError:
                pass  # offline fallback, immediately (TRD §10.3)
        return self._offline(question, lang, hits)

    def _refuse(self, lang: str, mode: str, notice: str, text: str = "") -> AskResponse:
        return AskResponse(
            answer=text,
            citations=[],
            answerable=False,
            mode=mode,  # type: ignore[arg-type]
            language=Language(lang),
            notice_key=notice,
        )

    def sources_text(self, hits: list[Hit], lang: str) -> str:
        parts = []
        for h in hits:
            c = h.chunk
            block = f"[{c.chunk_id}] {c.title['en']} — {c.heading['en']}\n{c.text['en']}"
            if lang != "en" and lang in c.text:
                block += f"\n({lang}) {c.heading[lang]}\n{c.text[lang]}"
            parts.append(block)
        return "\n\n".join(parts)

    def _online(self, question: str, lang: str, hits: list[Hit]) -> AskResponse:
        assert self.llm is not None
        prompt = (
            f"LANGUAGE: {lang}\nQUESTION: {question}\n\nSOURCES:\n{self.sources_text(hits, lang)}"
        )
        try:
            out = self.llm.generate_json(self._answer_system, prompt)
        except LlmBadOutputError:
            return self._refuse(lang, "online", "ask.dont_know")
        answer = str(out.get("answer") or "").strip()
        raw = out.get("citations") or []
        cited = [c for c in raw if isinstance(c, str)] if isinstance(raw, list) else []
        answerable = out.get("answerable") is True
        by_id = {h.chunk.chunk_id: h.chunk for h in hits}
        if any(c not in by_id for c in cited):
            return self._refuse(lang, "online", "ask.dont_know")  # cited something it was not given
        if self.is_bypass(question):
            return self._refuse(lang, "online", "ask.refuse_bypass")
        if answerable and not cited:
            return self._refuse(lang, "online", "ask.dont_know")
        if not answerable:
            return self._refuse(lang, "online", "ask.dont_know", text=answer)
        if not answer:
            return self._refuse(lang, "online", "ask.dont_know")
        return AskResponse(
            answer=answer,
            citations=[citation(by_id[c], lang) for c in dict.fromkeys(cited)],
            answerable=True,
            mode="online",
            language=Language(lang),
        )

    def _offline(self, question: str, lang: str, hits: list[Hit]) -> AskResponse:
        if self.is_bypass(question):
            return self._refuse(lang, "offline", "ask.refuse_bypass")
        if not hits or hits[0].score < self.cfg.offline_min_score:
            return self._refuse(lang, "offline", "ask.offline_unknown")
        c = hits[0].chunk
        _, text, translated = c.for_language(lang)
        return AskResponse(
            answer=text,
            citations=[citation(c, lang)],
            answerable=True,
            mode="offline",
            language=Language(lang),
            notice_key=None if lang == "en" or translated else "ask.offline_english",
        )

    # --- voice commands ---------------------------------------------------------------------
    def classify(self, utterance: str, language: Language) -> IntentResponse:
        m = match_intent(utterance, self.intents)
        if m.intent != "question" or self.llm is None:
            return IntentResponse(intent=m.intent, matched=m.matched)
        lang = language.value if isinstance(language, Language) else str(language)
        try:
            out = self.llm.generate_json(
                self._intent_system, f"LANGUAGE: {lang}\nUTTERANCE: {utterance}"
            )
        except (LlmUnavailableError, LlmBadOutputError):
            return IntentResponse(intent="question")
        intent = out.get("intent")
        if intent in INTENT_NAMES:
            return IntentResponse(intent=str(intent), slots={"source": "online"})
        return IntentResponse(intent="question")

    # --- spoken reports ---------------------------------------------------------------------
    def parse_report(self, transcript: str, language: Language) -> tuple[ReportDraft, str]:
        """(draft, "online" | "offline"): online only when the provider returns a valid draft."""
        offline = parse_offline(transcript, language, self.report_keywords)
        if self.llm is None or not transcript.strip():
            return offline, "offline"
        lang = language.value if isinstance(language, Language) else str(language)
        try:
            out = self.llm.generate_json(
                self._report_system, f"LANGUAGE: {lang}\nTRANSCRIPT: {transcript}"
            )
            draft = ReportDraft(
                type=ReportType(out["type"]),
                severity=Severity(out["severity"]),
                summary_en=str(out["summary_en"]).strip() or offline.summary_en,
                summary_local=str(out.get("summary_local") or transcript).strip(),
                people_involved=bool(out.get("people_involved")),
                injury=bool(out.get("injury")),
                parser="online",
            )
        except (LlmUnavailableError, LlmBadOutputError, KeyError, ValueError, TypeError):
            return offline, "offline"
        return draft, "online"
