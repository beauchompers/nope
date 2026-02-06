from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ioc_audit import IOCAuditLog, IOCAuditAction


async def log_ioc_created(
    db: AsyncSession,
    ioc_id: int,
    performed_by: str | None = None,
) -> IOCAuditLog:
    """Log IOC creation event."""
    entry = IOCAuditLog(
        ioc_id=ioc_id,
        action=IOCAuditAction.CREATED.value,
        performed_by=performed_by,
    )
    db.add(entry)
    return entry


async def log_ioc_added_to_list(
    db: AsyncSession,
    ioc_id: int,
    list_id: int,
    performed_by: str | None = None,
) -> IOCAuditLog:
    """Log IOC added to list event."""
    entry = IOCAuditLog(
        ioc_id=ioc_id,
        action=IOCAuditAction.ADDED_TO_LIST.value,
        list_id=list_id,
        performed_by=performed_by,
    )
    db.add(entry)
    return entry


async def log_ioc_removed_from_list(
    db: AsyncSession,
    ioc_id: int,
    list_id: int,
    performed_by: str | None = None,
) -> IOCAuditLog:
    """Log IOC removed from list event."""
    entry = IOCAuditLog(
        ioc_id=ioc_id,
        action=IOCAuditAction.REMOVED_FROM_LIST.value,
        list_id=list_id,
        performed_by=performed_by,
    )
    db.add(entry)
    return entry


async def log_ioc_comment(
    db: AsyncSession,
    ioc_id: int,
    content: str,
    performed_by: str | None = None,
) -> IOCAuditLog:
    """Log standalone comment on IOC."""
    entry = IOCAuditLog(
        ioc_id=ioc_id,
        action=IOCAuditAction.COMMENT.value,
        content=content,
        performed_by=performed_by,
    )
    db.add(entry)
    return entry


async def log_ioc_deleted(
    db: AsyncSession,
    ioc_id: int,
    performed_by: str | None = None,
) -> IOCAuditLog:
    """Log IOC deletion event (logged before actual deletion)."""
    entry = IOCAuditLog(
        ioc_id=ioc_id,
        action=IOCAuditAction.DELETED.value,
        performed_by=performed_by,
    )
    db.add(entry)
    return entry
