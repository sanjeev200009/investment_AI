"""Unified LLM access with automatic provider failover.

NVIDIA NIM is the primary provider. OpenRouter is used *only* when NVIDIA fails,
is unavailable, rate-limited, or times out. Both expose an OpenAI-compatible
``/chat/completions`` API, so a single client type serves both — only ``base_url``,
``api_key`` and the model id differ.

Two call shapes exist because the codebase needs both:

* :func:`acreate` — the ReAct agent's tool-calling loop, streaming or not. Returns
  the raw provider response so ``agent/core.py`` keeps its own delta accumulation.
* :func:`complete_text` / :func:`complete_text_sync` — short one-shot generations
  (news summaries, rule explanations, dashboard insights). Return ``None`` on total
  failure so existing template fallbacks still work.

Model ids live in :mod:`app.config`, never inline here: we record ``ai_model_used``
per message for the §13 evaluation, and free-tier model availability changes
without notice.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any

import openai
from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.config import get_settings

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """Which model to use. Separated because the agent needs reliable tool
    calling while utility calls just need short prose, and the cheapest model
    that can do the second often cannot do the first."""

    AGENT = "agent"
    UTILITY = "utility"


# HTTP statuses meaning "this provider cannot serve the request right now" —
# hand off to the fallback. 402 = out of credits, 404 = model retired,
# 429 = rate limited, 401/403 = key rejected, 5xx = provider fault.
#
# 400 is deliberately absent: a malformed request is *our* bug and will fail on
# every provider. Failing over would burn the fallback's quota and hide the fault.
FAILOVER_STATUSES = frozenset({401, 402, 403, 404, 408, 409, 413, 429,
                               500, 502, 503, 504, 529})


class LLMUnavailable(RuntimeError):
    """Every provider in the chain failed."""


# Most current free models are *reasoning* models: they spend tokens on hidden
# reasoning before emitting any visible content. At the short budgets utility
# calls use, that returns EMPTY content with finish_reason='length' — a silent
# failure that would ship as blank AI summaries rather than as an error.
# Measured on openai/gpt-oss-20b (0 chars content / 761 chars hidden reasoning)
# and nvidia/nemotron-3-nano-30b-a3b (75 chars / 660 chars).
#
# Each vendor exposes a different knob to turn reasoning down, so match on the
# model-id prefix. Applied to UTILITY only: the agent's tool selection was
# verified at full reasoning effort and we don't want to weaken it.
#
# These go in `extra_body`, not as top-level kwargs: the openai SDK validates its
# own signature and raises TypeError locally for anything it doesn't know, so a
# top-level `chat_template_kwargs` never reaches the server — it just looks like
# a provider outage and silently drains into the fallback.
_REASONING_OFF: tuple[tuple[str, dict[str, Any]], ...] = (
    ("openai/gpt-oss", {"reasoning_effort": "low"}),
    ("nvidia/nemotron", {"chat_template_kwargs": {"thinking": False}}),
)


def _reasoning_kwargs(model: str) -> dict[str, Any]:
    for prefix, kwargs in _REASONING_OFF:
        if model.startswith(prefix):
            return dict(kwargs)
    return {}


@dataclass(frozen=True)
class Served:
    """Which provider and model actually answered. Recorded as ``ai_model_used``."""

    provider: str
    model: str
    attempt: int

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


@dataclass(frozen=True)
class _Provider:
    name: str
    base_url: str
    api_key: str
    agent_model: str
    utility_model: str
    extra_headers: dict[str, str] | None = None

    def model_for(self, role: Role) -> str:
        return self.agent_model if role is Role.AGENT else self.utility_model


@lru_cache
def _chain() -> tuple[_Provider, ...]:
    """Provider preference order. NVIDIA first, always.

    A provider with no API key is dropped rather than left to fail at request
    time — otherwise every call would waste a round trip on a 401 before
    reaching the provider that works.
    """
    s = get_settings()
    candidates = [
        _Provider(
            name="nvidia",
            base_url=s.NVIDIA_BASE_URL,
            api_key=s.NVIDIA_API_KEY,
            agent_model=s.NVIDIA_AGENT_MODEL,
            utility_model=s.NVIDIA_UTILITY_MODEL,
        ),
        _Provider(
            name="openrouter",
            base_url=s.OPENROUTER_BASE_URL,
            api_key=s.OPENROUTER_API_KEY,
            agent_model=s.OPENROUTER_AGENT_MODEL,
            utility_model=s.OPENROUTER_UTILITY_MODEL,
            # OpenRouter uses these for request attribution on its dashboard.
            extra_headers={"HTTP-Referer": s.FRONTEND_URL, "X-Title": "InvestAI"},
        ),
    ]
    live = tuple(p for p in candidates if p.api_key)
    if not live:
        logger.error("No LLM provider configured: set NVIDIA_API_KEY and/or "
                     "OPENROUTER_API_KEY in .env")
    else:
        logger.info("LLM provider chain: %s",
                    " -> ".join(f"{p.name}({p.model_for(Role.AGENT)})" for p in live))
    return live


@lru_cache
def _async_client(base_url: str, api_key: str, timeout: float) -> openai.AsyncOpenAI:
    return openai.AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout,
                              max_retries=0)  # retries are our job, per-provider


@lru_cache
def _sync_client(base_url: str, api_key: str, timeout: float) -> openai.OpenAI:
    return openai.OpenAI(base_url=base_url, api_key=api_key, timeout=timeout,
                         max_retries=0)


def _should_failover(exc: Exception) -> bool:
    """True if another provider might succeed where this one didn't."""
    if isinstance(exc, (APITimeoutError, APIConnectionError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in FAILOVER_STATUSES
    # Anything else — a TypeError from an unsupported kwarg, a bug in our own
    # request assembly — is not an outage, and failing over would hide it behind
    # a working fallback while making the primary look permanently dead. A
    # top-level `chat_template_kwargs` did exactly that until this returned False.
    return False


def _describe(exc: Exception) -> str:
    if isinstance(exc, APIStatusError):
        return f"HTTP {exc.status_code}"
    return type(exc).__name__


async def acreate(
    *,
    messages: list[dict],
    tools: list[dict] | None = None,
    stream: bool = False,
    role: Role = Role.AGENT,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> tuple[Any, Served]:
    """Create a chat completion, failing over across the provider chain.

    Returns ``(response, served)``. With ``stream=True`` the response is an
    async iterator of chunks, matching ``openai``'s own return type.

    Failover for streaming happens at the point the request is issued — the
    ``await`` below completes only after the provider has accepted the request
    and returned response headers, so a 402/429/timeout surfaces here, *before*
    any token has been handed to the caller. Once streaming has begun a provider
    switch is impossible (tokens are already on the wire), which is why the
    timeout is deliberately short.
    """
    chain = _chain()
    if not chain:
        raise LLMUnavailable("no LLM provider has an API key configured")

    timeout = get_settings().LLM_TIMEOUT_SECONDS
    failures: list[str] = []

    for attempt, provider in enumerate(chain, start=1):
        model = provider.model_for(role)
        client = _async_client(provider.base_url, provider.api_key, timeout)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if role is Role.UTILITY and (extra := _reasoning_kwargs(model)):
            kwargs["extra_body"] = extra
        if provider.extra_headers:
            kwargs["extra_headers"] = provider.extra_headers

        t0 = time.monotonic()
        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - classified below
            ms = int((time.monotonic() - t0) * 1000)
            reason = _describe(exc)
            failures.append(f"{provider.name}/{model}: {reason}")
            if not _should_failover(exc):
                logger.error("LLM %s/%s rejected the request (%s) after %dms — not "
                             "retrying other providers, this looks like a bug in the "
                             "request itself", provider.name, model, reason, ms)
                raise
            remaining = len(chain) - attempt
            logger.warning("LLM %s/%s unavailable (%s) after %dms; %s",
                           provider.name, model, reason, ms,
                           "falling back" if remaining else "no fallback left")
            continue

        if attempt > 1:
            logger.info("LLM served by fallback %s/%s after %s",
                        provider.name, model, "; ".join(failures))
        return response, Served(provider.name, model, attempt)

    raise LLMUnavailable("all LLM providers failed: " + "; ".join(failures))


async def complete_text(
    prompt: str,
    *,
    system: str | None = None,
    role: Role = Role.UTILITY,
    max_tokens: int | None = None,
    temperature: float = 0.3,
) -> str | None:
    """One-shot text generation. ``None`` if every provider failed.

    ``max_tokens`` defaults to ``LLM_UTILITY_MAX_TOKENS`` rather than to a small
    number: callers ask for "2 sentences" in the prompt, and enforcing brevity
    via the token cap instead is what produced empty output on reasoning models.

    Callers keep their own template fallback for the ``None`` case, so a dead
    LLM degrades the feature rather than breaking the request.
    """
    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
    try:
        response, served = await acreate(
            messages=messages, role=role, temperature=temperature,
            max_tokens=max_tokens or get_settings().LLM_UTILITY_MAX_TOKENS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("complete_text failed on every provider: %s", exc)
        return None

    text = (response.choices[0].message.content or "").strip()
    if not text:
        logger.warning("complete_text: %s returned empty content", served.label)
        return None
    return text


def complete_text_sync(
    prompt: str,
    *,
    system: str | None = None,
    role: Role = Role.UTILITY,
    max_tokens: int | None = None,
    temperature: float = 0.3,
) -> str | None:
    """Blocking twin of :func:`complete_text`, for the sync dashboard endpoint.

    FastAPI runs ``def`` endpoints in a threadpool, so blocking here is safe and
    avoids making the surrounding blocking SQLAlchemy queries async.
    """
    chain = _chain()
    if not chain:
        return None

    settings = get_settings()
    timeout = settings.LLM_TIMEOUT_SECONDS
    max_tokens = max_tokens or settings.LLM_UTILITY_MAX_TOKENS
    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]

    for provider in chain:
        model = provider.model_for(role)
        client = _sync_client(provider.base_url, provider.api_key, timeout)
        kwargs: dict[str, Any] = {
            "model": model, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens,
        }
        if role is Role.UTILITY and (extra := _reasoning_kwargs(model)):
            kwargs["extra_body"] = extra
        if provider.extra_headers:
            kwargs["extra_headers"] = provider.extra_headers
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            if not _should_failover(exc):
                logger.error("LLM %s/%s rejected request: %s", provider.name,
                             model, _describe(exc))
                return None
            logger.warning("LLM %s/%s unavailable (%s), trying next",
                           provider.name, model, _describe(exc))
            continue
        text = (response.choices[0].message.content or "").strip()
        if text:
            return text
        logger.warning("LLM %s/%s returned empty content", provider.name, model)

    return None


def provider_chain_summary() -> list[dict[str, str]]:
    """Introspection for the health endpoint and the §13 write-up."""
    return [
        {"order": str(i), "provider": p.name,
         "agent_model": p.agent_model, "utility_model": p.utility_model}
        for i, p in enumerate(_chain(), start=1)
    ]
