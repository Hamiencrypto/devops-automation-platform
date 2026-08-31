"""Authentication endpoints — register, login, and current-user probe."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    get_current_user_optional,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserOut

router = APIRouter()


@router.post("/register", response_model=UserOut, summary="Register a new user")
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    requester: User | None = Depends(get_current_user_optional),
) -> User:
    """Create a new user account.

    Security rules:
      * The very first user ever registered is auto-promoted to ADMIN.
      * After that, self-registration only allows DEVELOPER or VIEWER roles.
      * Only an existing ADMIN can create another ADMIN.
    """
    from app.models import UserRole

    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    # Determine the role to assign
    requested_role = payload.role
    real_user_count = db.query(User).filter(User.username != "system").count()
    if real_user_count == 0:
        # First real user on the system — bootstrap as admin
        final_role = UserRole.ADMIN
    elif requested_role == UserRole.ADMIN:
        # Promoting to admin requires an existing admin caller
        if not requester or requester.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Only an administrator can create another administrator",
            )
        final_role = UserRole.ADMIN
    else:
        final_role = requested_role

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=final_role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token, summary="Login and get JWT token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is disabled")
    token = create_access_token(subject=user.username, role=user.role.value)
    return Token(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserOut, summary="Who am I")
def me(
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> User:
    """Return the currently authenticated user.

    Behavior:
      * If `ENABLE_AUTH=false`, always return the implicit system user.
      * If auth is enabled and a valid Bearer token is provided, return the
        matching user.
      * Otherwise return 401 so the frontend can route to /login.
    """
    if not settings.ENABLE_AUTH:
        # Re-use get_current_user which provisions a system user when auth off
        return get_current_user(token=None, db=db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
