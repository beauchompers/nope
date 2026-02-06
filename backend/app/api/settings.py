from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.db import get_db
from app.models import UIUser, ListCredential, Exclusion, APIKey
from app.models.user import UserRole
from app.api.auth import get_current_user, require_admin
from app.services.htpasswd import sync_htpasswd
from app.services.auth import validate_password_complexity
from app.services.encryption import generate_api_key
from app.config import settings as app_settings
from app.services.config_service import get_system_config, set_system_config, get_edl_base_url

router = APIRouter(prefix="/api/settings", tags=["settings"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Schemas ---

class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole = UserRole.analyst  # Default to analyst


class UserUpdate(BaseModel):
    role: UserRole | None = None
    password: str | None = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole

    class Config:
        from_attributes = True


class CredentialCreate(BaseModel):
    username: str
    password: str


class CredentialResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class ExclusionCreate(BaseModel):
    value: str
    type: str
    reason: str | None = None


class ExclusionResponse(BaseModel):
    id: int
    value: str
    type: str
    reason: str | None
    is_builtin: bool

    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    name: str


class APIKeyResponse(BaseModel):
    id: int
    name: str
    key: str
    created_at: datetime
    last_used_at: datetime | None

    class Config:
        from_attributes = True


class EdlUrlResponse(BaseModel):
    host: str
    port: int
    full_url: str


class EdlUrlUpdate(BaseModel):
    host: str
    port: int


# --- UI Users ---

@router.get("/users", response_model=list[UserResponse])
async def get_users(
    db: AsyncSession = Depends(get_db),
    _: UIUser = Depends(require_admin),
):
    """Get all UI users."""
    result = await db.execute(select(UIUser).order_by(UIUser.username))
    return list(result.scalars().all())


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: UIUser = Depends(require_admin),
):
    """Create a new UI user."""
    # Validate password complexity
    try:
        validate_password_complexity(data.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check for duplicate
    existing = await db.execute(select(UIUser).where(UIUser.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = UIUser(
        username=data.username,
        hashed_password=pwd_context.hash(data.password),
        role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UIUser = Depends(require_admin),
):
    """Delete a UI user."""
    result = await db.execute(select(UIUser).where(UIUser.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent deleting yourself
    if user.username == current_user.username:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    await db.delete(user)
    await db.commit()


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UIUser = Depends(require_admin),
):
    """Update a UI user's role or password."""
    result = await db.execute(select(UIUser).where(UIUser.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent demoting yourself from admin
    if user.username == current_user.username and data.role and data.role != UserRole.admin:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    if data.role is not None:
        user.role = data.role

    if data.password is not None:
        try:
            validate_password_complexity(data.password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        user.hashed_password = pwd_context.hash(data.password)

    await db.commit()
    await db.refresh(user)
    return user


# --- EDL Credential (Single Global Credential) ---

class CredentialUpdate(BaseModel):
    username: str
    password: str | None = None  # If None, only update username


@router.get("/credential", response_model=CredentialResponse)
async def get_credential(
    db: AsyncSession = Depends(get_db),
    _: UIUser = Depends(require_admin),
):
    """Get the single EDL credential."""
    result = await db.execute(select(ListCredential).limit(1))
    credential = result.scalar_one_or_none()

    if not credential:
        raise HTTPException(status_code=404, detail="No EDL credential configured")

    return credential


@router.put("/credential", response_model=CredentialResponse)
async def update_credential(
    data: CredentialUpdate,
    db: AsyncSession = Depends(get_db),
    _: UIUser = Depends(require_admin),
):
    """Update the single EDL credential (or create if none exists)."""
    result = await db.execute(select(ListCredential).limit(1))
    credential = result.scalar_one_or_none()

    if credential:
        # Update existing
        credential.username = data.username
        if data.password:
            credential.hashed_password = pwd_context.hash(data.password)
    else:
        # Create new (shouldn't happen if seeder ran, but handle gracefully)
        if not data.password:
            raise HTTPException(status_code=400, detail="Password required for new credential")
        credential = ListCredential(
            username=data.username,
            hashed_password=pwd_context.hash(data.password),
        )
        db.add(credential)

    await db.commit()
    await db.refresh(credential)

    # Sync htpasswd file
    await sync_htpasswd(db)

    return credential


# --- Exclusions ---

@router.get("/exclusions", response_model=list[ExclusionResponse])
async def get_exclusions(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Get all exclusions."""
    result = await db.execute(select(Exclusion).order_by(Exclusion.value))
    return list(result.scalars().all())


@router.post("/exclusions", response_model=ExclusionResponse, status_code=status.HTTP_201_CREATED)
async def create_exclusion(
    data: ExclusionCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Create a new exclusion."""
    # Validate type
    valid_types = ["ip", "domain", "cidr", "wildcard"]
    if data.type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {valid_types}")

    # Validate value format based on type
    value = data.value.strip()
    if not value:
        raise HTTPException(status_code=400, detail="Value cannot be empty")

    # Wildcard patterns should use wildcard type
    if "*" in value and data.type != "wildcard":
        raise HTTPException(
            status_code=400,
            detail="Wildcard patterns (containing *) must use 'wildcard' type"
        )

    # Wildcard type must have wildcard pattern
    if data.type == "wildcard" and not value.startswith("*."):
        raise HTTPException(
            status_code=400,
            detail="Wildcard exclusions must start with '*.' (e.g., *.example.com)"
        )

    # Check for duplicate
    existing = await db.execute(select(Exclusion).where(Exclusion.value == value))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Exclusion already exists")

    exclusion = Exclusion(
        value=value,
        type=data.type,
        reason=data.reason,
        is_builtin=False,
    )
    db.add(exclusion)
    await db.commit()
    await db.refresh(exclusion)
    return exclusion


@router.delete("/exclusions/{exclusion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exclusion(
    exclusion_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Delete an exclusion."""
    result = await db.execute(select(Exclusion).where(Exclusion.id == exclusion_id))
    exclusion = result.scalar_one_or_none()

    if not exclusion:
        raise HTTPException(status_code=404, detail="Exclusion not found")

    if exclusion.is_builtin:
        raise HTTPException(status_code=400, detail="Cannot delete built-in exclusions")

    await db.delete(exclusion)
    await db.commit()


# --- API Keys ---

@router.get("/api-keys", response_model=list[APIKeyResponse])
async def get_api_keys(
    db: AsyncSession = Depends(get_db),
    _: UIUser = Depends(require_admin),
):
    """Get all API keys (admin only)."""
    result = await db.execute(select(APIKey).order_by(APIKey.name))
    api_keys = result.scalars().all()

    return [
        APIKeyResponse(
            id=api_key.id,
            name=api_key.name,
            key=api_key.key,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
        )
        for api_key in api_keys
    ]


@router.post("/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    _: UIUser = Depends(require_admin),
):
    """Create a new API key."""
    # Validate name
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    # Check for duplicate name
    existing = await db.execute(select(APIKey).where(APIKey.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="API key name already exists")

    # Generate the key
    key = generate_api_key()

    api_key = APIKey(
        name=name,
        key=key,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=api_key.key,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
    )


@router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    api_key_id: int,
    db: AsyncSession = Depends(get_db),
    _: UIUser = Depends(require_admin),
):
    """Delete an API key."""
    result = await db.execute(select(APIKey).where(APIKey.id == api_key_id))
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    await db.delete(api_key)
    await db.commit()


# --- EDL URL Configuration ---

@router.get("/edl-url", response_model=EdlUrlResponse)
async def get_edl_url(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Get the current EDL URL configuration."""
    host = await get_system_config(db, "edl_host", "localhost")
    port_str = await get_system_config(db, "edl_port", "8081")
    port = int(port_str)
    full_url = f"https://{host}:{port}"

    return EdlUrlResponse(host=host, port=port, full_url=full_url)


@router.put("/edl-url", response_model=EdlUrlResponse)
async def update_edl_url(
    data: EdlUrlUpdate,
    db: AsyncSession = Depends(get_db),
    _: UIUser = Depends(require_admin),
):
    """Update the EDL URL configuration (admin only)."""
    # Validate host - strip any scheme if user pastes full URL
    host = data.host.strip()
    if host.startswith("https://"):
        host = host[8:]
    elif host.startswith("http://"):
        host = host[7:]

    # Remove trailing slash or port from host
    if "/" in host:
        host = host.split("/")[0]
    if ":" in host:
        host = host.split(":")[0]

    if not host:
        raise HTTPException(status_code=400, detail="Host cannot be empty")

    # Validate port
    if data.port < 1 or data.port > 65535:
        raise HTTPException(status_code=400, detail="Port must be between 1 and 65535")

    await set_system_config(db, "edl_host", host)
    await set_system_config(db, "edl_port", str(data.port))

    full_url = f"https://{host}:{data.port}"

    return EdlUrlResponse(host=host, port=data.port, full_url=full_url)


# --- Public Config ---

class PublicConfig(BaseModel):
    edl_base_url: str


@router.get("/config", response_model=PublicConfig)
async def get_public_config(
    db: AsyncSession = Depends(get_db),
):
    """Get public configuration settings (no auth required)."""
    # Read from database, fall back to env var for backwards compatibility
    base_url = await get_edl_base_url(db)

    # If still default localhost and EDL_BASE_URL env is set, use that
    if base_url == "https://localhost:8081" and app_settings.edl_base_url:
        base_url = app_settings.edl_base_url

    return PublicConfig(edl_base_url=base_url)
