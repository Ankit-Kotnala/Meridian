"""Celery adapter for the resume-processing outbox publisher port."""

import asyncio
from uuid import UUID

from careeros.modules.resume_health.application import PROCESS_RESUME_TASK
from celery import Celery

from careeros_worker.payloads import parse_job_payload


class CeleryJobPublisher:
    """Publish only allowlisted durable IDs; document bytes never enter the broker."""

    def __init__(self, application: Celery) -> None:
        self._application = application

    async def publish(self, task_name: str, job_id: UUID, trace_id: str) -> None:
        if task_name != PROCESS_RESUME_TASK:
            raise ValueError("outbox task name is not allowlisted")
        canonical_job_id, canonical_trace_id = parse_job_payload(str(job_id), trace_id)
        await asyncio.to_thread(
            self._application.send_task,
            task_name,
            kwargs={
                "job_id": str(canonical_job_id),
                "trace_id": canonical_trace_id,
            },
            queue="resume-health",
            serializer="json",
        )
