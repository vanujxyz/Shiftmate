# Milestone 14: Ask Cat assistant

## What was built
- **Knowledge base** (`knowledge/`): 15 team-written English files covering the TRD list, and Hindi and Tamil versions of the four key safety files (seatbelt, swing radius, heat, emergency exit). The files use the same thresholds as the machine's config. They are clearly sample content, and the cab always shows the banner (D-088).
- **Index** (`shiftmate assistant index`): chunks cut at headings (at most 350 words, 50 of overlap), with ids that name the same passage in every language. Retrieval is hybrid: BM25 with Indic-safe tokens plus the multilingual MiniLM embedder, saved locally, so it works offline. On the first run the command downloads the embedder once. 46 chunks and 70 indexed texts. The lexical score is weighted by how much of the question it covers, so off-topic questions don't pass (D-085).
- **Provider layer** (`assistant/llm.py`):
  - Gemini `gemini-3.5-flash-lite`, the model tested with this key (D-086);
  - JSON output, temperature 0, at most 600 tokens, a 12 s timeout;
  - a missing key, 429, timeout or server error falls back to offline at once;
  - the key is held as a secret and never logged.
- **Answers** (`assistant/service.py`, D-087):
  - online answers are checked: strict JSON, citations only from retrieved chunks, and an answer that claims to be answerable must cite a source;
  - offline answers are the best passage as written, in the operator's language when translated, and only above the 0.55 bar;
  - requests to defeat a safety system are refused in both modes.
- **Voice intents:** the keyword rules run first, then the model classifies what the rules miss. **Spoken reports:** the transcript goes to the model first, with the keyword parser as the fallback (F-REP-01). `/reports/parse` now reports `online` or `offline`.
- **Cab `/ask` screen:** type a question or tap an example, in en/hi/ta. Online answers show source chips; offline answers are labelled, with a note when a passage is only in English; refusals are said plainly; "Read it out" speaks the answer. For now the push-to-talk disc opens Ask Cat; voice arrives in milestone 15.
- **Evaluation** (`shiftmate eval assistant`, part of `eval all`): 40 questions, online and offline, with an LLM judge for key facts. Every call is paced and cached (D-089).

## Results (docs/EVAL.md, as measured)
| mode | citation accuracy | key-fact coverage | refusal accuracy |
|---|---|---|---|
| online (Gemini) | 93.3 % | 93.3 % | 100 % |
| offline | 66.7 % | 70.0 % | 100 % |

- **Online** meets every target (85 % for citations and key facts, 90 % for refusals). It missed two Tamil questions on topics with no Tamil translation (cold start, someone fainting).
- **Offline does not meet the citation and key-fact targets.** It answers only when the best passage clears 0.55, and so it refuses rather than guesses; its refusal accuracy is 100 %.

## Checked live (gateway running, key configured)
- **Online answers:**
  - a Tamil swing-radius question got a correct Tamil answer citing `swing_radius#3` in 3.5 s;
  - "bypass the seatbelt switch" was refused;
  - "price of a new bucket" came back as "not in the manuals, ask your supervisor or the dealer".
- **In the cab (Tamil, 1280 × 800):** tapping the example gave a Tamil answer with its source. The screen has no overflow, and no nav tab is marked while Ask Cat is open (a bug found and fixed).
- **Shell mangling (not an app bug):** a Tamil question sent from the shell with curl arrived garbled; from Python with UTF-8 it answered correctly.

## How to test
```
uv run --directory backend shiftmate assistant index
uv run --directory backend shiftmate eval assistant
uv run --directory backend shiftmate edge
pnpm --filter cab dev
```
Load Ravi's shift, sign in, and tap the push-to-talk disc.
```
pnpm test:all
pnpm lint:all
pnpm e2e
```

## Tests run
- **Backend:** 253 pass, 26 of them new:
  - knowledge chunking and translation alignment;
  - retrieval in any language, the machine-type filter and the coverage factor;
  - the index round trip;
  - strict JSON, the no-key path and the eval cache;
  - online answers and every refusal case;
  - offline fallback and its English note, and the score bar;
  - bypass refusal in both modes;
  - intents and the online report parser with its fallback;
  - the gateway using an injected assistant.

  The suite never calls the provider.
- **Frontend:** 200 pass (4 new Ask screen tests in the cab). **e2e:** 3 of 3. **Lint and contracts:** clean.

## Decisions
- D-085: retrieval scoring (a lexical match must cover the question).
- D-086: the LLM provider in practice.
- D-087: answer validation and the safety-bypass guard.
- D-088: the knowledge base.
- D-089: the assistant evaluation method.

## Observations (for the owner)
- **Tamil retrieval is the weak spot.** The multilingual embedder is weaker in Tamil than in Hindi. More hi/ta translations of the manuals would help most, but those need native review and weren't added just to pass evaluation questions.
- **`google-genai` pinned `websockets` from 17.1 to 16.1.1.** All tests pass.
- **LLM cache:** evaluation replies are cached in `data/cache/llm/` (git-ignored), so re-running the evaluation costs no quota.

## Downloads (as announced)
- `google-genai` 1.x (Python SDK) and its dependencies;
- the `paraphrase-multilingual-MiniLM-L12-v2` embedder, 466 MB, saved in `models/embeddings/` (git-ignored).
