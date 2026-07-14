"""Container health probe for broker-to-worker communication."""

import sys
from collections.abc import Callable
from typing import Any

from careeros_worker.app import celery_app


def worker_is_responsive(
    ping_control: Callable[..., list[dict[str, Any]] | None] | None = None,
) -> bool:
    """Return whether at least one worker responds through Celery remote control."""
    ping = ping_control or celery_app.control.ping
    replies = ping(timeout=3.0)
    return bool(replies)


def main() -> int:
    try:
        return 0 if worker_is_responsive() else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
