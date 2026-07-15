"""Deterministic, fixed-point Resume Health v1 scoring engine."""

import json
from dataclasses import asdict, dataclass
from hashlib import sha256

ENGINE_VERSION = "resume-health/1.0.0"
CONFIGURATION_VERSION = "resume-health-default/1"
FEATURE_SCHEMA_VERSION = "resume-health-features/1"


@dataclass(frozen=True, slots=True)
class ResumeHealthFeatures:
    text_characters: int
    page_count: int
    image_only: bool
    section_count: int
    recognized_section_count: int
    block_count: int
    concise_block_count: int
    bullet_count: int
    action_bullet_count: int
    outcome_bullet_count: int
    duplicate_block_count: int
    chronology_signal_count: int
    warning_count: int
    reading_order_violation_count: int
    average_confidence_basis_points: int

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if name == "image_only":
                continue
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.average_confidence_basis_points > 10_000:
            raise ValueError("average confidence must not exceed 10000")


@dataclass(frozen=True, slots=True)
class ComponentResult:
    code: str
    weight_basis_points: int
    score_basis_points: int
    contribution_basis_points: int
    explanation: str


@dataclass(frozen=True, slots=True)
class FeatureContributionResult:
    component_code: str
    feature_code: str
    feature_value_basis_points: int
    weight_basis_points: int
    contribution_basis_points: int


@dataclass(frozen=True, slots=True)
class FindingResult:
    code: str
    severity: str
    component_code: str
    message: str
    quick_win: bool


@dataclass(frozen=True, slots=True)
class ResumeHealthScore:
    engine_version: str
    configuration_version: str
    feature_schema_version: str
    feature_values: dict[str, int | bool]
    feature_set_hash: bytes
    raw_score_basis_points: int | None
    display_score: int | None
    components: tuple[ComponentResult, ...]
    feature_contributions: tuple[FeatureContributionResult, ...]
    findings: tuple[FindingResult, ...]
    insufficient_reason: str | None


_TOP_WEIGHTS = {
    "machine_readability": 2_500,
    "recruiter_clarity": 2_000,
    "content_impact": 2_000,
    "achievement_strength": 1_500,
    "structure": 1_000,
    "consistency_truth": 1_000,
}


def score_resume_health(features: ResumeHealthFeatures) -> ResumeHealthScore:
    """Return a reproducible score; unreliable input produces no number."""
    feature_hash = _feature_hash(features)
    if features.image_only:
        return _insufficient(features, feature_hash, "image_only_document")
    if features.text_characters < 200 or features.block_count < 3:
        return _insufficient(features, feature_hash, "insufficient_extractable_text")

    recognized_ratio = _ratio(features.recognized_section_count, features.section_count)
    concise_ratio = _ratio(features.concise_block_count, features.block_count)
    action_ratio = _ratio(features.action_bullet_count, features.bullet_count)
    outcome_ratio = _ratio(features.outcome_bullet_count, features.bullet_count)
    duplicate_score = _penalty(features.duplicate_block_count, 2_000)
    warning_score = _penalty(features.warning_count, 1_500)
    reading_order_score = _penalty(features.reading_order_violation_count, 2_500)
    section_breadth = min(10_000, features.recognized_section_count * 2_500)
    chronology = min(10_000, features.chronology_signal_count * 2_000)
    page_fit = (
        10_000
        if 1 <= features.page_count <= 3
        else max(2_000, 10_000 - 2_000 * abs(features.page_count - 2))
    )
    searchable = min(10_000, features.text_characters * 10)
    if features.bullet_count == 0:
        # Paragraph-led formats are valid, but action/outcome structure is unknown.
        action_ratio = 5_000
        outcome_ratio = 5_000

    component_inputs = {
        "machine_readability": (
            ("searchable_text", searchable, 3_000),
            ("parser_confidence", features.average_confidence_basis_points, 3_000),
            ("reading_order_integrity", reading_order_score, 2_000),
            ("recognized_section_ratio", recognized_ratio, 2_000),
        ),
        "recruiter_clarity": (
            ("recognized_section_ratio", recognized_ratio, 3_000),
            ("concise_block_ratio", concise_ratio, 3_000),
            ("section_breadth", section_breadth, 2_000),
            ("chronology_coverage", chronology, 2_000),
        ),
        "content_impact": (
            ("action_bullet_ratio", action_ratio, 3_500),
            ("outcome_bullet_ratio", outcome_ratio, 3_000),
            ("duplicate_content_integrity", duplicate_score, 2_000),
            ("concise_block_ratio", concise_ratio, 1_500),
        ),
        "achievement_strength": (
            ("outcome_bullet_ratio", outcome_ratio, 4_500),
            ("action_bullet_ratio", action_ratio, 3_500),
            ("duplicate_content_integrity", duplicate_score, 2_000),
        ),
        "structure": (
            ("section_breadth", section_breadth, 3_500),
            ("recognized_section_ratio", recognized_ratio, 2_500),
            ("page_fit", page_fit, 2_000),
            ("concise_block_ratio", concise_ratio, 2_000),
        ),
        "consistency_truth": (
            ("parser_confidence", features.average_confidence_basis_points, 3_500),
            ("parser_warning_integrity", warning_score, 3_000),
            ("duplicate_content_integrity", duplicate_score, 2_000),
            ("chronology_coverage", chronology, 1_500),
        ),
    }
    component_values = {
        code: _weighted(tuple((value, weight) for _, value, weight in inputs))
        for code, inputs in component_inputs.items()
    }

    explanations = {
        "machine_readability": (
            "Measures extractable text, parser confidence, reading order, and section recognition."
        ),
        "recruiter_clarity": (
            "Measures observable organization, concise blocks, and readable chronology signals."
        ),
        "content_impact": (
            "Measures action/outcome structure and repetition without judging hiring value."
        ),
        "achievement_strength": (
            "Measures observable action-and-outcome phrasing; it does not verify the claims."
        ),
        "structure": "Measures recognizable sections, hierarchy, length, and scan-friendly blocks.",
        "consistency_truth": (
            "Measures parser confidence and detectable consistency warnings, not background "
            "verification."
        ),
    }
    components = tuple(
        ComponentResult(
            code=code,
            weight_basis_points=weight,
            score_basis_points=component_values[code],
            contribution_basis_points=_multiply(component_values[code], weight),
            explanation=explanations[code],
        )
        for code, weight in _TOP_WEIGHTS.items()
    )
    feature_contributions = tuple(
        contribution
        for component_code, inputs in component_inputs.items()
        for contribution in _allocate_feature_contributions(
            component_code, inputs, component_values[component_code]
        )
    )
    raw = sum(component.contribution_basis_points for component in components)
    findings: list[FindingResult] = []
    if features.reading_order_violation_count:
        findings.append(
            FindingResult(
                "reading_order_warning",
                "warning",
                "machine_readability",
                "Review the extracted reading order before relying on the analysis.",
                True,
            )
        )
    if recognized_ratio < 6_000:
        findings.append(
            FindingResult(
                "section_headings_unclear",
                "warning",
                "structure",
                "Use clear section headings so content can be reviewed in a predictable order.",
                True,
            )
        )
    if features.bullet_count and action_ratio < 5_000:
        findings.append(
            FindingResult(
                "few_action_led_bullets",
                "info",
                "content_impact",
                "Consider beginning more bullets with a clear action where that preserves "
                "the facts.",
                True,
            )
        )
    if features.bullet_count and outcome_ratio < 4_000:
        findings.append(
            FindingResult(
                "outcome_context_limited",
                "info",
                "achievement_strength",
                "Add outcome context only where you can support and confirm it.",
                False,
            )
        )
    if features.warning_count:
        findings.append(
            FindingResult(
                "parser_warnings_present",
                "warning",
                "consistency_truth",
                "Resolve parser warnings and confirm uncertain fields before reuse.",
                False,
            )
        )
    return ResumeHealthScore(
        engine_version=ENGINE_VERSION,
        configuration_version=CONFIGURATION_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        feature_values=_feature_values(features),
        feature_set_hash=feature_hash,
        raw_score_basis_points=raw,
        display_score=(raw + 50) // 100,
        components=components,
        feature_contributions=feature_contributions,
        findings=tuple(findings),
        insufficient_reason=None,
    )


