"""Outbox publishing remains allowlisted and identifier-only."""

import asyncio
from typing import Any, cast
from unittest.mock import Mock
from uuid import uuid4

from careeros.modules.resume_health.application import PROCESS_RESUME_TASK
from celery import Celery

from careeros_worker.publisher import CeleryJobPublisher


def test_publisher_sends_only_job_and_trace_identifiers() -> None:
    application = cast(Celery, Mock())
    publisher = CeleryJobPublisher(application)
    job_id = uuid4()

    asyncio.run(publisher.publish(PROCESS_RESUME_TASK, job_id, "1" * 32))

    sender = cast(Any, application).send_task
    sender.assert_called_once_with(
        PROCESS_RESUME_TASK,
        kwargs={"job_id": str(job_id), "trace_id": "1" * 32},
        queue="resume-health",
        serializer="json",
    )


def test_publisher_rejects_a_task_name_from_tampered_outbox_data() -> None:
    application = cast(Celery, Mock())
    publisher = CeleryJobPublisher(application)

    try:
        asyncio.run(publisher.publish("careeros.attacker.task", uuid4(), "2" * 32))
    except ValueError as exc:
        assert str(exc) == "outbox task name is not allowlisted"
    else:
        raise AssertionError("tampered task name was accepted")

    cast(Any, application).send_task.assert_not_called()
