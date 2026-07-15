"""Authenticate the BFF-derived client key used for per-source abuse controls."""

import base64
import hashlib
import hmac
import ipaddress
import secrets
from typing import cast

from careeros.modules.identity.domain.errors import CsrfRejected
from fastapi import Request

from careeros_api.config import Settings

BFF_CLIENT_SIGNAL_HEADER = "X-CareerOS-Client-Signal"
_BFF_SIGNAL_CONTEXT = b"careeros-bff-client-v1\0"


def verified_client_source_key(request: Request) -> str:
    """Return an opaque stable rate key after verifying the trusted BFF signal.

    Staging and production fail closed because the API peer is normally the web
    tier, not the originating client. Development and test retain a peer-based
    fallback so direct local API workflows remain usable.
    """

    raw = request.headers.get(BFF_CLIENT_SIGNAL_HEADER)
    settings = cast(Settings, request.app.state.settings)
    if raw is None:
        if settings.environment in {"staging", "production"}:
            raise CsrfRejected
        peer = request.client.host if request.client is not None else "unavailable"
        return f"development-peer:{peer}"

    version, separator, remainder = raw.partition(".")
    encoded_source, signature_separator, signature = remainder.rpartition(".")
    if (
        version != "v1"
        or not separator
        or not signature_separator
        or len(encoded_source) > 128
        or len(signature) != 64
    ):
        raise CsrfRejected
    try:
        padding = "=" * (-len(encoded_source) % 4)
        source = base64.urlsafe_b64decode(encoded_source + padding).decode("ascii")
    except (ValueError, UnicodeDecodeError):
        raise CsrfRejected from None
    if source == "unavailable":
        if settings.environment in {"staging", "production"}:
            raise CsrfRejected
    else:
        try:
            ipaddress.ip_address(source)
        except ValueError:
            raise CsrfRejected from None

    expected = hmac.new(
        settings.bff_client_signal_secret.get_secret_value().encode("utf-8"),
        _BFF_SIGNAL_CONTEXT + source.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not secrets.compare_digest(expected, signature):
        raise CsrfRejected
    return f"bff:{signature}"
