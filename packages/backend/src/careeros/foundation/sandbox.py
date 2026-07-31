"""Small process-isolation primitives for hostile document parsers."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_FORBIDDEN_AUDIT_EVENTS = frozenset(
    {
        "os.posix_spawn",
        "os.spawn",
        "os.system",
        "socket.__new__",
        "socket.bind",
        "socket.connect",
        "socket.getaddrinfo",
        "subprocess.Popen",
    }
)


def sanitized_parser_environment(workspace: Path) -> dict[str, str]:
    """Return a minimal child environment containing no application credentials."""

    resolved = workspace.resolve(strict=True)
    environment = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "TEMP": str(resolved),
        "TMP": str(resolved),
        "TMPDIR": str(resolved),
    }
    for name in ("SYSTEMROOT", "WINDIR", "COMSPEC"):
        value = os.environ.get(name)
        if value is not None:
            environment[name] = value
    return environment


def install_parser_egress_guard() -> None:
    """Deny standard-library network and child-process creation in a parser child."""

    def reject_egress(event: str, args: tuple[Any, ...]) -> None:
        del args
        if event in _FORBIDDEN_AUDIT_EVENTS:
            raise PermissionError("parser egress is disabled")

    sys.addaudithook(reject_egress)
