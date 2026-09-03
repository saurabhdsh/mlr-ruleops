from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.enums import RoleName
from app.core.errors import ForbiddenAction, Unauthorized
from app.db.session import get_db
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: UUID, email: str, roles: list[str]) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expiry_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid or expired token") from exc


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
    x_correlation_id: Annotated[str | None, Header()] = None,
) -> User:
    if creds is None:
        raise Unauthorized()
    payload = decode_token(creds.credentials)
    user = (
        db.query(User)
        .options(selectinload(User.roles))
        .filter(User.id == payload.get("sub"))
        .one_or_none()
    )
    if user is None or not user.is_active:
        raise Unauthorized("User not found or inactive")
    if x_correlation_id:
        user._correlation_id = x_correlation_id  # type: ignore[attr-defined]
    return user


def require_roles(*roles: RoleName):
    allowed = {r.value for r in roles}

    def _dep(user: Annotated[User, Depends(get_current_user)]) -> User:
        names = {r.name for r in user.roles}
        if RoleName.ADMIN.value in names:
            return user
        if names.isdisjoint(allowed):
            raise ForbiddenAction(f"Requires one of: {', '.join(sorted(allowed))}")
        return user

    return _dep
