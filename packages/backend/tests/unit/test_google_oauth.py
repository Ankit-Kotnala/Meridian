"""Google OpenID Connect adapter policy tests that require no provider credentials."""

from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest

from careeros.integrations.oauth.google import GoogleOAuthOptions, GoogleOAuthProvider
from careeros.modules.identity.domain.errors import OAuthFlowRejected


class MemoryFlowStore:
    def __init__(self) -> None:
        self.flows: dict[str, dict[str, object]] = {}

    async def save_oauth_flow(
        self, state: str, payload: dict[str, object], ttl_seconds: int
    ) -> None:
        assert ttl_seconds == 600
        self.flows[state] = payload

    async def consume_oauth_flow(self, state: str) -> dict[str, object]:
        payload = self.flows.pop(state, None)
        if payload is None:
            raise OAuthFlowRejected
        return payload


@pytest.mark.asyncio
async def test_start_binds_state_nonce_pkce_return_path_and_linking_user() -> None:
    store = MemoryFlowStore()
    provider = GoogleOAuthProvider(
        GoogleOAuthOptions(
            client_id="test-client-id",
            client_secret="test-client-secret",  # noqa: S106
            redirect_uri="https://app.example.com/api/v1/auth/google/callback",
        ),
        store,  # type: ignore[arg-type]
    )
    user_id = uuid4()

    started = await provider.start("/settings/sessions", user_id)
    query = parse_qs(urlparse(started.authorization_url).query)
    state = query["state"][0]
    flow = store.flows[state]

    assert query["client_id"] == ["test-client-id"]
    assert query["redirect_uri"] == ["https://app.example.com/api/v1/auth/google/callback"]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["openid email profile"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"][0]
    assert query["nonce"] == [flow["nonce"]]
    assert flow["code_verifier"]
    assert flow["return_to"] == "/settings/sessions"
    assert flow["link_user_id"] == str(user_id)


@pytest.mark.asyncio
async def test_start_rejects_external_return_targets() -> None:
    provider = GoogleOAuthProvider(
        GoogleOAuthOptions(
            client_id="test-client-id",
            client_secret="test-client-secret",  # noqa: S106
            redirect_uri="https://app.example.com/api/v1/auth/google/callback",
        ),
        MemoryFlowStore(),  # type: ignore[arg-type]
    )

    with pytest.raises(OAuthFlowRejected):
        await provider.start("https://attacker.example/steal")
    with pytest.raises(OAuthFlowRejected):
        await provider.start("//attacker.example/steal")
