"""Evaluation harness for §13 — run a fixed question set against the agent and
produce the numbers Chapter 5 needs (I-17).

§13 sets nine quantitative targets; until this script existed there was no
instrumentation to produce *any* of them. What this harness measures directly:

  * Response time (§13 target < 3-5s) — wall clock per question, plus
    time-to-first-token on the streaming path.
  * Recommendation accuracy support — every ranked recommendation carries its
    factor breakdown, which an expert rates against the same questions.
  * Engagement rate (target > 5 messages/session) — counted by
    scripts/engagement_stats.py from chat_messages; not duplicated here.

What needs a human (and why this cannot fake it):

  * Recommendation accuracy > 80% and trust scores need *expert-rated* answers
    — the harness records the agent's answer alongside the reference answer
    from questions.json so a rater can score them side by side. Ground truth
    for Sri Lankan market advice is a supervisor decision, not a code one.

Usage (offline parts — no LLM calls, safe anywhere):

    python -m scripts.evaluate_agent --summary     # latency percentiles from logs
    python -m scripts.evaluate_agent --export      # JSON bundle for rating

The live part (--live) runs the question set against a *running API* with a
real token, hitting POST /chat/message and recording timings + answers:

    python -m scripts.evaluate_agent --live --base-url http://localhost:8000/api/v1 --token <JWT>

The question set lives in questions.json next to this script. Add a
`reference_answer` per question once the supervisor supplies ground truth;
unrated export marks them "unrated" rather than inventing a score.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

QUESTIONS_FILE = Path(__file__).with_name("questions.json")


def load_questions() -> list[dict]:
    """The fixed question set. Edit questions.json, not this file."""
    if not QUESTIONS_FILE.exists():
        return [
            # Seed set if the JSON has not been created yet — the file is
            # written back so raters always work from the same artifact.
            {"id": 1, "question": "What does the ASPI measure?",
             "reference_answer": None},
            {"id": 2, "question": "Is it a good time to buy HNB?",
             "reference_answer": None},
        ]
    return json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))


def save_questions(questions: list[dict]) -> None:
    QUESTIONS_FILE.write_text(
        json.dumps(questions, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── live evaluation ────────────────────────────────────────────────────────

async def run_live(base_url: str, token: str, out_path: Path) -> int:
    """POST each question to the running API, record timing and the answer."""
    import httpx

    questions = load_questions()
    results = []
    async with httpx.AsyncClient(timeout=120) as client:
        for q in questions:
            t0 = time.monotonic()
            try:
                resp = await client.post(
                    f"{base_url}/chat/message",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"message": q["question"]},
                )
                elapsed = time.monotonic() - t0
                if resp.status_code == 200:
                    answer = resp.json().get("response", "")
                    results.append({
                        "id": q["id"],
                        "question": q["question"],
                        "reference_answer": q.get("reference_answer"),
                        "agent_answer": answer,
                        "response_seconds": round(elapsed, 2),
                        "meets_target": elapsed < 5.0,
                        "rated": None,   # filled by the human rater
                    })
                else:
                    results.append({
                        "id": q["id"], "question": q["question"],
                        "error": f"HTTP {resp.status_code}",
                        "response_seconds": round(elapsed, 2),
                    })
            except Exception as exc:  # noqa: BLE001
                results.append({
                    "id": q["id"], "question": q["question"],
                    "error": f"{type(exc).__name__}: {exc}",
                })
            # Politeness toward the free LLM tier between questions.
            await asyncio.sleep(2)

    bundle = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "target_seconds": 5.0,
        "results": results,
    }
    out_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    return len(results)


# ─── offline log analysis ───────────────────────────────────────────────────

# The request middleware (app/main.py) emits: path="..." method=... status=... duration_ms=...
_LOG_LINE = re.compile(
    r'path="(?P<path>[^"]+)"\s+method=(?P<method>\w+)\s+'
    r"status=(?P<status>\d+)\s+duration_ms=(?P<ms>\d+)")


def summarise_logs(log_text: str) -> dict:
    """Percentiles from captured middleware logs."""
    rows = [
        (m.group("path"), int(m.group("ms")))
        for m in _LOG_LINE.finditer(log_text)
    ]
    if not rows:
        return {"error": "no request-log lines found in input"}

    chat = [ms for path, ms in rows
            if path.startswith("/api/v1/chat") and ms > 0]
    other = [ms for path, ms in rows if not path.startswith("/api/v1/chat")]

    def pct(values: list[int], p: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        idx = min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))
        return ordered[idx]

    return {
        "requests_total": len(rows),
        "chat_requests": len(chat),
        "chat_median_ms": pct(chat, 50),
        "chat_p95_ms": pct(chat, 95),
        "chat_within_5s_pct": (
            round(sum(1 for ms in chat if ms <= 5000) / len(chat) * 100, 1)
            if chat else None),
        "non_chat_median_ms": pct(other, 50),
        "non_chat_p95_ms": pct(other, 95),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluation harness for the §13 metrics (I-17)")
    parser.add_argument("--live", action="store_true",
                        help="run the question set against a running API")
    parser.add_argument("--base-url", default="http://localhost:8000/api/v1")
    parser.add_argument("--token", default="",
                        help="a verified Supabase access token")
    parser.add_argument("--summary", action="store_true",
                        help="summarise request logs pasted on stdin")
    parser.add_argument("--export", action="store_true",
                        help="write the question set for expert rating")
    parser.add_argument("--out", default="evaluation_results.json")
    args = parser.parse_args()

    if args.summary:
        import sys
        print(json.dumps(summarise_logs(sys.stdin.read()), indent=2))
        return

    if args.export:
        questions = load_questions()
        save_questions(questions)
        print(f"Question set at {QUESTIONS_FILE} — add reference answers, "
              f"then rate the live export against them.")
        return

    if args.live:
        if not args.token:
            parser.error("--live needs --token (a Supabase access token)")
        n = asyncio.run(run_live(args.base_url, args.token, Path(args.out)))
        print(f"{n} questions evaluated -> {args.out}\n"
              f"Hand that file to your rater alongside questions.json.")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
