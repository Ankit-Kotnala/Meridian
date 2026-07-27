"""Worker liveness task adapter."""

from careeros_worker import __version__
from careeros_worker.app import celery_app
from careeros_worker.tasks.contracts import PingResult

PING_TASK_NAME = "careeros.worker.health.ping"


@celery_app.task(name=PING_TASK_NAME, ignore_result=False)  # type: ignore[untyped-decorator]
def ping() -> PingResult:
    """Return deterministic liveness metadata without touching infrastructure."""
    return {
        "status": "ok",
        "service": "careeros-worker",
        "version": __version__,
    }
