# Model selection

Why these models, measured rather than assumed. Reproduce with:

```bash
python -m scripts.verify_llm_providers
```

## Constraints

| Constraint | Source |
| --- | --- |
| Free tier only | project has no LLM budget |
| Reliable multi-argument tool calling | the ReAct agent has 6 tools; `get_stock_data` takes a symbol *list* |
| Streaming with correct tool-call deltas | `agent/core.py` accumulates `delta.tool_calls` incrementally |
| Perceived response < 5 s | NFR-4 |
| NVIDIA primary, OpenRouter fallback only | deployment requirement |

## Starting state: the AI layer was completely dead

Three separate hardcoded models had all stopped working:

| Model | Used by | Status when tested |
| --- | --- | --- |
| `google/gemini-2.5-flash` | `agent/core.py`, `ai_providers.py` | **HTTP 402** — "This request requires more credits" |
| `google/gemini-flash-1.5` | `sentiment.py`, `rules_tasks.py` | **HTTP 404** — "No endpoints found" (retired) |
| `nvidia/nv-embedqa-e5-v5` | `agent/embeddings.py` | **HTTP 410 Gone** — end of life |

So the chat agent, news summarisation, alert explanations and the entire RAG
retrieval path were all non-functional. This is why model ids now live in
`app/config.py` and can be swapped without touching code.

## NVIDIA availability is narrower than the catalogue suggests

The account lists 83 models, but most return `404 "Not found for account"`.
Eight handled the real `TOOL_SCHEMAS` correctly (called `get_stock_data` with
both `HNB` and `COMB` in a valid JSON array):

| Model | Tool-call latency |
| --- | --- |
| `openai/gpt-oss-20b` | **682 ms** |
| `nvidia/nemotron-3-nano-30b-a3b` | 1 381 ms |
| `moonshotai/kimi-k3` | 1 426 ms |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | 2 542 ms |
| `nvidia/nemotron-3-super-120b-a12b` | 2 940 ms |
| `openai/gpt-oss-120b` | 11 500 ms |
| `minimaxai/minimax-m3` | 15 721 ms |
| `nvidia/nemotron-3-ultra-550b-a55b` | 18 100 ms |

The last three are excluded on latency alone: a ReAct turn needs at least two
sequential calls, so an 11.5 s single call cannot meet a 5 s budget.

## AGENT role → `openai/gpt-oss-20b` (NVIDIA)

Measured on the full round trip (tool call → tool result → grounded answer):

| Model | ReAct total | TTFB | Stream chunks | Notes |
| --- | --- | --- | --- | --- |
| **`openai/gpt-oss-20b`** | **2 874 ms** | 344 ms | 27 | clean tables, reasoning kept out of `content` |
| `nvidia/nemotron-3-nano-30b-a3b` | 6 719 ms | 454 ms | 24 | exceeds the NFR budget |

`gpt-oss-20b` wins on latency with ~1.7 s of headroom against NFR-4, and was the
only candidate whose streamed tool-call deltas reassembled into valid JSON on
every attempt.

## UTILITY role → `nvidia/nemotron-3-nano-30b-a3b` (NVIDIA)

This role nearly shipped a silent data-quality bug. Current free models are
*reasoning* models: they spend tokens on hidden reasoning before emitting visible
content. The call sites passed `max_tokens` of 100–250, and that budget was
consumed before any answer appeared:

| Model | Prompt | Visible content | Hidden reasoning | `finish_reason` |
| --- | --- | --- | --- | --- |
| `openai/gpt-oss-20b` | dashboard insight | **0 chars** | 761 chars | `length` |
| `openai/gpt-oss-20b` | alert explanation | 33 chars (cut off) | 695 chars | `length` |
| `nvidia/nemotron-3-nano-30b-a3b` | alert explanation | 75 chars (cut off) | 660 chars | `length` |

These are not crashes — they return HTTP 200 with an empty string, so blank AI
summaries would have been written to the database without any error.

Two fixes, both required:

1. **Ask for brevity in the prompt, not via `max_tokens`.** `LLM_UTILITY_MAX_TOKENS`
   is 700; the prompts still say "1-2 sentences".
2. **Turn reasoning down.** Each vendor exposes a different knob, applied by
   model-id prefix in `llm.py` and sent via `extra_body`:
   - `openai/gpt-oss*` → `reasoning_effort: "low"`
   - `nvidia/nemotron*` → `chat_template_kwargs: {"thinking": false}`

