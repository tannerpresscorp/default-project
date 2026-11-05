from collections.abc import AsyncIterator
from contextvars import ContextVar
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .identity import AuthenticationError, IdentityUnavailable, Principal

current_principal: ContextVar[Principal | None] = ContextVar("principal", default=None)
bearer = HTTPBearer(auto_error=False)


async def authenticated_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AsyncIterator[Principal]:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    verifier = request.app.state.verifier
    if verifier is None:
        raise HTTPException(status_code=503, detail="Authentication unavailable")
    try:
        principal = await verifier.verify(credentials.credentials)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"}
        ) from exc
    except IdentityUnavailable as exc:
        raise HTTPException(status_code=503, detail="Authentication unavailable") from exc
    token = current_principal.set(principal)
    try:
        yield principal
    finally:
        current_principal.reset(token)
