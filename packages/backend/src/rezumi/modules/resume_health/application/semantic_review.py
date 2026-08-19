"""Pure typed review operations for semantic resume snapshots."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from rezumi.modules.resume_health.application.models import (
    AddSemanticEntity,
    AddSemanticField,
    ConfirmSemanticField,
    CorrectSemanticField,
    ReclassifySemanticEntity,
    RemoveSemanticEntity,
    RemoveSemanticField,
    SemanticReviewOperation,
)
from rezumi.modules.resume_health.domain import (
    CanonicalSemantics,
    DatePrecision,
    SemanticEntity,
    SemanticEntityKind,
    SemanticField,
    SemanticFieldType,
    SemanticReviewState,
    allowed_semantic_field_names,
    allowed_semantic_field_types,
)
from rezumi.modules.resume_health.domain.errors import ResumeStateConflict


def auto_confirm_parsed_semantics(semantics: CanonicalSemantics) -> CanonicalSemantics:
    """Trust parser output for first-pass career record population.

    Parsed resume fields start UNREVIEWED. Account uploads auto-confirm them so
    experiences, skills, and contact facts can land in the career record without
    a separate manual review step. Users can still correct values later.
    """
    if not semantics.entities:
        raise ResumeStateConflict
    return apply_semantic_review(semantics, (), confirm_no_changes=True)


def apply_semantic_review(
    semantics: CanonicalSemantics,
    operations: tuple[SemanticReviewOperation, ...],
    *,
    confirm_no_changes: bool,
) -> CanonicalSemantics:
    """Return a reviewed successor while retaining all original source claims."""
    if confirm_no_changes and operations:
        raise ResumeStateConflict
    if not confirm_no_changes and not operations:
        raise ResumeStateConflict
    entities = list(semantics.entities)
    touched: set[tuple[str, object]] = set()
    for operation in operations:
        if isinstance(operation, AddSemanticEntity):
            if not operation.fields:
                raise ResumeStateConflict
            fields = tuple(
                _new_field(
                    field.name,
                    field.field_type,
                    field.value,
                    field.date_precision,
                )
                for field in operation.fields
            )
            _validate_fields(operation.kind, fields)
            entities.append(
                SemanticEntity(
                    id=uuid4(),
                    kind=operation.kind,
                    review_state=SemanticReviewState.USER_ADDED,
                    fields=fields,
                )
            )
            continue
        if isinstance(operation, ReclassifySemanticEntity):
            _touch(touched, "entity", operation.entity_id)
            index, entity = _find_entity(entities, operation.entity_id)
            if entity.review_state is SemanticReviewState.REMOVED:
                raise ResumeStateConflict
            names = {item.field_id: item.name for item in operation.fields}
            if len(names) != len(operation.fields) or set(names) != {
                field.id for field in entity.fields
            }:
                raise ResumeStateConflict
            fields = tuple(replace(field, name=names[field.id]) for field in entity.fields)
            _validate_fields(operation.kind, fields)
            if operation.kind is entity.kind and fields == entity.fields:
                raise ResumeStateConflict
            entities[index] = replace(
                entity,
                kind=operation.kind,
                fields=fields,
                review_state=_changed_entity_state(entity),
            )
            continue
        if isinstance(operation, RemoveSemanticEntity):
            _touch(touched, "entity", operation.entity_id)
            index, entity = _find_entity(entities, operation.entity_id)
            if entity.review_state is SemanticReviewState.REMOVED:
                raise ResumeStateConflict
            entities[index] = replace(
                entity,
                review_state=SemanticReviewState.REMOVED,
                fields=tuple(
                    replace(field, review_state=SemanticReviewState.REMOVED)
                    for field in entity.fields
                ),
            )
            continue
        if isinstance(operation, AddSemanticField):
            index, entity = _find_entity(entities, operation.entity_id)
            if entity.review_state is SemanticReviewState.REMOVED:
                raise ResumeStateConflict
            field = _new_field(
                operation.name,
                operation.field_type,
                operation.value,
                operation.date_precision,
            )
            _validate_fields(entity.kind, (*entity.fields, field))
            entities[index] = replace(
                entity,
                fields=(*entity.fields, field),
                review_state=_changed_entity_state(entity),
            )
            continue
        field_id = operation.field_id
        _touch(touched, "field", field_id)
        entity_index, entity, field_index, field = _find_field(entities, field_id)
        if field.review_state is SemanticReviewState.REMOVED:
            raise ResumeStateConflict
        if isinstance(operation, ConfirmSemanticField):
            if field.review_state is not SemanticReviewState.UNREVIEWED:
                raise ResumeStateConflict
            replacement = replace(field, review_state=SemanticReviewState.CONFIRMED)
        elif isinstance(operation, CorrectSemanticField):
            value = _safe_value(operation.value)
            precision = operation.date_precision or field.date_precision
            _validate_date_precision(field.field_type, precision)
            if value == field.value and precision == field.date_precision:
                raise ResumeStateConflict
            replacement = replace(
                field,
                value=value,
                date_precision=precision,
                confidence_basis_points=10_000,
                review_state=(
                    SemanticReviewState.USER_ADDED
                    if field.review_state is SemanticReviewState.USER_ADDED
                    else SemanticReviewState.CORRECTED
                ),
            )
        elif isinstance(operation, RemoveSemanticField):
            replacement = replace(field, review_state=SemanticReviewState.REMOVED)
        else:
            raise ResumeStateConflict
        updated_fields = list(entity.fields)
        updated_fields[field_index] = replacement
        entities[entity_index] = replace(
            entity,
            fields=tuple(updated_fields),
            review_state=_entity_state(tuple(updated_fields), entity.review_state),
        )
    if confirm_no_changes:
        entities = [
            replace(
                entity,
                review_state=(
                    SemanticReviewState.CONFIRMED
                    if entity.review_state is SemanticReviewState.UNREVIEWED
                    else entity.review_state
                ),
                fields=tuple(
                    replace(field, review_state=SemanticReviewState.CONFIRMED)
                    if field.review_state is SemanticReviewState.UNREVIEWED
                    else field
                    for field in entity.fields
                ),
            )
            for entity in entities
        ]
    revised = replace(
        semantics,
        entities=tuple(entities),
        review_state=(
            SemanticReviewState.CONFIRMED if confirm_no_changes else SemanticReviewState.CORRECTED
        ),
    )
    if revised == semantics:
        if confirm_no_changes:
            return semantics
        raise ResumeStateConflict
    return revised


def _new_field(
    name: str,
    field_type: SemanticFieldType,
    value: str,
    date_precision: DatePrecision | None,
) -> SemanticField:
    _validate_date_precision(field_type, date_precision)
    return SemanticField(
        id=uuid4(),
        name=name,
        field_type=field_type,
        value=_safe_value(value),
        confidence_basis_points=10_000,
        review_state=SemanticReviewState.USER_ADDED,
        date_precision=date_precision,
    )


def _validate_date_precision(
    field_type: SemanticFieldType,
    date_precision: DatePrecision | None,
) -> None:
    if (field_type is SemanticFieldType.DATE) != (date_precision is not None):
        raise ResumeStateConflict


def _validate_fields(
    kind: SemanticEntityKind,
    fields: tuple[SemanticField, ...],
) -> None:
    try:
        allowed = allowed_semantic_field_names(kind)
    except (KeyError, TypeError) as exc:
        raise ResumeStateConflict from exc
    if any(
        field.name not in allowed
        or field.field_type not in allowed_semantic_field_types(kind, field.name)
        for field in fields
    ):
        raise ResumeStateConflict


def _safe_value(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 10_000 or "\x00" in normalized:
        raise ResumeStateConflict
    return normalized


def _find_entity(entities: list[SemanticEntity], entity_id: object) -> tuple[int, SemanticEntity]:
    matches = [(index, entity) for index, entity in enumerate(entities) if entity.id == entity_id]
    if len(matches) != 1:
        raise ResumeStateConflict
    return matches[0]


def _find_field(
    entities: list[SemanticEntity], field_id: object
) -> tuple[int, SemanticEntity, int, SemanticField]:
    matches = [
        (entity_index, entity, field_index, field)
        for entity_index, entity in enumerate(entities)
        for field_index, field in enumerate(entity.fields)
        if field.id == field_id
    ]
    if len(matches) != 1:
        raise ResumeStateConflict
    return matches[0]


def _touch(touched: set[tuple[str, object]], kind: str, identifier: object) -> None:
    key = (kind, identifier)
    if key in touched:
        raise ResumeStateConflict
    touched.add(key)


def _changed_entity_state(entity: SemanticEntity) -> SemanticReviewState:
    if entity.review_state is SemanticReviewState.USER_ADDED:
        return SemanticReviewState.USER_ADDED
    return SemanticReviewState.CORRECTED


def _entity_state(
    fields: tuple[SemanticField, ...],
    previous: SemanticReviewState,
) -> SemanticReviewState:
    states = {field.review_state for field in fields}
    if states == {SemanticReviewState.REMOVED}:
        return SemanticReviewState.REMOVED
    if previous is SemanticReviewState.USER_ADDED:
        return SemanticReviewState.USER_ADDED
    if states <= {SemanticReviewState.CONFIRMED, SemanticReviewState.REMOVED}:
        return SemanticReviewState.CONFIRMED
    if states & {
        SemanticReviewState.CORRECTED,
        SemanticReviewState.USER_ADDED,
        SemanticReviewState.REMOVED,
    }:
        return SemanticReviewState.CORRECTED
    return SemanticReviewState.UNREVIEWED
