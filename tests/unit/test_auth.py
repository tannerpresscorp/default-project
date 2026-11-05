import time
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from packages.auth.identity import (
    AuthenticationError,
    IdentityUnavailable,
    IdentityVerifier,
    verify_token,
)


@pytest.fixture
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(key, **overrides):
    claims = {
        "iss": "https://issuer.example/",
        "aud": "platform",
        "sub": "user-123",
        "exp": int(time.time()) + 60,
        "tenant_id": str(uuid4()),
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "key-1"})


def test_verified_identity_derives_tenant_from_signed_claim(signing_key):
    tenant = uuid4()
    principal = verify_token(
        token(signing_key, tenant_id=str(tenant)),
        signing_key.public_key(),
        issuer="https://issuer.example/",
        audience="platform",
        tenant_claim="tenant_id",
    )
    assert principal.tenant_id == tenant
    assert principal.subject == "user-123"


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "other"},
        {"iss": "https://evil.example/"},
        {"tenant_id": "invalid"},
        {"sub": ""},
        {"exp": 1},
    ],
)
def test_invalid_or_untrusted_claims_are_rejected(signing_key, overrides):
    with pytest.raises(AuthenticationError):
        verify_token(
            token(signing_key, **overrides),
            signing_key.public_key(),
            issuer="https://issuer.example/",
            audience="platform",
            tenant_claim="tenant_id",
        )


def test_invalid_signature_is_rejected(signing_key):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AuthenticationError):
        verify_token(
            token(signing_key),
            other.public_key(),
            issuer="https://issuer.example/",
            audience="platform",
            tenant_claim="tenant_id",
        )


def test_weak_signing_key_is_rejected():
    weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    with pytest.warns(jwt.warnings.InsecureKeyLengthWarning):
        weak_token = token(weak)
    with pytest.raises(AuthenticationError):
        verify_token(
            weak_token,
            weak.public_key(),
            issuer="https://issuer.example/",
            audience="platform",
            tenant_claim="tenant_id",
        )


def test_verifier_requires_secure_oidc_configuration():
    with pytest.raises(ValueError):
        IdentityVerifier(
            issuer="http://issuer.example",
            audience="platform",
            jwks_url="http://issuer.example/keys",
            tenant_claim="tenant_id",
        )


@pytest.mark.anyio
async def test_verifier_fetches_only_configured_jwks_and_rejects_unknown_key(signing_key):
    import json

    from jwt.algorithms import RSAAlgorithm

    public_jwk = json.loads(RSAAlgorithm.to_jwk(signing_key.public_key()))
    public_jwk["kid"] = "key-1"
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"keys": [public_jwk]})

    verifier = IdentityVerifier(
        issuer="https://issuer.example/",
        audience="platform",
        jwks_url="https://issuer.example/keys",
        tenant_claim="tenant_id",
        transport=httpx.MockTransport(handler),
    )
    assert (await verifier.verify(token(signing_key))).subject == "user-123"
    assert calls == ["https://issuer.example/keys"]
    unknown = jwt.encode({"sub": "x"}, signing_key, algorithm="RS256", headers={"kid": "unknown"})
    with pytest.raises(AuthenticationError):
        await verifier.verify(unknown)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_verifier_rejects_oversized_jwks(signing_key):
    body = b'{"keys":[],"padding":"' + b"x" * (1024 * 1024 + 1) + b'"}'
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=body))
    verifier = IdentityVerifier(
        issuer="https://issuer.example/",
        audience="platform",
        jwks_url="https://issuer.example/keys",
        tenant_claim="tenant_id",
        transport=transport,
    )
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(token(signing_key))
