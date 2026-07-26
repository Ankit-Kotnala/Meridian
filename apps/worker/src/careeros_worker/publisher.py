"""Celery adapter for allowlisted identifier-only processing outboxes."""

import asyncio
from uuid import UUID

from careeros.modules.career_record.application import PROCESS_EVIDENCE_ATTACHMENT_TASK
from careeros.modules.resume_health.application import PROCESS_RESUME_TASK
from celery import Celery  # type: ignore[import-untyped,unused-ignore]

from careeros_worker.payloads import parse_identifier_payload, parse_job_payload
from careeros_worker.task_names import PROCESS_CAREER_ANALYTICS_REFRESH_TASK


class CeleryJobPublisher:
    """Publish only allowlisted durable IDs; document bytes never enter the broker."""

    def __init__(self, application: Celery) -> None:
        self._application = application

    async def publish(self, task_name: str, job_id: UUID, trace_id: str) -> None:
        queues = {
            PROCESS_RESUME_TASK: "resume-health",
            PROCESS_EVIDENCE_ATTACHMENT_TASK: "career-record",
        }
        queue = queues.get(task_name)
        if queue is None:
            raise ValueError("outbox task name is not allowlisted")
        canonical_job_id, canonical_trace_id = parse_job_payload(str(job_id), trace_id)
        await asyncio.to_thread(
            self._application.send_task,
            task_name,
            kwargs={
                "job_id": str(canonical_job_id),
                "trace_id": canonical_trace_id,
            },
            queue=queue,
            serializer="json",
        )


class CeleryAnalyticsPublisher:
    """Publish the single allowlisted analytics task with one durable UUID."""

    def __init__(self, application: Celery) -> None:
        self._application = application

    async def publish(self, job_id: UUID) -> None:
        canonical_job_id = parse_identifier_payload(str(job_id))
        await asyncio.to_thread(
            self._application.send_task,
            PROCESS_CAREER_ANALYTICS_REFRESH_TASK,
            kwargs={"job_id": str(canonical_job_id)},
            queue="default",
            serializer="json",
        )
