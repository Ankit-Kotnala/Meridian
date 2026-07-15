"""Container health probe for the Celery beat scheduler process."""

import os
import sys
from collections.abc import Callable
from pathlib import Path

# The scheduler owns this mode-0700, noexec tmpfs directory in the container.
DEFAULT_PID_FILE = Path("/tmp/careeros/celerybeat.pid")  # noqa: S108
DEFAULT_PROC_ROOT = Path("/proc")


def scheduler_is_responsive(
    pid_file: Path = DEFAULT_PID_FILE,
    proc_root: Path = DEFAULT_PROC_ROOT,
    signal_process: Callable[[int, int], None] = os.kill,
) -> bool:
    """Return whether the recorded PID is a live Celery beat process."""
    try:
        pid = int(pid_file.read_text(encoding="ascii").strip())
        if pid <= 1:
            return False

        signal_process(pid, 0)
        command_line = (proc_root / str(pid) / "cmdline").read_bytes().lower()
    except (OSError, ValueError):
        return False

    return b"celery" in command_line and b"beat" in command_line


def main() -> int:
    return 0 if scheduler_is_responsive() else 1


if __name__ == "__main__":
    sys.exit(main())
