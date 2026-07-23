"""JWT authentication and role extraction for read-only dashboard APIs."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from snoc_agent.config import Settings

bearer = HTTPBearer(auto_error=False)
BEARER_DEPENDENCY = Depends(bearer)


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    roles: frozenset[str]
    authenticated: bool

    @property
    def can_view_sensitive_details(self) -> bool:
        return bool(self.roles.intersection({"ADMIN", "SNOC_ADMIN", "AUDITOR"}))


def settings_from_request(request: Request) -> Settings:
    return request.app.state.settings


async def current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = BEARER_DEPENDENCY,
) -> Principal:
    settings = settings_from_request(request)
    public_key = settings.auth_jwt_public_key.get_secret_value()
    auth_configured = bool(public_key and settings.auth_jwt_issuer and settings.auth_jwt_audience)
    if not auth_configured:
        if settings.app_env.casefold() in {"production", "prod"}:
            raise HTTPException(503, "authentication is not configured")
        return Principal("development-readonly", frozenset({"VIEWER"}), False)
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(401, "bearer token required")
    try:
        claims = jwt.decode(
            credentials.credentials,
            public_key,
            algorithms=["RS256", "ES256"],
            issuer=settings.auth_jwt_issuer,
            audience=settings.auth_jwt_audience,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "invalid bearer token") from exc
    raw_roles = claims.get("roles", claims.get("role", []))
    if isinstance(raw_roles, str):
        roles = frozenset({raw_roles.upper()})
    elif isinstance(raw_roles, list):
        roles = frozenset(str(value).upper() for value in raw_roles)
    else:
        roles = frozenset()
    return Principal(str(claims["sub"]), roles, True)
