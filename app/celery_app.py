import os

from celery import Celery


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)


celery_app = Celery(
    "video_converter",
    broker=REDIS_URL,
    backend=REDIS_URL,
)


celery_app.conf.update(
    result_expires=86400,

    task_track_started=True,

    task_acks_late=True,

    worker_prefetch_multiplier=1,

    broker_transport_options={
        "visibility_timeout": 24 * 60 * 60,
    },

    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
import app.tasks
