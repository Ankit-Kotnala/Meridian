"""Phase 0 worker tasks."""

from typing import TypedDict

from careeros_worker import __version__
from careeros_worker.app import celery_app

PING_TASK_NAME = "careeros.worker.health.ping"


class PingResult(TypedDict):
    status: str
    service: str
    version: str


@celery_app.task(name=PING_TASK_NAME, ignore_result=False)  # type: ignore[untyped-decorator]
def ping() -> PingResult:
    """Return deterministic liveness metadata without touching infrastructure."""
    return {
        "status": "ok",
        "service": "careeros-worker",
        "version": __version__,
    }