With both applied:

| Model | summary | alert | insight | hidden reasoning |
| --- | --- | --- | --- | --- |
| **`nvidia/nemotron-3-nano-30b-a3b`** | 1 237 ms | **818 ms** | 1 311 ms | **0 chars** |
| `openai/gpt-oss-20b` | 1 713 ms | 1 225 ms | 1 288 ms | 17–66 chars |

`nemotron-3-nano` is chosen: it is the fastest, and it is the only one that
emitted *no* hidden reasoning at all, so none of the token budget is wasted.

> Note: `extra_body`, not a top-level kwarg. The `openai` SDK validates its own
> signature and raises `TypeError` locally for unknown parameters, so the request
> never reaches the server. During development this made every NVIDIA utility
> call fail at 0 ms and drain silently into the OpenRouter fallback — the outputs
> still looked fine, which is exactly what made it hard to spot.

## OpenRouter fallback → `minimax/minimax-m3:free`

| Model | Tool calling | Latency | Note |
| --- | --- | --- | --- |
| **`minimax/minimax-m3:free`** | correct | 3 332 ms | also the only usable Sinhala |
| `nvidia/nemotron-3-super-120b-a12b:free` | correct | 3 945 ms | same family as the primary |
| `nvidia/nemotron-3.5-lightning:free` | correct | 6 111 ms | leaks reasoning into `content` |
| `z-ai/glm-5.2:free` | — | — | HTTP 429 rate-limited |
| `google/gemma-4-31b-it:free` | — | — | HTTP 429 rate-limited |

Those two 429s are the concrete argument for having a fallback chain at all: free
tiers are rate-limited unpredictably.

## Embeddings → `nvidia/nemotron-3-embed-1b`, 2048 dims

The previous 1024-dim model is 410 Gone, and every other NVIDIA embedding model
returns 404 for this account. `nemotron-3-embed-1b` is the only one available. It
emits 2048 dimensions and rejects a `dimensions` override
(`400 "dimensions must be one of 2048"`).

Consequences, handled in migration `b2c3d4e5f6a7`:

- The column widens from `vector(1024)` to `vector(2048)`.
- **The ivfflat index is dropped.** pgvector's ivfflat *and* hnsw both cap at
  2000 dimensions, so a 2048-dim column cannot be ANN-indexed. Cosine search
  becomes an exact sequential scan — correct at this scale (hundreds to low
  thousands of scraped articles, a few ms per scan) and it returns *exact*
  nearest neighbours rather than ivfflat's approximation.

The model is **asymmetric**: documents must be embedded with
`input_type="passage"` and queries with `input_type="query"`. Measured, identical
text embedded both ways gives cosine 0.60 vs 0.43, so the distinction is real.
The previous code embedded everything as `"query"`, including stored documents.
Retrieval now ranks correctly — for *"How did HNB's bank profits perform last
quarter?"*: 0.434 (HNB profit story) / 0.103 (tea exports) / 0.059 (telecoms).

## Sinhala (FR-6) is not achievable with these models

Tested with a Sinhala prompt, graded on native-script character count, Latin
character count, and degenerate-repetition ratio:

| Provider | Model | Result |
| --- | --- | --- |
| NVIDIA | `openai/gpt-oss-20b` | 0 chars — produced nothing, twice |
| NVIDIA | `nvidia/nemotron-3-nano-30b-a3b` | misread the prompt entirely; degenerate repetition with thinking off |
| NVIDIA | `openai/gpt-oss-120b`, `moonshotai/kimi-k3` | timed out |
| OpenRouter | `nvidia/nemotron-3-super-120b-a12b:free` | 59 chars, truncated mid-word |
| OpenRouter | `nvidia/nemotron-3.5-lightning:free` | leaked `"Here's a thinking process:"` into the answer; 1 721 Latin vs 103 native chars |
| OpenRouter | **`minimax/minimax-m3:free`** | **usable** — 388 native chars, coherent |

Tamil is broadly fine across the same set.

**Implication for FR-6:** multilingual *UI* via i18n string tables is unaffected.
Multilingual *AI chat in Sinhala* is not reliably achievable on the free tier —
only the OpenRouter fallback can do it, and relying on the fallback for a
first-class feature is not a sound design. The viable path is generate-in-English
then translate, for which NVIDIA exposes `nvidia/riva-translate-4b-instruct`.
That is tracked as issue I-15, not resolved here.
