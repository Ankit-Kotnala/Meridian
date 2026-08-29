"""Golden and boundary tests for fixed-point Resume Health v2."""

from rezumi.modules.resume_health.domain.scoring import (
    CONFIGURATION_VERSION,
    ENGINE_VERSION,
    FEATURE_SCHEMA_VERSION,
    ResumeHealthFeatures,
    score_resume_health,
)


def _features(**overrides: object) -> ResumeHealthFeatures:
    values: dict[str, object] = {
        "text_characters": 2_000,
        "page_count": 2,
        "image_only": False,
        "section_count": 4,
        "recognized_section_count": 4,
        "block_count": 10,
        "concise_block_count": 10,
        "bullet_count": 4,
        "action_bullet_count": 4,
        "outcome_bullet_count": 4,
        "duplicate_block_count": 0,
        "chronology_signal_count": 5,
        "warning_count": 0,
        "reading_order_violation_count": 0,
        "average_confidence_basis_points": 10_000,
        "semantic_entity_count": 4,
        "semantic_field_count": 12,
        "parsed_semantic_field_count": 12,
        "source_anchored_field_count": 12,
        "reviewed_semantic_field_count": 12,
        "date_field_count": 4,
        "precise_date_field_count": 4,
    }
    values.update(overrides)
    return ResumeHealthFeatures(**values)  # type: ignore[arg-type]


def test_perfect_golden_score_is_exact_and_explainable() -> None:
    result = score_resume_health(_features())

    assert result.engine_version == ENGINE_VERSION
    assert result.configuration_version == CONFIGURATION_VERSION
    assert result.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert result.feature_values == {
        "text_characters": 2_000,
        "page_count": 2,
        "image_only": False,
        "section_count": 4,
        "recognized_section_count": 4,
        "block_count": 10,
        "concise_block_count": 10,
        "bullet_count": 4,
        "action_bullet_count": 4,
        "outcome_bullet_count": 4,
        "duplicate_block_count": 0,
        "chronology_signal_count": 5,
        "warning_count": 0,
        "reading_order_violation_count": 0,
        "average_confidence_basis_points": 10_000,
        "semantic_entity_count": 4,
        "semantic_field_count": 12,
        "parsed_semantic_field_count": 12,
        "source_anchored_field_count": 12,
        "reviewed_semantic_field_count": 12,
        "date_field_count": 4,
        "precise_date_field_count": 4,
    }
    assert result.raw_score_basis_points == 10_000
    assert result.display_score == 100
    assert [item.weight_basis_points for item in result.components] == [
        2_500,
        2_000,
        2_000,
        1_500,
        1_000,
        1_000,
    ]
    assert sum(item.contribution_basis_points for item in result.components) == 10_000
    for component in result.components:
        assert (
            sum(
                item.contribution_basis_points
                for item in result.feature_contributions
                if item.component_code == component.code
            )
            == component.score_basis_points
        )


def test_nontrivial_golden_score_is_exact() -> None:
    result = score_resume_health(
        _features(
            text_characters=612,
            page_count=1,
            section_count=4,
            recognized_section_count=4,
            block_count=14,
            concise_block_count=14,
            bullet_count=3,
            action_bullet_count=3,
            outcome_bullet_count=1,
            chronology_signal_count=5,
            average_confidence_basis_points=9_000,
        )
    )

    assert [component.score_basis_points for component in result.components] == [
        8_780,
        10_000,
        8_000,
        7_000,
        10_000,
        9_800,
    ]
    assert [component.contribution_basis_points for component in result.components] == [
        2_195,
        2_000,
        1_600,
        1_050,
        1_000,
        980,
    ]
    assert result.raw_score_basis_points == 8_825
    assert result.display_score == 88
    assert [finding.code for finding in result.findings] == ["outcome_context_limited"]
    assert [
        (
            item.component_code,
            item.feature_code,
            item.feature_value_basis_points,
            item.weight_basis_points,
            item.contribution_basis_points,
        )
        for item in result.feature_contributions[:4]
    ] == [
        ("machine_readability", "searchable_text", 6_120, 2_500, 1_530),
        ("machine_readability", "parser_confidence", 9_000, 2_500, 2_250),
        ("machine_readability", "reading_order_integrity", 10_000, 1_500, 1_500),
        ("machine_readability", "recognized_section_ratio", 10_000, 1_500, 1_500),
    ]


def test_score_is_deterministic_bounded_and_has_actionable_findings() -> None:
    features = _features(
        recognized_section_count=1,
        action_bullet_count=0,
        outcome_bullet_count=0,
        warning_count=2,
        reading_order_violation_count=1,
        average_confidence_basis_points=6_500,
    )
    first = score_resume_health(features)
    second = score_resume_health(features)

    assert first == second
    assert first.raw_score_basis_points is not None
    assert 0 <= first.raw_score_basis_points <= 10_000
    assert 0 <= first.display_score <= 100  # type: ignore[operator]
    assert {item.code for item in first.findings} >= {
        "reading_order_warning",
        "section_headings_unclear",
        "few_action_led_bullets",
        "outcome_context_limited",
        "parser_warnings_present",
    }


def test_image_only_and_sparse_documents_return_no_deceptive_zero() -> None:
    for features in (
        _features(image_only=True),
        _features(text_characters=100),
        _features(
            block_count=2,
            concise_block_count=2,
            bullet_count=0,
            action_bullet_count=0,
            outcome_bullet_count=0,
            chronology_signal_count=2,
        ),
    ):
        result = score_resume_health(features)
        assert result.raw_score_basis_points is None
        assert result.display_score is None
        assert result.components == ()
        assert result.feature_contributions == ()
        assert result.feature_schema_version == FEATURE_SCHEMA_VERSION
        assert result.feature_values["image_only"] == features.image_only
        assert result.insufficient_reason is not None


def test_paragraph_led_resume_does_not_divide_by_zero() -> None:
    result = score_resume_health(
        _features(bullet_count=0, action_bullet_count=0, outcome_bullet_count=0)
    )
    assert result.raw_score_basis_points is not None
    assert 0 <= result.raw_score_basis_points <= 10_000


def test_all_scoring_outputs_remain_bounded_at_feature_extremes() -> None:
    for features in (
        _features(
            section_count=0,
            recognized_section_count=0,
            concise_block_count=0,
            bullet_count=0,
            action_bullet_count=0,
            outcome_bullet_count=0,
            duplicate_block_count=10,
            chronology_signal_count=0,
            warning_count=100,
            reading_order_violation_count=100,
            average_confidence_basis_points=0,
        ),
        _features(
            text_characters=10_000_000,
            page_count=10_000,
            section_count=1,
            recognized_section_count=1,
            concise_block_count=10,
            bullet_count=10,
            action_bullet_count=10,
            outcome_bullet_count=10,
            chronology_signal_count=10,
        ),
    ):
        result = score_resume_health(features)
        assert result.raw_score_basis_points is not None
        assert 0 <= result.raw_score_basis_points <= 10_000
        assert result.display_score is not None
        assert 0 <= result.display_score <= 100
        for component in result.components:
            assert 0 <= component.score_basis_points <= 10_000
            assert 0 <= component.contribution_basis_points <= component.weight_basis_points
