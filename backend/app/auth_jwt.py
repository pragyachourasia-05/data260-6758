"""HW7 Part 1: JWT bearer authentication and role checks (replaces the HW4 session cookie).

Passwords are verified with the existing PBKDF2 helpers in crud.py; a token is issued
only after the MySQL user row is found and the password hash matches.
"""
import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

JWT_SECRET = os.getenv("JWT_SECRET", "s6758-dev-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
ROLES = ("reader", "writer", "moderator")

bearer = HTTPBearer(auto_error=False)


def create_access_token(username: str, role: str, minutes: int = ACCESS_TOKEN_MINUTES) -> str:
    """Signed HS256 token carrying the username (sub), role and expiry."""
    now = datetime.now(timezone.utc)
    payload = {"sub": username, "role": role, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_claims(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    """401 for a missing, malformed, tampered or expired token."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized("Not authenticated")
    try:
        claims = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise _unauthorized("Invalid token") from exc
    if claims.get("role") not in ROLES or not claims.get("sub"):
        raise _unauthorized("Invalid token")
    return claims


def require_roles(*allowed: str) -> Callable:
    """Dependency: 403 when the token is valid but its role is not allowed."""

    def checker(claims: dict = Depends(get_current_claims)) -> dict:
        if claims["role"] not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{claims['role']}' may not do this; requires {', '.join(allowed)}",
            )
        return claims

    return checker


# Reusable role policies for the domain routes (used as Depends(WRITER_OR_MODERATOR), ...).
WRITER_OR_MODERATOR = require_roles("writer", "moderator")
MODERATOR_ONLY = require_roles("moderator")
