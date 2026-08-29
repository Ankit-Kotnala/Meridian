"""Measured accuracy harness for the deterministic resume semantic parser.

This exists because there was no accuracy number for the parser before —
only fixed per-rule confidence constants that were never checked against a
labeled expectation. "100%" was explicitly ruled out as a target (no parser
hits that against real-world formatting diversity); this harness produces a
real, reproducible number instead, and a regression floor
(`tests/unit/test_resume_parser_accuracy.py`) so it can't silently get worse.

Scope: this measures semantic FIELD-extraction accuracy (name, email, job
title, employer, dates, etc.) given already section/block-classified input —
the layer with the regex-based extraction rules that decides whether a
person's information was read correctly. Section detection, multi-column
layout, and OCR are a different, earlier layer with their own existing tests
(`test_resume_section_detection.py`, `test_resume_document_extractors.py`);
they are not re-measured here.

Run:

    uv run --project backend python -m rezumi.development.eval_resume_parser
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from hashlib import sha256
from uuid import uuid4

from rezumi.modules.resume_health.domain import (
    BlockKind,
    CanonicalBlock,
    CanonicalResume,
    CanonicalSection,
    SectionKind,
    SemanticEntityKind,
    SourceSpan,
)
from rezumi.modules.resume_health.infrastructure.semantic_parser import (
    LocalResumeParserProvider,
)

_SOURCE_SHA256 = sha256(b"eval-resume-parser-fixture").hexdigest()


@dataclass(frozen=True, slots=True)
class GoldenSection:
    kind: SectionKind
    # (block_kind, text) pairs, in document order.
    blocks: tuple[tuple[BlockKind, str], ...]


@dataclass(frozen=True, slots=True)
class GoldenCase:
    name: str
    sections: tuple[GoldenSection, ...]
    # Expected entities per kind, in the order the parser should emit them.
    # Each entity is a dict of {field_name: expected_value}. A field the
    # parser is expected to leave unset should simply be omitted.
    expected: dict[SemanticEntityKind, tuple[dict[str, str], ...]] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class FieldTally:
    correct: int = 0
    wrong: int = 0
    missing: int = 0
    unexpected: int = 0

    @property
    def total_expected(self) -> int:
        return self.correct + self.wrong + self.missing

    @property
    def precision(self) -> float | None:
        found = self.correct + self.wrong + self.unexpected
        return None if found == 0 else self.correct / found

    @property
    def recall(self) -> float | None:
        return None if self.total_expected == 0 else self.correct / self.total_expected


def _resume(sections: tuple[GoldenSection, ...]) -> CanonicalResume:
    built: list[CanonicalSection] = []
    for section in sections:
        blocks = tuple(
            CanonicalBlock(
                id=uuid4(),
                kind=block_kind,
                text=text,
                confidence_basis_points=9_000,
                spans=(SourceSpan(1, 0, len(text)),),
            )
            for block_kind, text in section.blocks
        )
        built.append(
            CanonicalSection(
                id=uuid4(),
                kind=section.kind,
                title=section.kind.value.title(),
                confidence_basis_points=9_000,
                blocks=blocks,
            )
        )
    return CanonicalResume(
        schema_version="canonical-resume/2.0.0",
        sections=tuple(built),
        warnings=(),
    )


async def _parse(case: GoldenCase) -> dict[SemanticEntityKind, tuple[dict[str, str], ...]]:
    resume = _resume(case.sections)
    semantics = await LocalResumeParserProvider().parse(uuid4(), resume, _SOURCE_SHA256)
    actual: dict[SemanticEntityKind, list[dict[str, str]]] = {}
    for entity in semantics.entities:
        # SKILL entities hold one repeated "name" field per skill in the
        # list, not one field per name — expand each into its own
        # comparable pseudo-entity rather than letting a dict comprehension
        # silently collapse all but the last skill under one key.
        if entity.kind is SemanticEntityKind.SKILL:
            for skill_field in entity.fields:
                actual.setdefault(entity.kind, []).append({skill_field.name: skill_field.value})
            continue
        actual.setdefault(entity.kind, []).append(
            {field.name: field.value for field in entity.fields}
        )
    return {kind: tuple(entities) for kind, entities in actual.items()}


def _score_case(
    case: GoldenCase,
    actual: dict[SemanticEntityKind, tuple[dict[str, str], ...]],
) -> dict[str, FieldTally]:
    """Per-field tallies, keyed `"{entity_kind}.{field_name}"`.

    Entities are aligned positionally within each kind — case authors list
    expected entities in the order the parser should emit them.
    """
    tallies: dict[str, FieldTally] = {}

    def bump(key: str, **kwargs: int) -> None:
        current = tallies.get(key, FieldTally())
        tallies[key] = FieldTally(
            correct=current.correct + kwargs.get("correct", 0),
            wrong=current.wrong + kwargs.get("wrong", 0),
            missing=current.missing + kwargs.get("missing", 0),
            unexpected=current.unexpected + kwargs.get("unexpected", 0),
        )

    all_kinds = set(case.expected) | set(actual)
    for kind in all_kinds:
        expected_entities = case.expected.get(kind, ())
        actual_entities = actual.get(kind, ())
        for index in range(max(len(expected_entities), len(actual_entities))):
            expected_fields = expected_entities[index] if index < len(expected_entities) else {}
            actual_fields = actual_entities[index] if index < len(actual_entities) else {}
            field_names = set(expected_fields) | set(actual_fields)
            for name in field_names:
                key = f"{kind.value}.{name}"
                expected_value = expected_fields.get(name)
                actual_value = actual_fields.get(name)
                if expected_value is None and actual_value is not None:
                    bump(key, unexpected=1)
                elif expected_value is not None and actual_value is None:
                    bump(key, missing=1)
                elif expected_value == actual_value:
                    bump(key, correct=1)
                else:
                    bump(key, wrong=1)
    return tallies


@dataclass(frozen=True, slots=True)
class EvalReport:
    case_results: dict[str, dict[str, FieldTally]]

    def overall(self) -> tuple[float | None, float | None]:
        totals = FieldTally()
        for field_tallies in self.case_results.values():
            for tally in field_tallies.values():
                totals = FieldTally(
                    correct=totals.correct + tally.correct,
                    wrong=totals.wrong + tally.wrong,
                    missing=totals.missing + tally.missing,
                    unexpected=totals.unexpected + tally.unexpected,
                )
        return totals.precision, totals.recall

    def render(self) -> str:
        lines = ["Resume semantic parser accuracy report", "=" * 40]
        for case_name, field_tallies in self.case_results.items():
            lines.append(f"\n{case_name}:")
            for key, tally in sorted(field_tallies.items()):
                precision = "n/a" if tally.precision is None else f"{tally.precision:.0%}"
                recall = "n/a" if tally.recall is None else f"{tally.recall:.0%}"
                lines.append(
                    f"  {key:<28} precision={precision:>5} recall={recall:>5} "
                    f"(correct={tally.correct} wrong={tally.wrong} "
                    f"missing={tally.missing} unexpected={tally.unexpected})"
                )
        overall_precision, overall_recall = self.overall()
        lines.append("\nOverall:")
        lines.append(
            f"  precision={overall_precision:.1%}"
            if overall_precision is not None
            else "  precision=n/a"
        )
        lines.append(
            f"  recall={overall_recall:.1%}" if overall_recall is not None else "  recall=n/a"
        )
        return "\n".join(lines)


async def run_eval(corpus: tuple[GoldenCase, ...]) -> EvalReport:
    case_results: dict[str, dict[str, FieldTally]] = {}
    for case in corpus:
        actual = await _parse(case)
        case_results[case.name] = _score_case(case, actual)
    return EvalReport(case_results=case_results)


def main() -> int:
    from rezumi.development.resume_parser_golden_corpus import GOLDEN_CORPUS

    report = asyncio.run(run_eval(GOLDEN_CORPUS))
    print(report.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
