"""Outbox publishing remains allowlisted and identifier-only."""

import asyncio
from typing import Any, cast
from unittest.mock import Mock
from uuid import uuid4

import pytest
from careeros.modules.career_record.application import PROCESS_EVIDENCE_ATTACHMENT_TASK
from careeros.modules.resume_health.application import PROCESS_RESUME_TASK
from celery import Celery

from careeros_worker.publisher import CeleryAnalyticsPublisher, CeleryJobPublisher
from careeros_worker.task_names import PROCESS_CAREER_ANALYTICS_REFRESH_TASK


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


@pytest.mark.parametrize(
    ("task_name", "queue"),
    [
        (PROCESS_RESUME_TASK, "resume-health"),
        (PROCESS_EVIDENCE_ATTACHMENT_TASK, "career-record"),
    ],
)
def test_publisher_routes_each_allowlisted_task_to_its_private_queue(
    task_name: str, queue: str
) -> None:
    application = cast(Celery, Mock())
    job_id = uuid4()

    asyncio.run(CeleryJobPublisher(application).publish(task_name, job_id, "a" * 32))

    cast(Any, application).send_task.assert_called_once_with(
        task_name,
        kwargs={"job_id": str(job_id), "trace_id": "a" * 32},
        queue=queue,
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


def test_analytics_publisher_has_one_allowlisted_identifier_only_shape() -> None:
    application = cast(Celery, Mock())
    job_id = uuid4()

    asyncio.run(CeleryAnalyticsPublisher(application).publish(job_id))

    cast(Any, application).send_task.assert_called_once_with(
        PROCESS_CAREER_ANALYTICS_REFRESH_TASK,
        kwargs={"job_id": str(job_id)},
        queue="default",
        serializer="json",
    )
