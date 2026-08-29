"""Worker liveness task adapter."""

from rezumi_worker import __version__
from rezumi_worker.app import celery_app
from rezumi_worker.tasks.contracts import PingResult

PING_TASK_NAME = "rezumi.worker.health.ping"


@celery_app.task(name=PING_TASK_NAME, ignore_result=False)  # type: ignore[untyped-decorator]
def ping() -> PingResult:
    """Return deterministic liveness metadata without touching infrastructure."""
    return {
        "status": "ok",
        "service": "rezumi-worker",
        "version": __version__,
    }
