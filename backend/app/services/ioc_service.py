from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import IOC, List, ListIOC, IOCComment, Exclusion
from app.services.validation import validate_ioc, check_exclusions, is_ioc_type_allowed, ValidationError, ExclusionMatch
from app.services.edl_generator import generate_edl_file
from app.services.audit_service import (
    log_ioc_created,
    log_ioc_added_to_list,
    log_ioc_removed_from_list,
)


class IOCServiceError(Exception):
    """Base exception for IOC service errors."""
    pass


class IOCExcludedError(IOCServiceError):
    """Raised when IOC matches an exclusion rule."""
    def __init__(self, match: ExclusionMatch):
        self.match = match
        super().__init__(f"IOC excluded: {match.reason}")


class IOCValidationError(IOCServiceError):
    """Raised when IOC fails validation."""
    pass


class ListNotFoundError(IOCServiceError):
    """Raised when target list doesn't exist."""
    pass


class ListTypeMismatchError(IOCServiceError):
    """Raised when IOC type is not allowed for a list's type."""
    def __init__(self, ioc_type: str, list_type: str):
        self.ioc_type = ioc_type
        self.list_type = list_type
        super().__init__(f"Cannot add {ioc_type} IOC to a {list_type}-only list")


async def add_ioc(
    db: AsyncSession,
    value: str,
    list_slugs: list[str],
    comment: str | None = None,
    source: str | None = None,
    added_by: str | None = None,
) -> IOC:
    """
    Add an IOC to one or more lists.

    - Validates the IOC format
    - Checks against exclusion rules
    - Creates or retrieves existing IOC
    - Links to specified lists
    - Adds optional comment
    """
    # Validate IOC
    try:
        normalized_value, ioc_type = validate_ioc(value)
    except ValidationError as e:
        raise IOCValidationError(str(e))

    # Check exclusions
    exclusions_result = await db.execute(select(Exclusion))
    exclusions = list(exclusions_result.scalars().all())

    match = check_exclusions(normalized_value, ioc_type.value, exclusions)
    if match:
        raise IOCExcludedError(match)

    # Get target lists (skip if none specified)
    if list_slugs:
        lists_result = await db.execute(
            select(List).where(List.slug.in_(list_slugs))
        )
        lists = {lst.slug: lst for lst in lists_result.scalars().all()}

        missing = set(list_slugs) - set(lists.keys())
        if missing:
            raise ListNotFoundError(f"Lists not found: {', '.join(missing)}")

        # Validate IOC type is allowed for each list
        for lst in lists.values():
            if not is_ioc_type_allowed(ioc_type.value, lst.list_type):
                raise ListTypeMismatchError(ioc_type.value, lst.list_type)
    else:
        lists = {}

    # Get or create IOC
    ioc_result = await db.execute(
        select(IOC)
        .options(selectinload(IOC.list_iocs))
        .where(IOC.value == normalized_value)
    )
    ioc = ioc_result.scalar_one_or_none()

    is_new = ioc is None
    if is_new:
        ioc = IOC(value=normalized_value, type=ioc_type.value)
        db.add(ioc)
        await db.flush()  # Get ID
        await log_ioc_created(db, ioc.id, added_by)

    # Link to lists (skip if already linked)
    # For new IOCs, there are no existing links; for existing IOCs, list_iocs was eagerly loaded
    existing_list_ids = set() if is_new else {li.list_id for li in ioc.list_iocs}

    for slug, lst in lists.items():
        if lst.id not in existing_list_ids:
            list_ioc = ListIOC(
                list_id=lst.id,
                ioc_id=ioc.id,
                added_by=added_by,
            )
            db.add(list_ioc)
            await log_ioc_added_to_list(db, ioc.id, lst.id, added_by)

    # Add comment if provided
    if comment:
        ioc_comment = IOCComment(
            ioc_id=ioc.id,
            comment=comment,
            source=source,
        )
        db.add(ioc_comment)

    await db.commit()
    await db.refresh(ioc)

    # Regenerate EDL files for affected lists
    for slug in list_slugs:
        await generate_edl_file(db, slug)

    return ioc


