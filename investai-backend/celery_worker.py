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
#
# NOTE: crontab() below is evaluated in celery_app.conf.timezone
# (Asia/Colombo), NOT in UTC. CSE trades 09:30–14:30 Colombo time, so the
# trading-hours windows use hour="9-14" in local terms. The 09:00/09:15 ticks
# land before the open and the 14:45 tick after the close; those runs return no
# trade records and log the market status, which is harmless.
# ─────────────────────────────────────────────────────────────────────────────

celery_app.conf.beat_schedule = {
    # Market data: every 15 min during trading hours, Mon–Fri
    "scrape-cse-market-hours": {
        "task": "tasks.scrape_tasks.scrape_cse_data",
        "schedule": crontab(minute="*/15", hour="9-14", day_of_week="mon-fri"),
        "options": {"queue": "default"},
    },
    # Index readings: same window as the quotes, offset by 5 minutes so the two
    # scrapes do not hit cse.lk simultaneously. Re-scraping a session already
    # stored inserts nothing — (index_code, recorded_at) is unique — so the ticks
    # outside the session are harmless.
    "scrape-cse-indices-market-hours": {
        "task": "tasks.scrape_tasks.scrape_cse_indices",
        "schedule": crontab(minute="5,20,35,50", hour="9-14", day_of_week="mon-fri"),
        "options": {"queue": "default"},
    },
    # News: every 30 min around the clock (news doesn't stop at market close)
    "scrape-news-30min": {
        "task": "tasks.scrape_tasks.scrape_and_analyse_news",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "default"},
    },
    # Portfolio valuations: once a day at 15:10 Colombo, 40 minutes after the
    # 14:30 close, so the last market-hours scrape has landed.
    #
    # Every day, not just weekdays. A portfolio is worth something on a Saturday —
    # whatever Friday's close left it at — and skipping weekends would leave gaps a
    # chart would have to either bridge or misrepresent as a flat segment. Each
    # snapshot records which session its prices came from, so a weekend row is
    # identifiable as carrying Friday's prices rather than looking like new data.
    "snapshot-portfolio-values": {
        "task": "tasks.scrape_tasks.snapshot_portfolio_values",
        "schedule": crontab(minute="10", hour="15"),
        "options": {"queue": "default"},
    },
    # Investment rules: every 15 min during trading hours
    "check-investment-rules": {
        "task": "tasks.rules_tasks.check_investment_rules",
        "schedule": crontab(minute="*/15", hour="9-14", day_of_week="mon-fri"),
        "options": {"queue": "default"},
    },
    # Company fundamentals: once a day at 15:40 Colombo, half an hour after the
    # portfolio snapshot so the two long tasks do not overlap.
    #
    # Daily rather than intraday because sector, shares issued and market cap
    # change on corporate-action timescales. The sweep is 291 symbols x 2 POSTs and
    # measured 7.8 seconds, and it reads its symbol list from market_data_latest — so
    # it runs after the day's scrapes have landed and a newly listed symbol picks up
    # its name and sector on the same day it first trades.
    #
    # Every day, not weekdays. It is cheap, and running it on a Sunday is how a
    # sweep that failed on Friday self-heals before Monday's open rather than
    # leaving the app three days stale.
    "refresh-company-info": {
        "task": "tasks.scrape_tasks.refresh_company_info",
        "schedule": crontab(minute="40", hour="15"),
        "options": {"queue": "default"},
    },
}
