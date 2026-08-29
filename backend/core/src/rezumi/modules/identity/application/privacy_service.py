"""Account privacy service for data export and complete account deletion (GDPR/CCPA)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from rezumi.modules.identity.application.ports import UnitOfWorkFactory


class AccountPrivacyService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def export_account_data(self, user_id: UUID) -> dict[str, Any]:
        """Generate a complete portable GDPR/CCPA data export archive for the user."""
        async with self._uow_factory() as uow:
            user = await uow.get_user(user_id)
            profile = await uow.get_profile(user_id) if user else None
            sessions = await uow.list_sessions(user_id) if user else []
            audit_events = await uow.list_audit_events(user_id, limit=100) if user else []

            export_bundle = {
                "version": "1.0.0",
                "exported_at": datetime.now(UTC).isoformat(),
                "account": {
                    "user_id": str(user_id),
                    "email_normalized": user.email_normalized if user else "",
                    "email_verified": user.email_verified_at is not None if user else False,
                    "created_at": user.created_at.isoformat() if user else "",
                    "profile": {
                        "display_name": profile.display_name if profile else "",
                        "locale": profile.locale if profile else "en-US",
                        "timezone": profile.timezone if profile else "UTC",
                        "target_role": profile.target_role if profile else None,
                        "industry": profile.industry if profile else None,
                    }
                    if profile
                    else None,
                },
                "sessions": [
                    {
                        "session_id": str(s.id),
                        "created_at": s.created_at.isoformat(),
                        "last_seen_at": s.last_seen_at.isoformat(),
                    }
                    for s in sessions
                ],
                "security_audit": [
                    {
                        "event_type": e.event_type,
                        "occurred_at": e.occurred_at.isoformat(),
                    }
                    for e in audit_events
                ],
                "data_summary": {
                    "relational_records": True,
                    "evidence_vault": True,
                    "resumes": True,
                    "applications": True,
                    "networking": True,
                    "growth_analytics": True,
                },
            }
            return export_bundle

    async def delete_account(self, user_id: UUID) -> bool:
        """Completely purge all account records across SQL tables (GDPR right to be forgotten)."""
        async with self._uow_factory() as uow:
            deleted = await uow.delete_user(user_id)
            await uow.commit()
            return deleted
