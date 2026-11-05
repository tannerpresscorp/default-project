import asyncio
import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import UUID

import httpx
import jwt


class AuthenticationError(Exception):
    """Credentials could not be verified."""


class IdentityUnavailable(Exception):
    """The configured identity provider is unavailable."""


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    tenant_id: UUID


class Verifier(Protocol):
    async def verify(self, token: str) -> Principal: ...


def verify_token(
    token: str, key: Any, *, issuer: str, audience: str, tenant_claim: str
) -> Principal:
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            options={
                "require": ["exp", "iss", "aud", "sub", tenant_claim],
                "enforce_minimum_key_length": True,
            },
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("invalid subject")
        tenant = claims[tenant_claim]
        if not isinstance(tenant, str):
            raise ValueError("invalid tenant")
        return Principal(subject=subject, tenant_id=UUID(tenant))
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise AuthenticationError("Invalid credentials") from exc


class IdentityVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        tenant_claim: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if any(
            urlparse(url).scheme != "https" or not urlparse(url).hostname
            for url in (issuer, jwks_url)
        ):
            raise ValueError("OIDC issuer and JWKS URL must use HTTPS")
        if not audience or not tenant_claim:
            raise ValueError("OIDC audience and tenant claim are required")
        self.issuer = issuer
        self.audience = audience
        self.jwks_url = jwks_url
        self.tenant_claim = tenant_claim
        self.transport = transport

    async def verify(self, token: str) -> Principal:
        if len(token) > 16384:
            raise AuthenticationError("Invalid credentials")
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if header.get("alg") != "RS256" or not isinstance(kid, str) or not 0 < len(kid) <= 128:
                raise AuthenticationError("Invalid credentials")
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid credentials") from exc
        try:
            async with asyncio.timeout(3):
                async with httpx.AsyncClient(
                    timeout=3.0, follow_redirects=False, transport=self.transport
                ) as client:
                    async with client.stream("GET", self.jwks_url) as response:
                        response.raise_for_status()
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            content.extend(chunk)
                            if len(content) > 1024 * 1024:
                                raise ValueError("JWKS too large")
                        body = json.loads(content)
            keys = body["keys"]
            if not isinstance(keys, list) or len(keys) > 100:
                raise ValueError("Invalid JWKS")
            matches = [key for key in keys if isinstance(key, dict) and key.get("kid") == kid]
            if len(matches) != 1:
                raise AuthenticationError("Invalid credentials")
            if (
                matches[0].get("kty") != "RSA"
                or matches[0].get("use", "sig") != "sig"
                or matches[0].get("alg", "RS256") != "RS256"
                or ("key_ops" in matches[0] and "verify" not in matches[0]["key_ops"])
            ):
                raise AuthenticationError("Invalid credentials")
            jwk = jwt.PyJWK.from_dict(matches[0], algorithm="RS256")
        except (
            httpx.HTTPError,
            TimeoutError,
            ValueError,
            KeyError,
            TypeError,
            jwt.PyJWTError,
        ) as exc:
            raise IdentityUnavailable("Identity provider unavailable") from exc
        return verify_token(
            token,
            jwk.key,
            issuer=self.issuer,
            audience=self.audience,
            tenant_claim=self.tenant_claim,
        )
