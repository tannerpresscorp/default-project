import asyncio
import json
import time
from collections.abc import Callable
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
    """Verify RS256 tokens against a cached, bounded JWKS document.

    Keys are cached for ``cache_ttl_seconds``. An unknown ``kid`` triggers at
    most one forced refresh per ``refresh_min_interval_seconds`` so a rotation
    is picked up quickly without letting arbitrary tokens hammer the provider.
    Every refresh keeps the three-second timeout and deny-on-failure behavior.
    """

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        tenant_claim: str,
        transport: httpx.AsyncBaseTransport | None = None,
        cache_ttl_seconds: float = 300.0,
        refresh_min_interval_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        if any(
            urlparse(url).scheme != "https" or not urlparse(url).hostname
            for url in (issuer, jwks_url)
        ):
            raise ValueError("OIDC issuer and JWKS URL must use HTTPS")
        if not audience or not tenant_claim:
            raise ValueError("OIDC audience and tenant claim are required")
        if not 0 < cache_ttl_seconds <= 3600:
            raise ValueError("cache_ttl_seconds must be greater than 0 and at most 3600")
        if not 0 <= refresh_min_interval_seconds <= cache_ttl_seconds:
            raise ValueError("refresh_min_interval_seconds must be between 0 and cache_ttl_seconds")
        self.issuer = issuer
        self.audience = audience
        self.jwks_url = jwks_url
        self.tenant_claim = tenant_claim
        self.transport = transport
        self._cache_ttl_seconds = cache_ttl_seconds
        self._refresh_min_interval_seconds = refresh_min_interval_seconds
        self._clock = clock
        self._keys: dict[str, Any] = {}
        self._fetched_at: float | None = None
        self._refresh_lock = asyncio.Lock()

    def _cache_is_fresh(self) -> bool:
        return (
            self._fetched_at is not None
            and self._clock() - self._fetched_at < self._cache_ttl_seconds
        )

    def _refresh_is_rate_limited(self) -> bool:
        return (
            self._fetched_at is not None
            and self._clock() - self._fetched_at < self._refresh_min_interval_seconds
        )

    async def _resolve_key(self, kid: str) -> Any:
        if self._cache_is_fresh():
            key = self._keys.get(kid)
            if key is not None:
                return key
            if self._refresh_is_rate_limited():
                raise AuthenticationError("Invalid credentials")
        async with self._refresh_lock:
            # Another request may have refreshed while this one waited.
            if self._cache_is_fresh():
                key = self._keys.get(kid)
                if key is not None:
                    return key
                if self._refresh_is_rate_limited():
                    raise AuthenticationError("Invalid credentials")
            await self._fetch_keys()
        key = self._keys.get(kid)
        if key is None:
            raise AuthenticationError("Invalid credentials")
        return key

    async def _fetch_keys(self) -> None:
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
            parsed: dict[str, Any] = {}
            for key in keys:
                if not isinstance(key, dict):
                    continue
                key_id = key.get("kid")
                if not isinstance(key_id, str) or not 0 < len(key_id) <= 128:
                    continue
                if (
                    key.get("kty") != "RSA"
                    or key.get("use", "sig") != "sig"
                    or key.get("alg", "RS256") != "RS256"
                    or ("key_ops" in key and "verify" not in key["key_ops"])
                ):
                    continue
                if key_id in parsed:
                    raise ValueError("Duplicate JWKS key id")
                parsed[key_id] = jwt.PyJWK.from_dict(key, algorithm="RS256").key
            if not parsed:
                raise ValueError("No usable JWKS keys")
        except (
            httpx.HTTPError,
            TimeoutError,
            ValueError,
            KeyError,
            TypeError,
            jwt.PyJWTError,
        ) as exc:
            raise IdentityUnavailable("Identity provider unavailable") from exc
        self._keys = parsed
        self._fetched_at = self._clock()

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
        key = await self._resolve_key(kid)
        return verify_token(
            token,
            key,
            issuer=self.issuer,
            audience=self.audience,
            tenant_claim=self.tenant_claim,
        )
