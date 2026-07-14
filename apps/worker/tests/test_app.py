"""Celery configuration tests that do not connect to Redis."""

from careeros_worker.app import create_celery_app
from careeros_worker.config import WorkerSettings


def test_celery_uses_json_and_safe_delivery_defaults() -> None:
    settings = WorkerSettings.model_validate({"environment": "test"})
    app = create_celery_app(settings)

    assert app.conf.accept_content == ["json"]
    assert app.conf.task_serializer == "json"
    assert app.conf.result_serializer == "json"
    assert app.conf.task_acks_late is True
    assert app.conf.task_reject_on_worker_lost is True
    assert app.conf.worker_prefetch_multiplier == 1
    assert app.conf.task_soft_time_limit == 270
    assert app.conf.task_time_limit == 300
    assert app.conf.task_ignore_result is True


def test_task_retry_count_is_bounded() -> None:
    settings = WorkerSettings.model_validate({"environment": "test", "task_max_retries": 4})
    app = create_celery_app(settings)

    assert app.Task.max_retries == 4
