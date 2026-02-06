from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemConfig


async def get_system_config(db: AsyncSession, key: str, default: str = "") -> str:
    """Get a system config value by key, returning default if not found."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()
    return config.value if config else default


async def set_system_config(db: AsyncSession, key: str, value: str) -> None:
    """Set a system config value, creating or updating as needed."""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    config = result.scalar_one_or_none()

    if config:
        config.value = value
    else:
        db.add(SystemConfig(key=key, value=value))

    await db.commit()


async def get_edl_base_url(db: AsyncSession) -> str:
    """Get the full EDL base URL from config."""
    host = await get_system_config(db, "edl_host", "localhost")
    port = await get_system_config(db, "edl_port", "8081")
    return f"https://{host}:{port}"
