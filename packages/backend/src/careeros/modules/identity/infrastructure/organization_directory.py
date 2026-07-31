"""Purpose-limited identity directory for organization invitation acceptance."""

from uuid import UUID

from sqlalchemy import select

from careeros.foundation.database import Database
from careeros.modules.identity.infrastructure.models import UserModel


class IdentityOrganizationAccountDirectory:
    """Return only the normalized email required to bind an invitation."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def normalized_email(self, user_id: UUID) -> str | None:
        async with self._database.session() as session:
            value = await session.scalar(
                select(UserModel.email_normalized).where(
                    UserModel.id == user_id,
                    UserModel.status == "active",
                )
            )
            return str(value) if value is not None else None
