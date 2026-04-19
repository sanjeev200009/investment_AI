# celery_worker.py
from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "investai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.scrape_tasks", "tasks.notification_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    # ■■ Beat Schedule (periodic tasks) ■■■■■■■■■■■■■■■■■■■■■■■■■■
    beat_schedule={
        "scrape-cse-every-15-min": {
            "task": "tasks.scrape_tasks.scrape_cse_market_data",
            "schedule": crontab(minute='*/15'),
        },
        "scrape-news-hourly": {
            "task": "tasks.scrape_tasks.scrape_all_news",
            "schedule": crontab(minute=0), # top of every hour
        },
    },
)
