from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ListCredential


async def sync_htpasswd(db: AsyncSession) -> None:
    """
    Sync list credentials to htpasswd file for NGINX basic auth.

    The htpasswd file is written to the EDL output directory so NGINX can access it.
    Passlib bcrypt hashes are compatible with Apache htpasswd format.
    """
    result = await db.execute(select(ListCredential))
    credentials = result.scalars().all()

    htpasswd_path = Path(settings.edl_output_dir) / ".htpasswd"

    # Ensure directory exists
    htpasswd_path.parent.mkdir(parents=True, exist_ok=True)

    # Write htpasswd file
    # Format: username:hashed_password (bcrypt hashes from passlib work with nginx)
    lines = []
    for cred in credentials:
        lines.append(f"{cred.username}:{cred.hashed_password}")

    htpasswd_path.write_text("\n".join(lines) + "\n" if lines else "")
