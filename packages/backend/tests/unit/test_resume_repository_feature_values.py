import pytest

from rezumi.modules.resume_health.domain.errors import ResumeStateConflict
from rezumi.modules.resume_health.infrastructure.repository import (
    _analysis_feature_values,
)


def _version_one_values() -> dict[str, int | bool]:
    return {
        "text_characters": 500,
        "page_count": 1,
        "image_only": False,
        "section_count": 1,
        "recognized_section_count": 1,
        "block_count": 3,
        "concise_block_count": 3,
        "bullet_count": 1,
        "action_bullet_count": 1,
        "outcome_bullet_count": 0,
        "duplicate_block_count": 0,
        "chronology_signal_count": 0,
        "warning_count": 0,
        "reading_order_violation_count": 0,
        "average_confidence_basis_points": 9_000,
    }


def test_feature_values_accept_historical_version_one_schema() -> None:
    values = _version_one_values()

    assert _analysis_feature_values(values, "resume-health-features/1") == values


def test_feature_values_accept_version_two_semantic_schema() -> None:
    values = _version_one_values() | {
        "semantic_entity_count": 1,
        "semantic_field_count": 2,
        "parsed_semantic_field_count": 2,
        "source_anchored_field_count": 2,
        "reviewed_semantic_field_count": 1,
        "date_field_count": 1,
        "precise_date_field_count": 1,
    }

    assert _analysis_feature_values(values, "resume-health-features/2") == values


@pytest.mark.parametrize(
    ("values", "version"),
    [
        (_version_one_values(), "resume-health-features/unknown"),
        (_version_one_values() | {"unexpected": 1}, "resume-health-features/1"),
        (
            {
                key: value
                for key, value in _version_one_values().items()
                if key != "text_characters"
            },
            "resume-health-features/1",
        ),
    ],
)
def test_feature_values_reject_unknown_or_drifted_schemas(
    values: dict[str, int | bool],
    version: str,
) -> None:
    with pytest.raises(ResumeStateConflict):
        _analysis_feature_values(values, version)
