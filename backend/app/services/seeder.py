from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.config import settings
from app.models import UIUser, ListCredential, Exclusion, SystemConfig
from app.models.user import UserRole
from app.services.htpasswd import sync_htpasswd

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Built-in exclusions (use string values to match PostgreSQL enum)
BUILTIN_EXCLUSIONS = [
    # Top-level domains
    {"value": "com", "type": "domain", "reason": "Top-level domain"},
    {"value": "org", "type": "domain", "reason": "Top-level domain"},
    {"value": "net", "type": "domain", "reason": "Top-level domain"},
    {"value": "edu", "type": "domain", "reason": "Top-level domain"},
    {"value": "gov", "type": "domain", "reason": "Top-level domain"},
    {"value": "io", "type": "domain", "reason": "Top-level domain"},
    {"value": "co", "type": "domain", "reason": "Top-level domain"},
    # RFC1918 private ranges
    {"value": "10.0.0.0/8", "type": "cidr", "reason": "RFC1918 private range"},
    {"value": "172.16.0.0/12", "type": "cidr", "reason": "RFC1918 private range"},
    {"value": "192.168.0.0/16", "type": "cidr", "reason": "RFC1918 private range"},
    # Localhost
    {"value": "127.0.0.0/8", "type": "cidr", "reason": "Localhost range"},
    {"value": "localhost", "type": "domain", "reason": "Localhost"},
]


async def seed_system_config(db: AsyncSession) -> None:
    """Seed default system configuration values."""
    import os

    # Get port from environment, default to 8081
    default_port = os.environ.get("NOPE_PORT", "8081")

    defaults = {
        "edl_host": "localhost",
        "edl_port": default_port,
    }

    for key, value in defaults.items():
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )
        if result.scalar_one_or_none() is None:
            db.add(SystemConfig(key=key, value=value))

    await db.commit()


async def seed_database(db: AsyncSession) -> None:
    """Seed database with default data if empty."""

    # Create default UI admin user if none exists
    result = await db.execute(select(UIUser).limit(1))
    if result.scalar_one_or_none() is None:
        admin = UIUser(
            username=settings.default_admin_user,
            hashed_password=pwd_context.hash(settings.default_admin_password),
            role=UserRole.admin,
        )
        db.add(admin)

    # Create default EDL credential if none exists
    result = await db.execute(select(ListCredential).limit(1))
    if result.scalar_one_or_none() is None:
        edl_cred = ListCredential(
            username=settings.default_edl_user,
            hashed_password=pwd_context.hash(settings.default_edl_password),
        )
        db.add(edl_cred)

    # Create built-in exclusions if none exist
    result = await db.execute(select(Exclusion).where(Exclusion.is_builtin == True).limit(1))
    if result.scalar_one_or_none() is None:
        for excl_data in BUILTIN_EXCLUSIONS:
            exclusion = Exclusion(
                value=excl_data["value"],
                type=excl_data["type"],
                reason=excl_data["reason"],
                is_builtin=True,
            )
            db.add(exclusion)

    await db.commit()

    # Seed system configuration defaults
    await seed_system_config(db)

    # Sync htpasswd file for NGINX
    await sync_htpasswd(db)
