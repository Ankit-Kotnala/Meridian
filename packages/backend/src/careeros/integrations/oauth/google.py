"""Google OpenID Connect adapter with state, nonce, PKCE, and one-use flow state."""

import secrets
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oidc.core import CodeIDToken
from joserfc import jwt

from careeros.modules.identity.application.models import OAuthIdentity, OAuthStart
from careeros.modules.identity.domain.errors import OAuthFlowRejected
from careeros.modules.identity.infrastructure.redis_security import RedisSecurityStore


@dataclass(frozen=True, slots=True)
class GoogleOAuthOptions:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    authorization_endpoint: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_endpoint: str = "https://oauth2.googleapis.com/token"  # noqa: S105 -- endpoint URL
    jwks_uri: str = "https://www.googleapis.com/oauth2/v3/certs"
    flow_ttl_seconds: int = 600
    timeout_seconds: float = 8.0


class GoogleOAuthProvider:
    enabled = True

    def __init__(self, options: GoogleOAuthOptions, store: RedisSecurityStore) -> None:
        self._options = options
        self._store = store

    async def start(self, return_to: str, link_user_id: UUID | None = None) -> OAuthStart:
        if not return_to.startswith("/") or return_to.startswith("//"):
            raise OAuthFlowRejected
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        client = AsyncOAuth2Client(
            self._options.client_id,
            self._options.client_secret,
            scope="openid email profile",
            redirect_uri=self._options.redirect_uri,
            code_challenge_method="S256",
        )
        try:
            authorization_url, returned_state = client.create_authorization_url(
                self._options.authorization_endpoint,
                state=state,
                nonce=nonce,
                code_verifier=code_verifier,
                prompt="select_account",
            )
        finally:
            await client.aclose()
        if returned_state != state:
            raise OAuthFlowRejected
        await self._store.save_oauth_flow(
            state,
            {
                "nonce": nonce,
                "code_verifier": code_verifier,
                "return_to": return_to,
                "link_user_id": str(link_user_id) if link_user_id is not None else None,
            },
            self._options.flow_ttl_seconds,
        )
        return OAuthStart(authorization_url=authorization_url, state=state)

    async def complete(self, code: str, state: str) -> OAuthIdentity:
        try:
            flow = await self._store.consume_oauth_flow(state)
            nonce = self._required_string(flow, "nonce")
            code_verifier = self._required_string(flow, "code_verifier")
            return_to = self._required_string(flow, "return_to")
            client = AsyncOAuth2Client(
                self._options.client_id,
                self._options.client_secret,
                scope="openid email profile",
                redirect_uri=self._options.redirect_uri,
                state=state,
                timeout=self._options.timeout_seconds,
            )
            try:
                token = await client.fetch_token(
                    self._options.token_endpoint,
                    code=code,
                    code_verifier=code_verifier,
                    redirect_uri=self._options.redirect_uri,
                )
            finally:
                await client.aclose()
            id_token = token.get("id_token")
            if not isinstance(id_token, str):
                raise OAuthFlowRejected
            async with httpx.AsyncClient(timeout=self._options.timeout_seconds) as http:
                response = await http.get(self._options.jwks_uri)
                response.raise_for_status()
                keys = response.json()
            decoded = jwt.decode(id_token, keys, algorithms=["RS256"])
            claims = CodeIDToken(
                decoded.claims,
                decoded.header,
                params={
                    "nonce": nonce,
                    "client_id": self._options.client_id,
                    "access_token": token.get("access_token"),
                },
            )
            claims.validate()
            issuer = claims.get("iss")
            audience = claims.get("aud")
            if issuer not in {"https://accounts.google.com", "accounts.google.com"}:
                raise OAuthFlowRejected
            if audience != self._options.client_id and not (
                isinstance(audience, list) and self._options.client_id in audience
            ):
                raise OAuthFlowRejected
            if claims.get("nonce") != nonce:
                raise OAuthFlowRejected
            subject = claims.get("sub")
            email = claims.get("email")
            email_verified = claims.get("email_verified")
            if not isinstance(subject, str) or not isinstance(email, str):
                raise OAuthFlowRejected
            display_name = claims.get("name")
            link_value = flow.get("link_user_id")
            link_user_id = UUID(link_value) if isinstance(link_value, str) else None
            return OAuthIdentity(
                subject=subject,
                email=email,
                email_verified=email_verified is True,
                display_name=display_name if isinstance(display_name, str) else "CareerOS user",
                return_to=return_to,
                link_user_id=link_user_id,
            )
        except OAuthFlowRejected:
            raise
        except Exception as exc:
            raise OAuthFlowRejected from exc

    @staticmethod
    def _required_string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise OAuthFlowRejected
        return value
