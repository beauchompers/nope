from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import UIUser, UserRole
from app.services.auth import authenticate_user_with_lockout, AccountLockedError, create_access_token, decode_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await authenticate_user_with_lockout(db, form_data.username, form_data.password)
    except AccountLockedError:
        # Return generic 401 to prevent user enumeration
        # The lockout is still enforced server-side
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return Token(access_token=access_token, token_type="bearer")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    # Verify user still exists in database
    result = await db.execute(select(UIUser).where(UIUser.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return username


async def get_current_user_with_role(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UIUser:
    """Get current user with full user object including role."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    result = await db.execute(select(UIUser).where(UIUser.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


def require_role(required_role: UserRole):
    """Dependency factory that requires a specific role."""
    async def role_checker(
        current_user: UIUser = Depends(get_current_user_with_role),
    ) -> UIUser:
        # Admin can access everything
        if current_user.role == UserRole.admin:
            return current_user
        # Otherwise check specific role
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return role_checker


# Convenience dependency
require_admin = require_role(UserRole.admin)


class UserInfo(BaseModel):
    username: str


@router.get("/me", response_model=UserInfo)
async def get_me(current_user: str = Depends(get_current_user)):
    """Get current user info."""
    return UserInfo(username=current_user)
