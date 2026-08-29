"""Regression floor for the resume semantic parser accuracy harness.

This is the enforced number, not a promise of universal accuracy — see
`rezumi.development.eval_resume_parser`'s module docstring for scope. The
golden corpus is a starting set (10 cases as of writing); extend it as new
real-world failure modes are found, and raise the floor as it improves.
"""

from __future__ import annotations

import pytest

from rezumi.development.eval_resume_parser import run_eval
from rezumi.development.resume_parser_golden_corpus import GOLDEN_CORPUS

_MIN_PRECISION = 0.95
_MIN_RECALL = 0.95


@pytest.mark.asyncio
async def test_semantic_parser_meets_the_measured_accuracy_floor() -> None:
    report = await run_eval(GOLDEN_CORPUS)
    precision, recall = report.overall()

    assert precision is not None and recall is not None, report.render()
    assert precision >= _MIN_PRECISION, (
        f"Precision regressed to {precision:.1%} (floor {_MIN_PRECISION:.0%}).\n"
        + report.render()
    )
    assert recall >= _MIN_RECALL, (
        f"Recall regressed to {recall:.1%} (floor {_MIN_RECALL:.0%}).\n" + report.render()
    )
