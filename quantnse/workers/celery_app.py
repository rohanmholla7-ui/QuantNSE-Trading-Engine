from celery import Celery
from celery.schedules import crontab

from quantnse.config import get_settings

settings = get_settings()
celery_app = Celery("quantnse", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.timezone = "Asia/Kolkata"
celery_app.conf.beat_schedule = {
    "preopen": {
        "task": "quantnse.workers.tasks.preopen_poll",
        "schedule": crontab(hour=9, minute=0),
    },
    "funnel": {
        "task": "quantnse.workers.tasks.run_morning_funnel",
        "schedule": crontab(hour=9, minute=30),
    },
    "square-off": {
        "task": "quantnse.workers.tasks.square_off_alert",
        "schedule": crontab(hour=15, minute=18),
    },
    "eod-fii": {
        "task": "quantnse.workers.tasks.ingest_fii_dii",
        "schedule": crontab(hour=17, minute=30),
    },
}
