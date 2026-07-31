"""Worker-only organization invitation email composition."""

from __future__ import annotations

from html import escape
from urllib.parse import quote

from careeros.modules.identity.application.models import EmailMessage
from careeros.modules.identity.application.ports import EmailSender
from careeros.modules.organizations.application import InvitationDeliveryMessage


class OrganizationInvitationEmailSender:
    """Render a bounded invitation message at the deployable composition root."""

    def __init__(self, sender: EmailSender, public_app_url: str) -> None:
        self._sender = sender
        self._public_app_url = public_app_url.rstrip("/")

    async def send(self, message: InvitationDeliveryMessage) -> None:
        url = f"{self._public_app_url}/accept-invitation?token={quote(message.token, safe='')}"
        organization_name = escape(message.organization_name)
        escaped_url = escape(url, quote=True)
        await self._sender.send(
            EmailMessage(
                recipient=message.recipient,
                subject=f"Invitation to join {message.organization_name}",
                text_body=(
                    f"You have been invited to join {message.organization_name} on CareerOS.\n\n"
                    f"Accept the invitation: {url}\n\n"
                    "If you did not expect this invitation, you can ignore this email."
                ),
                html_body=(
                    "<p>You have been invited to join "
                    f"<strong>{organization_name}</strong> on CareerOS.</p>"
                    f'<p><a href="{escaped_url}">Accept invitation</a></p>'
                    "<p>If you did not expect this invitation, you can ignore this email.</p>"
                ),
            )
        )
