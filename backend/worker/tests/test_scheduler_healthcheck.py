"""Celery beat scheduler health probe tests."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from rezumi_worker.scheduler_healthcheck import scheduler_is_responsive


def write_process(tmp_path: Path, *, pid_text: str, command_line: bytes) -> tuple[Path, Path]:
    pid_file = tmp_path / "celerybeat.pid"
    pid_file.write_text(pid_text, encoding="ascii")
    proc_root = tmp_path / "proc"
    process_dir = proc_root / pid_text.strip()
    process_dir.mkdir(parents=True)
    (process_dir / "cmdline").write_bytes(command_line)
    return pid_file, proc_root


def test_scheduler_probe_accepts_a_live_celery_beat_process(tmp_path: Path) -> None:
    pid_file, proc_root = write_process(
        tmp_path,
        pid_text="42",
        command_line=b"python\0celery\0--app\0rezumi_worker.app:celery_app\0beat\0",
    )
    signal_process = Mock()

    assert scheduler_is_responsive(pid_file, proc_root, signal_process)
    signal_process.assert_called_once_with(42, 0)


@pytest.mark.parametrize("pid_text", ["", "not-a-pid", "0", "1", "-4"])
def test_scheduler_probe_rejects_an_invalid_pid(tmp_path: Path, pid_text: str) -> None:
    pid_file = tmp_path / "celerybeat.pid"
    pid_file.write_text(pid_text, encoding="ascii")

    assert not scheduler_is_responsive(pid_file, tmp_path / "proc", Mock())


def test_scheduler_probe_rejects_a_missing_process(tmp_path: Path) -> None:
    pid_file, proc_root = write_process(
        tmp_path,
        pid_text="42",
        command_line=b"python\0celery\0beat\0",
    )
    signal_process = Mock(side_effect=ProcessLookupError)

    assert not scheduler_is_responsive(pid_file, proc_root, signal_process)


def test_scheduler_probe_rejects_the_wrong_process(tmp_path: Path) -> None:
    pid_file, proc_root = write_process(
        tmp_path,
        pid_text="42",
        command_line=b"python\0unrelated-service\0",
    )

    assert not scheduler_is_responsive(pid_file, proc_root, Mock())


def test_scheduler_probe_falls_back_to_container_init_process(tmp_path: Path) -> None:
    pid_file = tmp_path / "celerybeat.pid"
    pid_file.write_text("7", encoding="ascii")
    proc_root = tmp_path / "proc"
    init_process = proc_root / "1"
    init_process.mkdir(parents=True)
    (init_process / "cmdline").write_bytes(
        b"/sbin/docker-init\0--\0celery\0beat\0"
    )
    signal_process = Mock(side_effect=ProcessLookupError)

    assert scheduler_is_responsive(pid_file, proc_root, signal_process)
