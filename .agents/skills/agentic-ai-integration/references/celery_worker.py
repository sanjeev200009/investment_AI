# celery_worker.py
"""
Celery application with Beat scheduler.

Workers:
  celery -A celery_worker worker --loglevel=info -Q default

Beat scheduler:
  celery -A celery_worker beat --loglevel=info

Monitor:
  celery -A celery_worker flower
"""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "investai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "tasks.scrape_tasks",
        "tasks.notification_tasks",
        "tasks.rules_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Colombo",   # IST/SL time
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,       # re-queue on worker crash
    task_reject_on_worker_lost=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Beat schedule
# CSE market hours: 9:30–14:30 local (3:00–9:00 UTC)
# ─────────────────────────────────────────────────────────────────────────────

celery_app.conf.beat_schedule = {
    # Market data: every 15 min during trading hours, Mon–Fri
    "scrape-cse-market-hours": {
        "task": "tasks.scrape_tasks.scrape_cse_data",
        "schedule": crontab(minute="*/15", hour="3-9", day_of_week="mon-fri"),
        "options": {"queue": "default"},
    },
    # News: every 30 min around the clock (news doesn't stop at market close)
    "scrape-news-30min": {
        "task": "tasks.scrape_tasks.scrape_and_analyse_news",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "default"},
    },
    # Investment rules: every 15 min during trading hours
    "check-investment-rules": {
        "task": "tasks.rules_tasks.check_investment_rules",
        "schedule": crontab(minute="*/15", hour="3-9", day_of_week="mon-fri"),
        "options": {"queue": "default"},
    },
}
