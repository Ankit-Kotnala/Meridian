"""Document task payloads contain identifiers only and fail closed."""

from uuid import uuid4

import pytest

from careeros_worker.payloads import parse_job_payload


def test_valid_job_and_trace_ids_are_normalized() -> None:
    job_id = uuid4()

    parsed, trace_id = parse_job_payload(str(job_id), "A" * 32)

    assert parsed == job_id
    assert trace_id == "a" * 32


@pytest.mark.parametrize(
    ("job_id", "trace_id"),
    [
        ("not-a-uuid", "a" * 32),
        (str(uuid4()).upper(), "a" * 32),
        (str(uuid4()), "short"),
        (str(uuid4()), "z" * 32),
    ],
)
def test_invalid_or_noncanonical_payloads_are_rejected(job_id: str, trace_id: str) -> None:
    with pytest.raises(ValueError):
        parse_job_payload(job_id, trace_id)
