from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import List, ListIOC


async def generate_edl_file(db: AsyncSession, list_slug: str) -> str | None:
    """
    Generate EDL text file for a list.

    Returns the file path if successful, None if list not found.
    """
    result = await db.execute(
        select(List)
        .options(selectinload(List.list_iocs).selectinload(ListIOC.ioc))
        .where(List.slug == list_slug)
    )
    list_obj = result.scalar_one_or_none()

    if not list_obj:
        return None

    # Generate content - one IOC value per line
    lines = [li.ioc.value for li in list_obj.list_iocs]
    content = "\n".join(sorted(lines))

    # Write to file
    output_dir = Path(settings.edl_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    file_path = output_dir / list_slug
    file_path.write_text(content)

    return str(file_path)


async def generate_all_edl_files(db: AsyncSession) -> list[str]:
    """Generate EDL files for all lists. Returns list of file paths."""
    result = await db.execute(select(List.slug))
    slugs = [row[0] for row in result.all()]

    paths = []
    for slug in slugs:
        path = await generate_edl_file(db, slug)
        if path:
            paths.append(path)

    return paths


async def delete_edl_file(list_slug: str) -> bool:
    """Delete EDL file for a list. Returns True if deleted."""
    file_path = Path(settings.edl_output_dir) / list_slug
    if file_path.exists():
        file_path.unlink()
        return True
    return False
