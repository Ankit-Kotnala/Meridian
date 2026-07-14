"""Validation for the deliberately narrow document-task payload."""

import re
from uuid import UUID

_TRACE_ID = re.compile(r"^[0-9a-fA-F]{32}$")


def parse_job_payload(job_id: str, trace_id: str) -> tuple[UUID, str]:
    """Accept one durable job UUID and one W3C-compatible trace identifier."""
    try:
        parsed_job_id = UUID(job_id)
    except (ValueError, AttributeError) as exc:
        raise ValueError("job_id must be a UUID") from exc
    if str(parsed_job_id) != job_id:
        raise ValueError("job_id must use canonical UUID form")
    if not _TRACE_ID.fullmatch(trace_id):
        raise ValueError("trace_id must contain exactly 32 hexadecimal characters")
    return parsed_job_id, trace_id.casefold()
