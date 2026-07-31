"""Presentation-only mapping for protected administration responses."""

from typing import Literal, cast

from careeros.modules.administration.application import (
    AdminAuditPage,
    AdminCatalogSnapshot,
    AdminDeadLetterPage,
    AdminSystemSnapshot,
    RetryResult,
)

from careeros_api.modules.administration.schemas import (
    AdminAuditEventResponse,
    AdminAuditPageResponse,
    AdminCatalogResponse,
    AdminDeadLetterPageResponse,
    AdminDeadLetterResponse,
    AdminRetryResponse,
    AdminSystemResponse,
    AdminSystemTotalsResponse,
)


def system_response(value: AdminSystemSnapshot) -> AdminSystemResponse:
    return AdminSystemResponse(
        generated_at=value.generated_at,
        totals=AdminSystemTotalsResponse(
            users_active=value.totals.users_active,
            users_disabled=value.totals.users_disabled,
            organizations_active=value.totals.organizations_active,
            subscriptions_active=value.totals.subscriptions_active,
            queued_jobs=value.totals.queued_jobs,
            retry_wait_jobs=value.totals.retry_wait_jobs,
            running_jobs=value.totals.running_jobs,
            dead_letter_jobs=value.totals.dead_letter_jobs,
        ),
        audit_chain_valid=value.audit_chain_valid,
    )


def catalog_response(value: AdminCatalogSnapshot) -> AdminCatalogResponse:
    return AdminCatalogResponse(
        generated_at=value.generated_at,
        configured_plans=value.configured_plans,
        owner_decision_required_plans=value.owner_decision_required_plans,
        enabled_feature_flags=list(value.enabled_feature_flags),
        role_taxonomy_versions=value.role_taxonomy_versions,
        active_role_definitions=value.active_role_definitions,
        resume_template_keys=list(value.resume_template_keys),
    )


def dead_letter_page_response(value: AdminDeadLetterPage) -> AdminDeadLetterPageResponse:
    return AdminDeadLetterPageResponse(
        items=[
            AdminDeadLetterResponse(
                kind=item.kind,
                id=item.id,
                status=item.status,
                safe_error_code=item.safe_error_code,
                attempts=item.attempts,
                max_attempts=item.max_attempts,
                occurred_at=item.occurred_at,
                retry_supported=item.retry_supported,
            )
            for item in value.items
        ],
        next_cursor=value.next_cursor,
    )


def retry_response(value: RetryResult) -> AdminRetryResponse:
    return AdminRetryResponse(
        kind=value.kind,
        id=value.id,
        status=value.status,
        replayed=value.replayed,
    )


def audit_page_response(value: AdminAuditPage) -> AdminAuditPageResponse:
    return AdminAuditPageResponse(
        items=[
            AdminAuditEventResponse(
                id=item.id,
                sequence=item.sequence or 0,
                actor_reference=item.actor_reference or "",
                actor_role=item.actor_role.value if item.actor_role is not None else None,
                capability=item.capability.value,
                action=item.action,
                outcome=cast(
                    Literal["accepted", "success", "denied", "failed"],
                    item.outcome,
                ),
                reason=item.reason,
                target_kind=item.target_kind,
                target_id=item.target_id,
                request_id=item.request_id,
                trace_id=item.trace_id,
                previous_hash=item.previous_hash or "",
                event_hash=item.event_hash or "",
                occurred_at=item.occurred_at,
            )
            for item in value.items
        ],
        next_cursor=value.next_cursor,
    )