async def remove_ioc_from_list(
    db: AsyncSession,
    ioc_id: int,
    list_slug: str,
) -> bool:
    """Remove an IOC from a specific list. Returns True if removed."""
    result = await db.execute(
        select(ListIOC)
        .join(List)
        .where(ListIOC.ioc_id == ioc_id, List.slug == list_slug)
    )
    list_ioc = result.scalar_one_or_none()

    if list_ioc:
        list_id = list_ioc.list_id
        await log_ioc_removed_from_list(db, ioc_id, list_id)
        await db.delete(list_ioc)
        await db.commit()
        # Regenerate the affected list
        await generate_edl_file(db, list_slug)
        return True

    return False


async def delete_ioc(db: AsyncSession, ioc_id: int) -> bool:
    """Delete an IOC entirely. Returns True if deleted."""
    # Get IOC with its list associations
    result = await db.execute(
        select(IOC)
        .options(selectinload(IOC.list_iocs).selectinload(ListIOC.list))
        .where(IOC.id == ioc_id)
    )
    ioc = result.scalar_one_or_none()

    if ioc:
        # Get list slugs before deletion
        affected_slugs = [li.list.slug for li in ioc.list_iocs]

        await db.delete(ioc)
        await db.commit()

        # Regenerate affected lists
        for slug in affected_slugs:
            await generate_edl_file(db, slug)

        return True

    return False


async def search_iocs(
    db: AsyncSession,
    query: str,
    limit: int = 50,
    list_slug: str | None = None,
) -> list[IOC]:
    """Search IOCs by value (partial match), optionally filtered by list."""
    stmt = (
        select(IOC)
        .options(
            selectinload(IOC.list_iocs).selectinload(ListIOC.list),
            selectinload(IOC.comments),
        )
        .where(IOC.value.ilike(f"%{query}%"))
    )

    if list_slug:
        stmt = stmt.join(IOC.list_iocs).join(ListIOC.list).where(List.slug == list_slug).distinct()

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_iocs_for_list(
    db: AsyncSession,
    list_slug: str,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[IOC] | None, int]:
    """
    Get paginated IOCs for a specific list.

    Returns:
        Tuple of (iocs, total_count). iocs is None if list not found.
    """
    # Verify list exists
    list_result = await db.execute(select(List).where(List.slug == list_slug))
    lst = list_result.scalar_one_or_none()

    if not lst:
        return None, 0

    # Get total count
    count_result = await db.execute(
        select(func.count())
        .select_from(ListIOC)
        .where(ListIOC.list_id == lst.id)
    )
    total = count_result.scalar()

    # Get paginated IOCs
    result = await db.execute(
        select(IOC)
        .join(ListIOC)
        .where(ListIOC.list_id == lst.id)
        .order_by(IOC.value)
        .offset(offset)
        .limit(limit)
    )
    iocs = list(result.scalars().all())

    return iocs, total


async def add_ioc_comment(
    db: AsyncSession,
    value: str,
    comment: str,
    source: str | None = None,
) -> bool:
    """
    Add a comment to an existing IOC.

    Returns:
        True if comment added, False if IOC not found.
    """
    result = await db.execute(select(IOC).where(IOC.value == value.strip().lower()))
    ioc = result.scalar_one_or_none()

    if not ioc:
        return False

    ioc_comment = IOCComment(
        ioc_id=ioc.id,
        comment=comment,
        source=source,
    )
    db.add(ioc_comment)
    await db.commit()
    return True


