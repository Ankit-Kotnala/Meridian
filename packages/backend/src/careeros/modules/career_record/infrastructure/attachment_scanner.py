"""Fail-closed ClamAV INSTREAM adapter for evidence attachments."""

import asyncio
import struct
from dataclasses import dataclass
from pathlib import Path

from careeros.modules.career_record.application.attachment_workflow import (
    MalwareScanResult,
    ScanVerdict,
)


@dataclass(frozen=True, slots=True)
class AttachmentClamAvOptions:
    host: str = "localhost"
    port: int = 3310
    timeout_seconds: float = 30.0
    chunk_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        if not self.host or not 1 <= self.port <= 65_535:
            raise ValueError("invalid attachment ClamAV endpoint")
        if self.timeout_seconds <= 0 or not 1 <= self.chunk_bytes <= 1024 * 1024:
            raise ValueError("invalid attachment ClamAV resource bounds")


class AttachmentClamAvScanner:
    def __init__(self, options: AttachmentClamAvOptions) -> None:
        self._options = options

    async def scan(self, path: Path) -> MalwareScanResult:
        try:
            return await asyncio.wait_for(self._scan(path), self._options.timeout_seconds)
        except (TimeoutError, OSError, asyncio.IncompleteReadError):
            return MalwareScanResult(ScanVerdict.UNAVAILABLE)

    async def _scan(self, path: Path) -> MalwareScanResult:
        reader, writer = await asyncio.open_connection(self._options.host, self._options.port)
        try:
            writer.write(b"zINSTREAM\0")
            with path.open("rb") as source:
                while chunk := source.read(self._options.chunk_bytes):
                    writer.write(struct.pack("!I", len(chunk)))
                    writer.write(chunk)
                    await writer.drain()
            writer.write(struct.pack("!I", 0))
            await writer.drain()
            response = (
                (await reader.readuntil(b"\0")).rstrip(b"\0").decode("utf-8", errors="replace")
            )
        finally:
            writer.close()
            await writer.wait_closed()
        if response.endswith(" OK"):
            return MalwareScanResult(ScanVerdict.CLEAN)
        if response.endswith(" FOUND"):
            return MalwareScanResult(ScanVerdict.INFECTED)
        return MalwareScanResult(ScanVerdict.UNAVAILABLE)
