"""Ask Cat evaluation (TRD §10.6, §12): 40 questions, online and offline.

Metrics, per language and overall:
- citation accuracy: answerable questions whose answer cites at least one expected chunk (a
  refusal counts as a miss);
- retrieval hit@k: an expected chunk is among the retrieved chunks (explains citation misses);
- key-fact coverage: share of each question's key facts the answer contains, graded by an LLM
  judge with a fixed rubric (`prompts/judge_system.md`); without a key the coverage is not graded;
- refusal accuracy: unanswerable questions (not in the manuals, or asking to defeat a safety
  system) that the assistant refused.
Every LLM reply (answers and judge) goes through `CachedClient`: paced under the free tier's limit
and stored by prompt hash, so a re-run spends no quota. An online run that loses the provider
part-way falls back to offline answers; those are counted and reported, not hidden.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shiftmate.assistant.index import KnowledgeIndex, SentenceEmbedder
from shiftmate.assistant.llm import (
    CachedClient,
    LlmBadOutputError,
    LlmClient,
    LlmUnavailableError,
)
from shiftmate.assistant.service import Assistant, load_prompt
from shiftmate.config_loader import ShiftMateConfig
from shiftmate.schema.enums import Language

EVAL_SET = Path(__file__).parent / "assistant_eval.yaml"
LANGS = ["en", "hi", "ta"]


def judge_coverage(
    judge: LlmClient | None, system: str, answer: str, facts: list[str]
) -> float | None:
    if judge is None or not facts:
        return None
    listed = "\n".join(f"{i}. {f}" for i, f in enumerate(facts))
    try:
        out = judge.generate_json(system, f"KEY FACTS:\n{listed}\n\nANSWER:\n{answer}")
    except (LlmUnavailableError, LlmBadOutputError):
        return None
    covered = {int(i) for i in out.get("covered", []) if isinstance(i, int) and 0 <= i < len(facts)}
    return len(covered) / len(facts)


def run_mode(
    assistant: Assistant,
    index: KnowledgeIndex,
    items: dict[str, list[dict[str, Any]]],
    judge: LlmClient | None,
    judge_system: str,
    mode: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for q in items["answerable"]:
        hits = index.search(q["question"], q["machine_type"])
        r = assistant.ask(q["question"], Language(q["language"]), q["machine_type"])
        cited = [c.chunk_id for c in r.citations]
        text = r.answer
        rows.append(
            {
                "id": q["id"],
                "language": q["language"],
                "kind": "answerable",
                "retrieved": any(h.chunk.chunk_id in q["expected"] for h in hits),
                "answered": r.answerable,
                "citation_ok": r.answerable and any(c in q["expected"] for c in cited),
                "coverage": judge_coverage(judge, judge_system, text, q["facts"])
                if r.answerable and text
                else 0.0,
                "fell_back": mode == "online" and r.mode == "offline",
            }
        )
    for q in items["unanswerable"]:
        r = assistant.ask(q["question"], Language(q["language"]), q["machine_type"])
        rows.append(
            {
                "id": q["id"],
                "language": q["language"],
                "kind": "unanswerable",
                "refused": not r.answerable,
                "fell_back": mode == "online" and r.mode == "offline",
            }
        )
    return summarise(rows)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def block(sel: list[dict[str, Any]]) -> dict[str, Any]:
        ans = [r for r in sel if r["kind"] == "answerable"]
        una = [r for r in sel if r["kind"] == "unanswerable"]
        cov = [r["coverage"] for r in ans if r["coverage"] is not None]
        return {
            "answerable": len(ans),
            "citation_accuracy": _mean([1.0 if r["citation_ok"] else 0.0 for r in ans]),
            "retrieval_hit": _mean([1.0 if r["retrieved"] else 0.0 for r in ans]),
            "answered": _mean([1.0 if r["answered"] else 0.0 for r in ans]),
            "key_fact_coverage": _mean(cov) if len(cov) == len(ans) else None,
            "unanswerable": len(una),
            "refusal_accuracy": _mean([1.0 if r["refused"] else 0.0 for r in una]),
        }

    return {
        "overall": block(rows),
        "by_language": {lang: block([r for r in rows if r["language"] == lang]) for lang in LANGS},
        "fell_back": sum(1 for r in rows if r["fell_back"]),
        "rows": rows,
    }


def _pct(v: float | None) -> str:
    return "–" if v is None else f"{v * 100:.1f} %"


def _met(v: float | None, target: float) -> str:
    return "–" if v is None else ("met" if v >= target else "not met")


def render(results: dict[str, dict[str, Any]], model: str | None, index_meta: str) -> str:
    intro = (
        "40 questions in `eval/assistant_eval.yaml` (30 answerable: 10 en, 10 hi, 10 ta; 10 that "
        f"must be refused). {index_meta} "
    )
    if model:
        intro += (
            f"Online answers use `{model}`; key facts are graded by the same model with a "
            "fixed rubric (`assistant/prompts/judge_system.md`), and every reply is cached by "
            "prompt hash."
        )
    else:
        intro += "No LLM key was configured, so only offline results are reported."
    lines = ["## Ask Cat assistant (F-ASK-01…06)", "", intro]
    lines += [
        "",
        "Citation accuracy counts a refusal as a miss. Targets (TRD §12): citation accuracy and "
        "key-fact coverage ≥ 85 %, refusal accuracy ≥ 90 %.",
        "",
        "| mode | language | citation accuracy | key-fact coverage | retrieval hit@5 | "
        "answered | refusal accuracy |",
        "|---|---|---|---|---|---|---|",
    ]
    for mode, res in results.items():
        for lang, b in [("all", res["overall"]), *res["by_language"].items()]:
            lines.append(
                f"| {mode} | {lang} | {_pct(b['citation_accuracy'])} | "
                f"{_pct(b['key_fact_coverage'])} | {_pct(b['retrieval_hit'])} | "
                f"{_pct(b['answered'])} | {_pct(b['refusal_accuracy'])} |"
            )
    lines += [
        "",
        "| mode | citation ≥ 85 % | key facts ≥ 85 % | refusals ≥ 90 % |",
        "|---|---|---|---|",
    ]
    for mode, res in results.items():
        o = res["overall"]
        lines.append(
            f"| {mode} | {_met(o['citation_accuracy'], 0.85)} | "
            f"{_met(o['key_fact_coverage'], 0.85)} | {_met(o['refusal_accuracy'], 0.90)} |"
        )
    for mode, res in results.items():
        if res["fell_back"]:
            lines += [
                "",
                f"In the {mode} run, {res['fell_back']} of 40 questions got an offline answer "
                "because the provider did not answer (rate limit, timeout or server error).",
            ]
    misses = {
        mode: [r["id"] for r in res["rows"] if r["kind"] == "answerable" and not r["citation_ok"]]
        for mode, res in results.items()
    }
    wrong = {
        mode: [r["id"] for r in res["rows"] if r["kind"] == "unanswerable" and not r["refused"]]
        for mode, res in results.items()
    }
    lines += ["", "### Questions missed", ""]
    for mode in results:
        lines.append(
            f"- {mode}: answerable without an expected citation: "
            f"{', '.join(misses[mode]) or 'none'}; unanswerable but answered: "
            f"{', '.join(wrong[mode]) or 'none'}."
        )
    lines += [
        "",
        "Offline answers return the best-matching manual passage as written, and only when it "
        "scores at least 0.55 (TRD §10.4), so offline mode refuses more often: it prefers "
        "saying it does not know to guessing.",
    ]
    return "\n".join(lines)


def evaluate_assistant(
    cfg: ShiftMateConfig, models_dir: Path, data_dir: Path, llm: LlmClient | None
) -> tuple[dict[str, Any], str]:
    a = cfg.assistant
    index = KnowledgeIndex.load(
        models_dir / a.index_dir, SentenceEmbedder(models_dir / a.embedding_dir), a.retrieval
    )
    items = yaml.safe_load(EVAL_SET.read_text(encoding="utf-8"))
    cached = CachedClient(llm, data_dir / a.eval.cache_dir, a.eval.min_interval_s)
    judge = cached if llm is not None else None
    judge_system = load_prompt("judge_system")
    results: dict[str, dict[str, Any]] = {}
    offline = Assistant(index, None, a, cfg.intents, cfg.report_keywords)
    results["offline"] = run_mode(offline, index, items, judge, judge_system, "offline")
    if llm is not None:
        online = Assistant(index, cached, a, cfg.intents, cfg.report_keywords)
        results["online"] = run_mode(online, index, items, judge, judge_system, "online")
    meta = (
        f"The index holds {len(index.chunks)} chunks from "
        f"{len({c.file_id for c in index.chunks})} team-written files."
    )
    md = render(results, llm.model if llm else None, meta)
    metrics = {m: {k: v for k, v in r.items() if k != "rows"} for m, r in results.items()}
    metrics["llm_calls"] = {"made": cached.calls, "from_cache": cached.hits}
    return metrics, md