async def bulk_add_iocs(
    db: AsyncSession,
    values: list[str],
    list_slug: str,
    comment: str | None = None,
    source: str | None = None,
    added_by: str | None = None,
) -> dict[str, list]:
    """
    Add multiple IOCs to a list.

    Returns:
        Dict with 'added', 'skipped' (duplicates), and 'failed' (with reasons) lists.
    """
    # Verify list exists
    list_result = await db.execute(select(List).where(List.slug == list_slug))
    lst = list_result.scalar_one_or_none()
    if not lst:
        raise ListNotFoundError(f"List '{list_slug}' not found")

    # Load exclusions once
    exclusions_result = await db.execute(select(Exclusion))
    exclusions = list(exclusions_result.scalars().all())

    results = {"added": [], "skipped": [], "failed": []}

    for value in values:
        try:
            # Validate
            normalized_value, ioc_type = validate_ioc(value)

            # Check type allowed
            if not is_ioc_type_allowed(ioc_type.value, lst.list_type):
                results["failed"].append((value, f"Type {ioc_type.value} not allowed on {lst.list_type} list"))
                continue

            # Check exclusions
            match = check_exclusions(normalized_value, ioc_type.value, exclusions)
            if match:
                results["failed"].append((value, match.reason or "Excluded"))
                continue

            # Get or create IOC
            ioc_result = await db.execute(
                select(IOC)
                .options(selectinload(IOC.list_iocs))
                .where(IOC.value == normalized_value)
            )
            ioc = ioc_result.scalar_one_or_none()

            is_new = ioc is None
            if is_new:
                ioc = IOC(value=normalized_value, type=ioc_type.value)
                db.add(ioc)
                await db.flush()
                await log_ioc_created(db, ioc.id, added_by)

            # Check if already on list
            existing_list_ids = set() if is_new else {li.list_id for li in ioc.list_iocs}
            if lst.id in existing_list_ids:
                results["skipped"].append(normalized_value)
                continue

            # Link to list
            list_ioc = ListIOC(list_id=lst.id, ioc_id=ioc.id, added_by=added_by)
            db.add(list_ioc)
            await log_ioc_added_to_list(db, ioc.id, lst.id, added_by)

            # Add comment if provided
            if comment:
                ioc_comment = IOCComment(ioc_id=ioc.id, comment=comment, source=source)
                db.add(ioc_comment)

            results["added"].append(normalized_value)

        except ValidationError as e:
            results["failed"].append((value, str(e)))

    await db.commit()

    # Regenerate EDL
    await generate_edl_file(db, list_slug)

    return results


async def bulk_remove_iocs(
    db: AsyncSession,
    values: list[str],
    list_slug: str | None = None,
    all_lists: bool = False,
) -> dict[str, list]:
    """
    Remove multiple IOCs from list(s).

    Returns:
        Dict with 'removed' and 'not_found' lists.
    """
    results = {"removed": [], "not_found": []}
    affected_slugs = set()

    for value in values:
        normalized = value.strip().lower()

        # Find the IOC
        ioc_result = await db.execute(
            select(IOC)
            .options(selectinload(IOC.list_iocs).selectinload(ListIOC.list))
            .where(IOC.value == normalized)
        )
        ioc = ioc_result.scalar_one_or_none()

        if not ioc:
            results["not_found"].append(value)
            continue

        if all_lists:
            # Get affected slugs before deletion
            for li in ioc.list_iocs:
                affected_slugs.add(li.list.slug)
            await db.delete(ioc)
            results["removed"].append(value)
        elif list_slug:
            # Remove from specific list
            found = False
            for li in ioc.list_iocs:
                if li.list.slug == list_slug:
                    affected_slugs.add(list_slug)
                    await log_ioc_removed_from_list(db, ioc.id, li.list_id)
                    await db.delete(li)
                    results["removed"].append(value)
                    found = True
                    break
            if not found:
                results["not_found"].append(value)

    await db.commit()

    # Regenerate affected EDLs
    for slug in affected_slugs:
        await generate_edl_file(db, slug)

    return results
