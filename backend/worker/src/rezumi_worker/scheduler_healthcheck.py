"""Container health probe for the Celery beat scheduler process."""

import os
import sys
from collections.abc import Callable
from pathlib import Path

# The scheduler owns this mode-0700, noexec tmpfs directory in the container.
DEFAULT_PID_FILE = Path("/tmp/rezumi/celerybeat.pid")  # noqa: S108
DEFAULT_PROC_ROOT = Path("/proc")


def scheduler_is_responsive(
    pid_file: Path = DEFAULT_PID_FILE,
    proc_root: Path = DEFAULT_PROC_ROOT,
    signal_process: Callable[[int, int], None] = os.kill,
) -> bool:
    """Return whether Celery beat is running in this container.

    With Docker's ``init: true`` enabled, Celery's pidfile can contain a PID
    that is not visible from the healthcheck process namespace. In that case,
    the container init process (PID 1) is the reliable process marker because
    it is started with the Celery beat command as its argv.
    """
    try:
        init_command_line = (proc_root / "1" / "cmdline").read_bytes().lower()
    except OSError:
        init_command_line = b""
    if b"celery" in init_command_line and b"beat" in init_command_line:
        return True

    try:
        pid = int(pid_file.read_text(encoding="ascii").strip())
        if pid <= 1:
            return False

        signal_process(pid, 0)
        command_line = (proc_root / str(pid) / "cmdline").read_bytes().lower()
    except (OSError, ValueError):
        try:
            command_line = (proc_root / "1" / "cmdline").read_bytes().lower()
        except OSError:
            return False

    return b"celery" in command_line and b"beat" in command_line


def main() -> int:
    return 0 if scheduler_is_responsive() else 1


if __name__ == "__main__":
    sys.exit(main())
