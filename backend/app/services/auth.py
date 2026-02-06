import re
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import UIUser

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AccountLockedError(Exception):
    """Raised when account is locked due to too many failed attempts."""
    def __init__(self, locked_until: datetime):
        self.locked_until = locked_until
        super().__init__(f"Account locked until {locked_until}")


MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

ALGORITHM = "HS256"


def validate_password_complexity(password: str) -> None:
    """Validate password meets minimum length requirement.

    Raises:
        ValueError: If password is too short.
    """
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> UIUser | None:
    result = await db.execute(
        select(UIUser).where(UIUser.username == username)
    )
    user = result.scalar_one_or_none()

    if user and verify_password(password, user.hashed_password):
        return user

    return None


async def authenticate_user_with_lockout(
    db: AsyncSession,
    username: str,
    password: str,
) -> UIUser | None:
    """Authenticate user with account lockout protection.

    Raises:
        AccountLockedError: If account is currently locked.

    Returns:
        User if authenticated, None if invalid credentials.
    """
    result = await db.execute(
        select(UIUser).where(UIUser.username == username)
    )
    user = result.scalar_one_or_none()

    if not user:
        return None

    # Check if account is locked
    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until > now:
        raise AccountLockedError(user.locked_until)

    # Clear expired lockout
    if user.locked_until and user.locked_until <= now:
        user.locked_until = None
        user.failed_attempts = 0

    # Verify password
    if verify_password(password, user.hashed_password):
        # Success - reset failed attempts
        user.failed_attempts = 0
        user.locked_until = None
        await db.commit()
        return user

    # Failed login - increment counter
    user.failed_attempts += 1

    # Lock account after max attempts
    if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)

    await db.commit()
    return None
