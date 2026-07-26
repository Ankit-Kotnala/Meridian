"""Organization invitation email composition tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from careeros.modules.identity.application.models import EmailMessage
from careeros.modules.organizations.application import InvitationDeliveryMessage

from careeros_worker.organization_email import OrganizationInvitationEmailSender


class CapturingSender:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


@pytest.mark.asyncio
async def test_invitation_email_escapes_content_and_encodes_secret_url() -> None:
    captured = CapturingSender()
    sender = OrganizationInvitationEmailSender(captured, "https://app.example.test/")
    message = InvitationDeliveryMessage(
        invitation_id=uuid4(),
        organization_name="Fictional <Studio>",
        recipient="coach@example.test",
        token="fictional.token_-",  # noqa: S106 -- explicitly fictional credential
    )

    await sender.send(message)

    assert len(captured.messages) == 1
    email = captured.messages[0]
    assert email.recipient == "coach@example.test"
    assert email.subject == "Invitation to join Fictional <Studio>"
    assert "https://app.example.test/accept-invitation?token=fictional.token_-" in (email.text_body)
    assert "<strong>Fictional &lt;Studio&gt;</strong>" in email.html_body
    assert "<strong>Fictional <Studio></strong>" not in email.html_body
