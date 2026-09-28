"""Run the scheduled pipeline jobs once, in this process, without Redis.

For testing and one-off catch-up runs; in production Celery Beat triggers these
same tasks on the worker. Runs in eager mode, so the chained .delay() calls
(sentiment, embeddings, rule pushes) execute inline.

    python -m scripts.run_jobs market   # prices, indices, rule checks
    python -m scripts.run_jobs news     # news + sentiment + embeddings
    python -m scripts.run_jobs daily    # snapshots, company info, predictions

Exits non-zero if any job failed, so the Actions run shows red.
"""

import os
import sys
import time

os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"   # before celery_worker is imported

JOBS = {
    # Same grouping and order as the Beat schedule in celery_worker.py.
    "market": [
        "tasks.scrape_tasks.scrape_cse_data",
        "tasks.scrape_tasks.scrape_cse_indices",
        "tasks.rules_tasks.check_investment_rules",   # needs the fresh quotes
    ],
    "news": ["tasks.scrape_tasks.scrape_and_analyse_news"],
    "daily": [
        "tasks.scrape_tasks.snapshot_portfolio_values",
        "tasks.scrape_tasks.refresh_company_info",
        "tasks.scrape_tasks.update_price_predictions",
    ],
}


def main(groups: list[str]) -> int:
    unknown = [g for g in groups if g not in JOBS]
    if not groups or unknown:
        print(f"usage: python -m scripts.run_jobs {{{'|'.join(JOBS)}}} ...", file=sys.stderr)
        return 2

    from celery_worker import celery_app

    failures = 0
    for group in groups:
        for name in JOBS[group]:
            start = time.monotonic()
            try:
                result = celery_app.tasks[name].apply()
                result.get(propagate=True)
                print(f"ok    {name} ({time.monotonic() - start:.1f}s)", flush=True)
            except Exception as exc:  # keep going: one failed job must not skip the rest
                failures += 1
                print(f"FAIL  {name}: {type(exc).__name__}: {exc}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
