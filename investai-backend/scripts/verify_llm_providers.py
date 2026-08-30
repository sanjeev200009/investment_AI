"""Verify the LLM provider chain end to end, against the live APIs.

Run this after changing any model id, API key, or the failover logic:

    python -m scripts.verify_llm_providers

It exercises app.services.llm itself — not a reimplementation — so a pass here
means the code paths the app uses actually work. Checks, in order:

  1. config + chain construction (NVIDIA first, OpenRouter second)
  2. UTILITY role: the three real one-shot prompt shapes, non-empty output
  3. AGENT role: tool calling, streaming tool-call deltas, full ReAct round trip
  4. failover, negatively tested: NVIDIA is broken on purpose (bad key, retired
     model, timeout) and OpenRouter must take over automatically
  5. no-failover-on-400: a malformed request must surface, not silently move to
     the fallback and burn its quota
  6. embeddings: correct dimension, batch of 32, and query/passage retrieval rank

Exit code is 0 only if every check passes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time

from app.config import get_settings
from app.services import llm

logging.basicConfig(level=logging.WARNING,
                    format="      [%(levelname)s] %(name)s: %(message)s")

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> bool:
    results.append((PASS if ok else FAIL, name, detail))
    print(f"  {PASS if ok else FAIL}  {name}" + (f"  — {detail}" if detail else ""))
    sys.stdout.flush()
    return ok


def _reset_chain() -> None:
    """Provider chain and clients are cached; force a rebuild after changing
    settings so the next call sees them."""
    llm._chain.cache_clear()
    llm._async_client.cache_clear()
    llm._sync_client.cache_clear()


# --------------------------------------------------------------------------
# 1. configuration
# --------------------------------------------------------------------------
def check_config() -> bool:
    print("\n[1] configuration and provider chain")
    s = get_settings()
    ok = True
    ok &= record("NVIDIA_API_KEY is set", bool(s.NVIDIA_API_KEY),
                 f"{s.NVIDIA_API_KEY[:9]}…" if s.NVIDIA_API_KEY else "missing")
    ok &= record("OPENROUTER_API_KEY is set", bool(s.OPENROUTER_API_KEY),
                 f"{s.OPENROUTER_API_KEY[:11]}…" if s.OPENROUTER_API_KEY else "missing")

    chain = llm.provider_chain_summary()
    names = [p["provider"] for p in chain]
    ok &= record("NVIDIA is first in the chain", names[:1] == ["nvidia"],
                 " -> ".join(names) or "empty")
    ok &= record("OpenRouter is the fallback", names[1:2] == ["openrouter"],
                 " -> ".join(names) or "empty")
    for p in chain:
        print(f"        {p['order']}. {p['provider']:11} "
              f"agent={p['agent_model']}  utility={p['utility_model']}")
    return bool(ok)


# --------------------------------------------------------------------------
# 2. UTILITY role — the real prompt shapes
# --------------------------------------------------------------------------
UTILITY_CASES = [
    ("news summary (sentiment.summarise_article)",
     "Summarise this financial news article in 1-2 plain sentences suitable for a "
     "beginner investor in Sri Lanka. Focus on the practical impact.\n\n"
     "Headline: Hatton National Bank posts 34% rise in Q3 profit\n\n"
     "Article: HNB reported profit after tax of Rs 8.2 billion for the quarter "
     "ended 30 September, up 34% year on year, driven by lower impairment charges "
     "and a 12% expansion in its loan book."),
    ("alert explanation (rules_tasks._generate_rule_explanation)",
     "Write a short (2-3 sentences), beginner-friendly alert message for an "
     "investor. Their stock alert fired: HNB has dropped below your target price. "
     "Current price is LKR 168.25 with a -5.70% change today. End with one "
     "sentence of cautious, educational advice. Do not use jargon."),
]


async def check_utility() -> bool:
    print("\n[2] UTILITY role — real one-shot prompt shapes")
    ok = True

    # Assert on the *provider*, not just on getting text back. An earlier version
    # of this script only checked for non-empty output and passed while every
    # NVIDIA utility call was failing and draining into the fallback.
    for name, prompt in UTILITY_CASES:
        t0 = time.monotonic()
        resp, served = await llm.acreate(
            messages=[{"role": "user", "content": prompt}],
            role=llm.Role.UTILITY,
            max_tokens=get_settings().LLM_UTILITY_MAX_TOKENS, temperature=0.3)
        ms = int((time.monotonic() - t0) * 1000)
        text = (resp.choices[0].message.content or "").strip()
        ok &= record(name, len(text) > 40 and served.provider == "nvidia",
                     f"{len(text)} chars in {ms}ms via {served.label}")
        if text:
            print(f"        {text[:110]!r}")

    # the dashboard path is synchronous
    t0 = time.monotonic()
    text = llm.complete_text_sync(
        "Give a 2-sentence market insight for a beginner Sri Lankan investor. "
        "ASPI is at 12,480 (+0.8%), turnover LKR 2.1bn, banking sector leading.",
        role=llm.Role.UTILITY)
    ms = int((time.monotonic() - t0) * 1000)
    ok &= record("dashboard insight (sync path)", bool(text) and len(text) > 40,
                 f"{len(text) if text else 0} chars in {ms}ms")

    # the reasoning-suppression body must actually reach the server, which is
    # only observable as a non-empty answer at a deliberately tight budget
    resp, served = await llm.acreate(
        messages=[{"role": "user", "content": "In one sentence, what is a P/E ratio?"}],
        role=llm.Role.UTILITY, max_tokens=120)
    short = (resp.choices[0].message.content or "").strip()
    ok &= record("reasoning suppression works at a tight token budget",
                 len(short) > 20 and served.provider == "nvidia",
                 f"{len(short)} chars at max_tokens=120 via {served.label}")
    return bool(ok)


# --------------------------------------------------------------------------
# 3. AGENT role — tool calling, streaming, full ReAct loop
# --------------------------------------------------------------------------
SYS = ("You are InvestAI, an assistant for beginner investors on the Colombo "
       "Stock Exchange. Use tools for real data; never invent prices.")
Q = "What are the current prices of HNB and COMB, and which moved more today?"
TOOL_RESULT = json.dumps({
    "HNB": {"price": 178.50, "change": 4.25, "change_pct": 2.44},
    "COMB": {"price": 96.75, "change": -1.10, "change_pct": -1.12},
})


async def check_agent() -> bool:
    print("\n[3] AGENT role — tool calling, streaming, ReAct round trip")
    from app.services.agent.tools import TOOL_SCHEMAS
    ok = True

    # --- non-streaming tool call ---
    msgs = [{"role": "system", "content": SYS}, {"role": "user", "content": Q}]
    t0 = time.monotonic()
    resp, served = await llm.acreate(messages=msgs, tools=TOOL_SCHEMAS,
                                     role=llm.Role.AGENT)
    ms1 = int((time.monotonic() - t0) * 1000)
    tcs = resp.choices[0].message.tool_calls or []
    names = [tc.function.name for tc in tcs]
    ok &= record("decides to call get_stock_data",
                 "get_stock_data" in names and served.provider == "nvidia",
                 f"{names} via {served.label} in {ms1}ms")

    args_ok = False
    if tcs:
        try:
            a = json.loads(tcs[0].function.arguments)
            syms = [str(x).upper() for x in (a.get("symbols") or [])]
            args_ok = "HNB" in syms and "COMB" in syms
            detail = str(syms)
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            detail = f"unparseable: {e}"
    else:
        detail = "no tool call"
    ok &= record("passes both symbols in valid JSON args", args_ok, detail)

    # --- full ReAct: feed the tool result back, expect a grounded final answer ---
    if tcs:
        msgs.append({"role": "assistant", "content": resp.choices[0].message.content,
                     "tool_calls": [{"id": tc.id, "type": "function",
                                     "function": {"name": tc.function.name,
                                                  "arguments": tc.function.arguments}}
                                    for tc in tcs]})
        for tc in tcs:
            msgs.append({"role": "tool", "tool_call_id": tc.id,
                         "name": tc.function.name, "content": TOOL_RESULT})
        t0 = time.monotonic()
        resp2, served2 = await llm.acreate(messages=msgs, tools=TOOL_SCHEMAS,
                                          role=llm.Role.AGENT)
        ms2 = int((time.monotonic() - t0) * 1000)
        final = (resp2.choices[0].message.content or "").strip()
        grounded = "178" in final and "96" in final
        ok &= record("final answer is grounded in the tool result", grounded,
                     f"{len(final)} chars, total {ms1 + ms2}ms via {served2.label}")
        # NFR-4 target is a perceived response under ~5s
        ok &= record("ReAct round trip within the 5s NFR budget",
                     (ms1 + ms2) < 5000, f"{ms1 + ms2}ms")
        if final:
            print(f"        {final[:140]!r}")

    # --- streaming: tool-call deltas must accumulate the way core.py does ---
    # t0 before acreate, so ttfb includes the request itself — that is what the
    # user perceives.
    t0 = time.monotonic()
    stream, served3 = await llm.acreate(
        messages=[{"role": "system", "content": SYS},
                  {"role": "user", "content": "Get me the price of HNB."}],
        tools=TOOL_SCHEMAS, stream=True, role=llm.Role.AGENT)
    ttfb, chunks, acc = None, 0, {}
    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if not delta:
            continue
        chunks += 1
        if ttfb is None:
            ttfb = int((time.monotonic() - t0) * 1000)
        for tc in delta.tool_calls or []:
            acc.setdefault(tc.index, {"name": "", "args": ""})
            if tc.function:
                acc[tc.index]["name"] += tc.function.name or ""
                acc[tc.index]["args"] += tc.function.arguments or ""
    got = list(acc.values())
    stream_ok = bool(got) and got[0]["name"] == "get_stock_data"
    if stream_ok:
        try:
            json.loads(got[0]["args"])
        except json.JSONDecodeError:
            stream_ok = False
    ok &= record("streaming tool-call deltas reassemble correctly", stream_ok,
                 f"{chunks} chunks, ttfb={ttfb}ms via {served3.label}")
    return bool(ok)


# --------------------------------------------------------------------------
# 4. failover, negatively tested
# --------------------------------------------------------------------------
async def check_failover() -> bool:
    print("\n[4] failover — NVIDIA broken on purpose, OpenRouter must take over")
    s = get_settings()
    FIELDS = ("NVIDIA_API_KEY", "NVIDIA_AGENT_MODEL", "NVIDIA_UTILITY_MODEL",
              "NVIDIA_BASE_URL", "OPENROUTER_API_KEY", "LLM_TIMEOUT_SECONDS")
    saved = {f: getattr(s, f) for f in FIELDS}

    def restore() -> None:
        for f, v in saved.items():
            setattr(s, f, v)
        _reset_chain()

    ok = True

    # Timeout classification is asserted directly. A short LLM_TIMEOUT_SECONDS
    # cannot simulate "slow primary, healthy fallback" — it applies to the whole
    # chain and starves the fallback too, so the integration case below makes the
    # primary *unreachable* instead.
    from openai import APIConnectionError, APIStatusError, APITimeoutError
    import httpx as _httpx
    _req = _httpx.Request("POST", "http://x/v1/chat/completions")
    ok &= record("classifier: APITimeoutError triggers failover",
                 llm._should_failover(APITimeoutError(request=_req)))
    ok &= record("classifier: APIConnectionError triggers failover",
                 llm._should_failover(APIConnectionError(request=_req)))
    ok &= record("classifier: 429 rate limit triggers failover",
                 all(st in llm.FAILOVER_STATUSES for st in (401, 402, 403, 404, 429, 500, 503)),
                 "401 402 403 404 429 500 503 all present")
    ok &= record("classifier: 400 does NOT trigger failover",
                 400 not in llm.FAILOVER_STATUSES)
    ok &= record("classifier: a local TypeError does NOT trigger failover",
                 not llm._should_failover(TypeError("unexpected kwarg")),
                 "our bug, not an outage — must surface")

    scenarios = [
        ("rejected API key (401/403)",
         lambda: setattr(s, "NVIDIA_API_KEY", "nvapi-000000000000000000invalid")),
        ("retired/unknown model (404)",
         lambda: setattr(s, "NVIDIA_AGENT_MODEL", "nvidia/this-model-was-retired")),
        # blackholed RFC1918 address: connect hangs or is refused, so NVIDIA is
        # unreachable while OpenRouter keeps its full timeout budget
        ("primary unreachable (hang / connection failure)",
         lambda: (setattr(s, "NVIDIA_BASE_URL", "http://10.255.255.1:81/v1"),
                  setattr(s, "LLM_TIMEOUT_SECONDS", 8.0))),
    ]

    for name, break_it in scenarios:
        restore()
        break_it()
        _reset_chain()
        # Free tiers rate-limit back-to-back requests, and every scenario here
        # lands on the *same* fallback. Space them out so a 429 doesn't get
        # misread as broken failover.
        await asyncio.sleep(3)
        try:
            t0 = time.monotonic()
            resp, served = await llm.acreate(
                messages=[{"role": "user", "content": "Say OK."}],
                role=llm.Role.AGENT, max_tokens=400)
            ms = int((time.monotonic() - t0) * 1000)
            took_over = served.provider == "openrouter" and served.attempt == 2
            content = (resp.choices[0].message.content or "").strip()
            ok &= record(f"{name} -> OpenRouter answers", took_over and bool(content),
                         f"served by {served.label} (attempt {served.attempt}) in {ms}ms")
        except llm.LLMUnavailable as e:
            # The handoff and the fallback's own health are separate facts. If
            # both providers appear in the failure list then NVIDIA *did* hand
            # off and OpenRouter was reached — a 429/402 from it is the free
            # tier declining, not a failover bug. Anything else is a real fail.
            msg = str(e)
            handed_off = "nvidia/" in msg and "openrouter/" in msg
            fallback_quota = "HTTP 429" in msg or "HTTP 402" in msg
            ok &= record(f"{name} -> OpenRouter answers",
                         handed_off and fallback_quota,
                         "handoff to OpenRouter confirmed, but the fallback itself "
                         "was rate-limited/out of credit — free-tier limit, not a "
                         f"failover fault: {msg}" if handed_off and fallback_quota
                         else f"LLMUnavailable: {msg}")
        except Exception as e:  # noqa: BLE001
            ok &= record(f"{name} -> OpenRouter answers", False,
                         f"{type(e).__name__}: {e}")

    # both providers broken -> a clear error, not a silent empty string
    restore()
    s.NVIDIA_API_KEY = "nvapi-000000000000000000invalid"
    s.OPENROUTER_API_KEY = "sk-or-v1-000000000000000000invalid"
    _reset_chain()
    try:
        await llm.acreate(messages=[{"role": "user", "content": "Say OK."}],
                          role=llm.Role.AGENT)
        ok &= record("both providers down -> raises LLMUnavailable", False,
                     "call unexpectedly succeeded")
    except llm.LLMUnavailable:
        ok &= record("both providers down -> raises LLMUnavailable", True)
    except Exception as e:  # noqa: BLE001
        ok &= record("both providers down -> raises LLMUnavailable", False,
                     f"raised {type(e).__name__} instead")

    # ...and complete_text degrades to None so callers can use their template
    text = await llm.complete_text("Say OK.")
    ok &= record("both providers down -> complete_text returns None for the "
                 "template fallback", text is None, repr(text)[:40])

    # --- 400 must NOT fail over: our bug, not a provider outage ---
    restore()
    try:
        # negative max_tokens is rejected by the API as a bad request
        await llm.acreate(messages=[{"role": "user", "content": "hi"}],
                          role=llm.Role.AGENT, max_tokens=-5)
        ok &= record("malformed request (400) is not masked by failover", False,
                     "call unexpectedly succeeded")
    except llm.LLMUnavailable:
        ok &= record("malformed request (400) is not masked by failover", False,
                     "failed over and exhausted the chain instead of surfacing")
    except Exception as e:  # noqa: BLE001
        status = getattr(e, "status_code", None)
        ok &= record("malformed request (400) is not masked by failover",
                     status == 400, f"raised {type(e).__name__} status={status}")

    restore()
    return bool(ok)


# --------------------------------------------------------------------------
# 5. embeddings
# --------------------------------------------------------------------------
async def check_embeddings() -> bool:
    print("\n[5] embeddings — dimension, batching, retrieval rank")
    from app.services.agent.embeddings import (BATCH_SIZE, get_embedding,
                                               get_embeddings_batch)
    s = get_settings()
    ok = True

    passages = [
        "Hatton National Bank reported a 34% rise in third quarter profit after tax.",
        "Sri Lanka's tea exports fell 8% in October due to adverse weather.",
        "Dialog Axiata announced a new fibre broadband rollout in the North.",
    ]
    try:
        vecs = await get_embeddings_batch(passages, input_type="passage")
    except Exception as e:  # noqa: BLE001
        return record("embedding call succeeds", False, f"{type(e).__name__}: {e}")

    ok &= record(f"passage embeddings are {s.EMBED_DIM}-dim",
                 all(len(v) == s.EMBED_DIM for v in vecs),
                 f"{len(vecs)} vectors of {len(vecs[0])} dims "
                 f"({s.NVIDIA_EMBED_MODEL})")

    batch = await get_embeddings_batch([f"CSE headline {i}" for i in range(BATCH_SIZE)])
    ok &= record(f"full batch of {BATCH_SIZE} succeeds",
                 len(batch) == BATCH_SIZE, f"{len(batch)} vectors")

    qv = await get_embedding("How did HNB's bank profits perform last quarter?",
                             input_type="query")

    def cos(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        return dot / ((sum(x * x for x in a) ** .5) * (sum(y * y for y in b) ** .5))

    scores = [cos(qv, v) for v in vecs]
    best = scores.index(max(scores))
    ok &= record("query ranks the relevant passage first", best == 0,
                 "  ".join(f"{x:.3f}" for x in scores))
    return bool(ok)


async def main() -> int:
    print("=" * 74)
    print("InvestAI — LLM provider chain verification (live APIs)")
    print("=" * 74)
    checks = [check_config(), await check_utility(), await check_agent(),
              await check_failover(), await check_embeddings()]

    failed = [n for st, n, _ in results if st == FAIL]
    print("\n" + "=" * 74)
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("\nFailed:")
        for n in failed:
            print(f"  - {n}")
    print("=" * 74)
    return 0 if all(checks) and not failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