def _insufficient(
    features: ResumeHealthFeatures, feature_hash: bytes, reason: str
) -> ResumeHealthScore:
    return ResumeHealthScore(
        engine_version=ENGINE_VERSION,
        configuration_version=CONFIGURATION_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        feature_values=_feature_values(features),
        feature_set_hash=feature_hash,
        raw_score_basis_points=None,
        display_score=None,
        components=(),
        feature_contributions=(),
        findings=(
            FindingResult(
                reason,
                "warning",
                "machine_readability",
                "There is not enough reliable extracted text to calculate a Resume Health score.",
                False,
            ),
        ),
        insufficient_reason=reason,
    )


def _ratio(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return min(10_000, (numerator * 10_000 + denominator // 2) // denominator)


def _penalty(count: int, each: int) -> int:
    return max(0, 10_000 - count * each)


def _weighted(values: tuple[tuple[int, int], ...]) -> int:
    if sum(weight for _, weight in values) != 10_000:
        raise ValueError("sub-feature weights must total 10000")
    return min(10_000, max(0, (sum(value * weight for value, weight in values) + 5_000) // 10_000))


def _multiply(value: int, weight: int) -> int:
    return (value * weight + 5_000) // 10_000


def _allocate_feature_contributions(
    component_code: str,
    inputs: tuple[tuple[str, int, int], ...],
    component_score: int,
) -> tuple[FeatureContributionResult, ...]:
    products = [value * weight for _, value, weight in inputs]
    allocated = [product // 10_000 for product in products]
    remaining = component_score - sum(allocated)
    order = sorted(range(len(inputs)), key=lambda index: (-(products[index] % 10_000), index))
    for index in order[:remaining]:
        allocated[index] += 1
    return tuple(
        FeatureContributionResult(
            component_code=component_code,
            feature_code=feature_code,
            feature_value_basis_points=value,
            weight_basis_points=weight,
            contribution_basis_points=allocated[index],
        )
        for index, (feature_code, value, weight) in enumerate(inputs)
    )


def _feature_values(features: ResumeHealthFeatures) -> dict[str, int | bool]:
    return {
        "text_characters": features.text_characters,
        "page_count": features.page_count,
        "image_only": features.image_only,
        "section_count": features.section_count,
        "recognized_section_count": features.recognized_section_count,
        "block_count": features.block_count,
        "concise_block_count": features.concise_block_count,
        "bullet_count": features.bullet_count,
        "action_bullet_count": features.action_bullet_count,
        "outcome_bullet_count": features.outcome_bullet_count,
        "duplicate_block_count": features.duplicate_block_count,
        "chronology_signal_count": features.chronology_signal_count,
        "warning_count": features.warning_count,
        "reading_order_violation_count": features.reading_order_violation_count,
        "average_confidence_basis_points": features.average_confidence_basis_points,
    }


def _feature_hash(features: ResumeHealthFeatures) -> bytes:
    serialized = json.dumps(asdict(features), sort_keys=True, separators=(",", ":")).encode()
    return sha256(serialized).digest()
