from fastapi import APIRouter

from app.api.deps import DbDep, UserDep
from app.core.config import settings
from app.core.errors import Unauthorized
from app.models.user import User
from app.schemas.common import LoginRequest, TokenResponse, UserOut
from app.security.auth import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbDep) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise Unauthorized("Invalid email or password")
    token = create_access_token(user.id, user.email, user.role_names())
    return TokenResponse(access_token=token, expires_in_minutes=settings.jwt_expiry_minutes)


@router.get("/me", response_model=UserOut)
def me(user: UserDep) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=user.role_names(),
        department=user.department,
    )
