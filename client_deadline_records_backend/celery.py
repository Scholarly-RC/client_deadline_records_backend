import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "client_deadline_records_backend.settings"
)

app = Celery("client_deadline_records_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.timezone = "Asia/Manila"
app.conf.enable_utc = False
