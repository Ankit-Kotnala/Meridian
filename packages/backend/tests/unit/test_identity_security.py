"""Cryptographic adapter tests for password and opaque-token handling."""

import pytest
from argon2 import extract_parameters
from argon2.low_level import Type

from careeros.modules.identity.infrastructure.security import (
    Argon2PasswordHasher,
    HmacTokenManager,
    NormalizedEmailValidator,
)


@pytest.mark.asyncio
async def test_argon2id_parameters_and_wrong_password_behavior() -> None:
    hasher = Argon2PasswordHasher()
    encoded = await hasher.hash("a sufficiently long password")
    parameters = extract_parameters(encoded)

    assert parameters.type is Type.ID
    assert parameters.time_cost == 3
    assert parameters.memory_cost == 65_536
    assert parameters.parallelism == 4
    assert await hasher.verify(encoded, "a sufficiently long password")
    assert not await hasher.verify(encoded, "wrong password")
    assert not await hasher.verify("not-a-password-hash", "wrong password")


def test_opaque_tokens_store_only_keyed_digests_and_reject_malformed_values() -> None:
    tokens = HmacTokenManager("a-test-pepper-value-that-is-long-enough")
    issued = tokens.issue()
    parsed = tokens.parse(issued.encoded)

    assert parsed is not None
    token_id, secret = parsed
    assert token_id == issued.id
    assert secret not in repr(issued.digest)
    assert tokens.verify(issued.digest, secret)
    assert not tokens.verify(issued.digest, secret + "tampered")
    assert tokens.parse("not-a-token") is None
    assert tokens.parse("x." + "a" * 300) is None


def test_email_normalization_is_deterministic_without_dns_lookup() -> None:
    normalizer = NormalizedEmailValidator()

    assert normalizer.normalize(" Alex@EXAMPLE.com ") == "alex@example.com"
    with pytest.raises(ValueError, match="invalid"):
        normalizer.normalize("not an email")
