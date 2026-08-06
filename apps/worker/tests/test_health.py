"""Worker health task and container probe tests."""

from rezumi_worker.healthcheck import worker_is_responsive
from rezumi_worker.tasks import PING_TASK_NAME, ping


def test_ping_task_runs_without_a_broker() -> None:
    result = ping.run()

    assert result == {
        "status": "ok",
        "service": "rezumi-worker",
        "version": "0.1.0",
    }
    assert ping.name == PING_TASK_NAME


def test_container_probe_accepts_a_worker_reply() -> None:
    assert worker_is_responsive(lambda **_: [{"worker@example": {"ok": "pong"}}])


def test_container_probe_rejects_no_worker_replies() -> None:
    assert not worker_is_responsive(lambda **_: [])
