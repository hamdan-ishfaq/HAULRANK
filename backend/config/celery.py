"""Celery app — optional continuous compliance beat.

Broker uses REDIS_URL when set. Without Redis, skip worker/beat and use:
  python manage.py poll_compliance
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("haulrank")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
