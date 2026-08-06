"""Bounded SMTP email delivery adapter."""

from dataclasses import dataclass, field

import aiosmtplib

from rezumi.modules.identity.application.models import EmailMessage


@dataclass(frozen=True, slots=True)
class SmtpOptions:
    hostname: str
    port: int
    sender: str
    username: str | None = field(default=None, repr=False)
    password: str | None = field(default=None, repr=False)
    start_tls: bool = False
    timeout_seconds: float = 5.0


class SmtpEmailSender:
    def __init__(self, options: SmtpOptions) -> None:
        self._options = options

    async def send(self, message: EmailMessage) -> None:
        from email.message import EmailMessage as SmtpMessage

        outgoing = SmtpMessage()
        outgoing["From"] = self._options.sender
        outgoing["To"] = message.recipient
        outgoing["Subject"] = message.subject
        outgoing.set_content(message.text_body)
        outgoing.add_alternative(message.html_body, subtype="html")
        await aiosmtplib.send(
            outgoing,
            hostname=self._options.hostname,
            port=self._options.port,
            username=self._options.username,
            password=self._options.password,
            start_tls=self._options.start_tls,
            timeout=self._options.timeout_seconds,
        )

    async def ping(self) -> None:
        """Verify the configured SMTP endpoint without sending a message."""
        client = aiosmtplib.SMTP(
            hostname=self._options.hostname,
            port=self._options.port,
            username=self._options.username,
            password=self._options.password,
            timeout=self._options.timeout_seconds,
            start_tls=self._options.start_tls,
        )
        try:
            await client.connect()
            await client.noop()
        finally:
            if client.is_connected:
                await client.quit()

    async def dispose(self) -> None:
        """Sends use bounded one-shot connections, so there is no shared pool."""


class DisabledEmailSender:
    """Explicit non-production adapter for environments without email delivery."""

    async def send(self, message: EmailMessage) -> None:
        del message
        raise RuntimeError("email delivery is disabled")

    async def ping(self) -> None:
        return None

    async def dispose(self) -> None:
        return None
