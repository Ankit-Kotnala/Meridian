"""Broker-neutral publisher implementation using Celery without worker imports."""

import asyncio
from dataclasses import dataclass
from uuid import UUID

from celery import Celery
from kombu.exceptions import KombuError

from careeros.modules.resume_health.domain.errors import RetryableProcessingFailure


@dataclass(frozen=True, slots=True)
class CeleryPublisherOptions:
    broker_url: str
    queue: str = "resume-health"
    publish_timeout_seconds: float = 5.0


class CeleryJobPublisher:
    def __init__(self, options: CeleryPublisherOptions) -> None:
        self._options = options
        self._app = Celery("careeros-resume-publisher", broker=options.broker_url)
        self._app.conf.update(
            accept_content=["json"],
            task_serializer="json",
            task_publish_retry=True,
            task_publish_retry_policy={
                "max_retries": 2,
                "interval_start": 0,
                "interval_step": 0.2,
                "interval_max": 1,
            },
        )

    async def publish(self, task_name: str, job_id: UUID, trace_id: str) -> None:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._app.send_task,
                    task_name,
                    kwargs={"job_id": str(job_id), "trace_id": trace_id[:64]},
                    queue=self._options.queue,
                    serializer="json",
                ),
                self._options.publish_timeout_seconds,
            )
        except (TimeoutError, KombuError, OSError) as exc:
            raise RetryableProcessingFailure("task_publish_failed") from exc
