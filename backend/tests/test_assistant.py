"""Ask Cat (TRD §10): knowledge chunking, hybrid retrieval, the provider layer, answer validation,
offline fallback, the safety-bypass guard, intents and the online report parser. A deterministic
hashing embedder and a scripted LLM stand in for the real model and provider."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from shiftmate.assistant.index import KnowledgeIndex, tokenize
from shiftmate.assistant.knowledge import load_knowledge, sections, windows
from shiftmate.assistant.llm import (
    CachedClient,
    LlmBadOutputError,
    LlmUnavailableError,
    make_client,
    parse_json_object,
)
from shiftmate.assistant.service import Assistant
from shiftmate.config_loader import load_config
from shiftmate.schema.config import ChunkConfig, RetrievalConfig
from shiftmate.schema.enums import Language
from shiftmate.settings import REPO_ROOT

CFG = load_config()


class HashEmbedder:
    """Bag of hashed tokens → a normalised 256-d vector (deterministic, no model download)."""

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), 256), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in tokenize(t):
                out[i, int(hashlib.md5(tok.encode()).hexdigest(), 16) % 256] += 1.0
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


class ScriptedLlm:
    model = "scripted"

    def __init__(self, *replies) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def generate_json(self, system: str, prompt: str):
        self.prompts.append(prompt)
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def write_kb(root: Path) -> Path:
    kb = root / "kb"
    kb.mkdir()
    (kb / "README.md").write_text("# not a knowledge file\n", encoding="utf-8")
    (kb / "seatbelt.md").write_text(
        "---\nid: seatbelt\ntitle: {en: Seatbelt, hi: सीट बेल्ट, ta: சீட் பெல்ட்}\n"
        "machine_types: [all]\nsection: safety\n---\n# Seatbelt\n\n"
        "## When to wear it\nFasten the seatbelt before you start the engine.\n\n"
        "## Checking it\nCheck the belt for cuts at every walkaround.\n",
        encoding="utf-8",
    )
    (kb / "seatbelt.ta.md").write_text(
        "---\nid: seatbelt\nlanguage: ta\n---\n# சீட் பெல்ட்\n\n"
        "## எப்போது போட வேண்டும்\nஇன்ஜினைத் தொடங்கும் முன் சீட் பெல்ட்டைப் போடுங்கள்.\n\n"
        "## சரிபார்த்தல்\nஒவ்வொரு சோதனையிலும் பெல்ட்டைப் பாருங்கள்.\n",
        encoding="utf-8",
    )
    (kb / "swing.md").write_text(
        "---\nid: swing\ntitle: {en: Swing radius, hi: घुमाव, ta: சுழற்சி}\n"
        "machine_types: [excavator]\nsection: safety\n---\n# Swing\n\n"
        "## The danger zone\nKeep people out of the swing radius of the excavator.\n",
        encoding="utf-8",
    )
    return kb


@pytest.fixture
def kb_index(tmp_path) -> KnowledgeIndex:
    chunks = load_knowledge(write_kb(tmp_path), ChunkConfig(max_words=350, overlap_words=50))
    return KnowledgeIndex.build(
        chunks, HashEmbedder(), RetrievalConfig(top_k=5, bm25_weight=0.5, dense_weight=0.5)
    )


def assistant(index, llm=None) -> Assistant:
    return Assistant(index, llm, CFG.assistant, CFG.intents, CFG.report_keywords)


# --- knowledge ---------------------------------------------------------------------------------


def test_chunks_follow_headings_and_translations_line_up(kb_index) -> None:
    ids = [c.chunk_id for c in kb_index.chunks]
    assert ids == ["seatbelt#1", "seatbelt#2", "swing#1"]
    c = kb_index.by_id["seatbelt#1"]
    assert c.heading == {"en": "When to wear it", "ta": "எப்போது போட வேண்டும்"}
    assert c.for_language("ta")[2] is True and c.for_language("hi")[2] is False


def test_long_sections_are_windowed_with_overlap() -> None:
    text = " ".join(f"w{i}" for i in range(800))
    parts = windows(text, 350, 50)
    assert [len(p.split()) for p in parts] == [350, 350, 200]
    assert parts[1].split()[0] == "w300"
    assert sections("# T\nintro\n## A\nx y\n## B\nz") == [("A", "x y"), ("B", "z")]


def test_a_translation_must_have_the_same_sections(tmp_path) -> None:
    kb = write_kb(tmp_path)
    (kb / "swing.hi.md").write_text(
        "---\nid: swing\n---\n# x\n## one\na\n## two\nb\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="same 1 sections"):
        load_knowledge(kb, ChunkConfig(max_words=350, overlap_words=50))


def test_the_real_knowledge_base_loads() -> None:
    chunks = load_knowledge(REPO_ROOT / CFG.assistant.knowledge_dir, CFG.assistant.chunk)
    files = {c.file_id for c in chunks}
    assert len(files) >= 15
    translated = {c.file_id for c in chunks if {"hi", "ta"} <= set(c.text)}
    assert {"seatbelt_rops", "swing_radius", "heat_hydration", "emergency_exit"} <= translated


# --- retrieval ---------------------------------------------------------------------------------


def test_retrieval_finds_the_passage_in_any_written_language(kb_index) -> None:
    assert kb_index.search("when do I fasten the seatbelt")[0].chunk.chunk_id == "seatbelt#1"
    top = kb_index.search("சீட் பெல்ட்டைப் போடுங்கள்")[0]
    assert top.chunk.chunk_id == "seatbelt#1" and top.language == "ta"


def test_machine_type_filters_chunks(kb_index) -> None:
    assert "swing#1" in [h.chunk.chunk_id for h in kb_index.search("swing radius", "excavator")]
    assert "swing#1" not in [h.chunk.chunk_id for h in kb_index.search("swing radius", "dozer")]


def test_words_the_knowledge_base_never_uses_weaken_a_match(kb_index) -> None:
    on_topic = kb_index.search("check the belt for cuts")[0]
    off_topic = kb_index.search("price of a new belt from the dealer shop")[0]
    assert on_topic.bm25 > 0.9 and off_topic.bm25 < 0.5


def test_index_round_trips_through_disk(tmp_path, kb_index) -> None:
    kb_index.save(tmp_path / "idx", "hash")
    again = KnowledgeIndex.load(tmp_path / "idx", HashEmbedder(), kb_index.cfg)
    assert [c.chunk_id for c in again.chunks] == [c.chunk_id for c in kb_index.chunks]
    q = "when do I fasten the seatbelt"
    assert again.search(q)[0].score == pytest.approx(kb_index.search(q)[0].score)


# --- provider layer ----------------------------------------------------------------------------


def test_json_replies_are_parsed_strictly() -> None:
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(LlmBadOutputError):
        parse_json_object("sorry, I cannot")
    with pytest.raises(LlmBadOutputError):
        parse_json_object("[1, 2]")


def test_no_key_means_offline_by_design() -> None:
    assert make_client("gemini", "", "", CFG.assistant.llm) is None
    assert make_client("other", "k", "", CFG.assistant.llm) is None


def test_the_eval_cache_spends_each_prompt_once(tmp_path) -> None:
    inner = ScriptedLlm({"x": 1})
    cached = CachedClient(inner, tmp_path, min_interval_s=0)
    assert cached.generate_json("s", "p") == {"x": 1}
    assert cached.generate_json("s", "p") == {"x": 1}  # from disk: the script has no second reply
    assert (cached.calls, cached.hits) == (1, 1)
    with pytest.raises(LlmUnavailableError):
        CachedClient(None, tmp_path, 0).generate_json("s", "new prompt")


# --- answers -----------------------------------------------------------------------------------


def test_online_answer_with_valid_citations(kb_index) -> None:
    llm = ScriptedLlm(
        {"answer": "Before you start the engine.", "citations": ["seatbelt#1"], "answerable": True}
    )
    r = assistant(kb_index, llm).ask("When do I wear the seatbelt?", Language.EN)
    assert r.mode == "online" and r.answerable and r.answer == "Before you start the engine."
    assert [c.chunk_id for c in r.citations] == ["seatbelt#1"]
    assert r.citations[0].section == "When to wear it"
    assert "[seatbelt#1]" in llm.prompts[0] and "LANGUAGE: en" in llm.prompts[0]


@pytest.mark.parametrize(
    "reply",
    [
        {"answer": "x", "citations": ["made-up#9"], "answerable": True},  # not retrieved
        {"answer": "x", "citations": [], "answerable": True},  # answerable without a source
        LlmBadOutputError("not json"),
    ],
)
def test_invalid_online_replies_become_refusals(kb_index, reply) -> None:
    r = assistant(kb_index, ScriptedLlm(reply)).ask("seatbelt?", Language.EN)
    assert not r.answerable and r.citations == [] and r.notice_key == "ask.dont_know"


def test_the_model_saying_it_does_not_know_is_kept(kb_index) -> None:
    reply = {"answer": "It is not in the manuals.", "citations": [], "answerable": False}
    r = assistant(kb_index, ScriptedLlm(reply)).ask("engine torque?", Language.EN)
    assert not r.answerable and r.answer == "It is not in the manuals." and r.mode == "online"


def test_provider_trouble_falls_back_to_offline_at_once(kb_index) -> None:
    llm = ScriptedLlm(LlmUnavailableError("rate_limit"))
    r = assistant(kb_index, llm).ask("when do I fasten the seatbelt", Language.TA)
    assert r.mode == "offline" and r.answerable
    assert r.answer == "இன்ஜினைத் தொடங்கும் முன் சீட் பெல்ட்டைப் போடுங்கள்."
    assert r.notice_key is None


def test_offline_falls_back_to_english_with_a_note(kb_index) -> None:
    r = assistant(kb_index).ask("keep people out of the swing radius", Language.HI, "excavator")
    assert r.answerable and r.notice_key == "ask.offline_english" and "swing radius" in r.answer


def test_offline_refuses_below_the_score_bar(kb_index) -> None:
    r = assistant(kb_index).ask("who won the cricket match yesterday", Language.EN)
    assert not r.answerable and r.notice_key == "ask.offline_unknown"


@pytest.mark.parametrize("q", ["How do I bypass the seatbelt switch?", "அலாரத்தை அணைப்பது எப்படி"])
def test_safety_bypass_is_refused_in_both_modes(kb_index, q) -> None:
    yes = {"answer": "Tie it.", "citations": ["seatbelt#1"], "answerable": True}
    online = assistant(kb_index, ScriptedLlm(yes)).ask(q, Language.EN)
    offline = assistant(kb_index).ask(q, Language.EN)
    for r in (online, offline):
        assert not r.answerable and r.notice_key == "ask.refuse_bypass" and r.answer == ""


def test_without_an_index_it_says_the_manual_is_not_loaded() -> None:
    r = assistant(None).ask("anything", Language.EN)
    assert r.notice_key == "ask.not_indexed"


# --- intents and reports -----------------------------------------------------------------------


def test_intents_try_the_rules_first_then_the_model() -> None:
    llm = ScriptedLlm({"intent": "time_left"}, {"intent": "fly_away"})
    a = assistant(None, llm)
    assert a.classify("next task please", Language.EN).intent == "next_task"
    assert llm.prompts == []  # the rules answered; no call
    assert a.classify("am I nearly finished with this", Language.EN).intent == "time_left"
    assert a.classify("hmm", Language.EN).intent == "question"  # unknown intent names are ignored


def test_spoken_report_online_and_its_fallback() -> None:
    good = {
        "type": "near_miss",
        "severity": "high",
        "summary_en": "A worker walked behind the bucket.",
        "summary_local": "ஒரு தொழிலாளி வாளிக்குப் பின்னால் நடந்தார்.",
        "people_involved": True,
        "injury": False,
    }
    a = assistant(None, ScriptedLlm(good, {"type": "picnic"}))
    draft, mode = a.parse_report("worker walked behind the bucket", Language.TA)
    assert mode == "online" and draft.parser == "online" and draft.severity.value == "high"
    draft, mode = a.parse_report("worker walked behind the bucket", Language.TA)
    assert mode == "offline" and draft.parser == "offline"
    assert json.loads(draft.model_dump_json())["type"] in ("near_miss", "incident")


# --- the gateway uses the assistant ------------------------------------------------------------


def test_gateway_endpoints_use_the_assistant(tmp_path, kb_index) -> None:
    from fastapi.testclient import TestClient

    from shiftmate.edge.app import create_app

    report = {
        "type": "equipment_problem",
        "severity": "low",
        "summary_en": "The left mirror is cracked.",
        "summary_local": "The left mirror is cracked.",
        "people_involved": False,
        "injury": False,
    }
    answer = {"answer": "Before you start.", "citations": ["seatbelt#1"], "answerable": True}
    llm = ScriptedLlm(report, answer)
    app = create_app(
        history_dir=tmp_path / "history",
        models_dir=tmp_path / "models",
        db_path=tmp_path / "edge.db",
        autorun=False,
        assistant=assistant(kb_index, llm),
    )
    with TestClient(app) as client:
        parsed = client.post(
            "/reports/parse", json={"transcript": "left mirror cracked", "language": "en"}
        ).json()
        assert parsed["mode"] == "online" and parsed["draft"]["parser"] == "online"
        assert parsed["context"]["machine_id"] == "EXC001"
        r = client.post(
            "/assistant/ask", json={"question": "When do I wear the seatbelt?", "language": "en"}
        ).json()
        assert r["mode"] == "online" and r["citations"][0]["chunk_id"] == "seatbelt#1"
