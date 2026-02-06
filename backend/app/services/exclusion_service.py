"""Service functions for managing exclusion rules."""

import ipaddress
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import IOC, Exclusion, ExclusionType, ListIOC
from app.services.validation import ValidationError


class ExclusionError(Exception):
    """Base exception for exclusion operations."""
    pass


class BuiltinExclusionError(ExclusionError):
    """Raised when trying to modify a builtin exclusion."""
    pass


class DuplicateExclusionError(ExclusionError):
    """Raised when exclusion already exists."""
    pass


async def get_all_exclusions(db: AsyncSession) -> dict[str, list[Exclusion]]:
    """
    Get all exclusions grouped by builtin vs user-defined.

    Returns:
        Dict with 'builtin' and 'user_defined' lists of Exclusion objects.
    """
    result = await db.execute(select(Exclusion).order_by(Exclusion.value))
    exclusions = result.scalars().all()

    return {
        "builtin": [e for e in exclusions if e.is_builtin],
        "user_defined": [e for e in exclusions if not e.is_builtin],
    }


async def preview_exclusion_conflicts(
    db: AsyncSession,
    value: str,
    excl_type: str,
) -> list[dict]:
    """
    Find existing IOCs that would conflict with a proposed exclusion.

    Returns:
        List of dicts with 'value', 'type', and 'lists' for each conflicting IOC.
    """
    # Get all IOCs with their list associations
    result = await db.execute(
        select(IOC)
        .options(selectinload(IOC.list_iocs).selectinload(ListIOC.list))
    )
    all_iocs = result.scalars().all()

    conflicts = []
    for ioc in all_iocs:
        if _ioc_matches_exclusion(ioc.value, str(ioc.type), value, excl_type):
            conflicts.append({
                "value": ioc.value,
                "type": str(ioc.type),
                "lists": [li.list.slug for li in ioc.list_iocs],
            })

    return conflicts


def _ioc_matches_exclusion(
    ioc_value: str,
    ioc_type: str,
    excl_value: str,
    excl_type: str,
) -> bool:
    """Check if an IOC matches an exclusion pattern."""
    excl_value_lower = excl_value.lower()

    # CIDR check
    if excl_type == "cidr" and ioc_type == "ip":
        try:
            network = ipaddress.ip_network(excl_value_lower, strict=False)
            try:
                ip = ipaddress.ip_address(ioc_value)
                if ip in network:
                    return True
            except ValueError:
                try:
                    ioc_network = ipaddress.ip_network(ioc_value, strict=False)
                    if ioc_network.subnet_of(network):
                        return True
                except ValueError:
                    pass
        except ValueError:
            pass

    # Wildcard domain check
    if excl_type == "wildcard" and ioc_type in ("domain", "wildcard"):
        if excl_value_lower.startswith("*."):
            suffix = excl_value_lower[1:]  # ".internal.corp"
            if ioc_value.endswith(suffix):
                return True

    # Exact domain match
    if excl_type == "domain" and ioc_type == "domain":
        if ioc_value == excl_value_lower:
            return True

    # Exact IP match
    if excl_type == "ip" and ioc_type == "ip":
        if ioc_value == excl_value_lower:
            return True

    return False


def detect_exclusion_type(value: str) -> str | None:
    """Detect the type of exclusion pattern."""
    value = value.strip().lower()

    # Try as IP
    try:
        ipaddress.ip_address(value)
        return "ip"
    except ValueError:
        pass

    # Try as CIDR
    try:
        ipaddress.ip_network(value, strict=False)
        # Only return cidr if it's actually a network (has /)
        if "/" in value:
            return "cidr"
        else:
            return "ip"
    except ValueError:
        pass

    # Wildcard domain
    if value.startswith("*."):
        return "wildcard"

    # Regular domain (simple check)
    if "." in value and not value.startswith("."):
        return "domain"

    return None


async def add_exclusion(
    db: AsyncSession,
    value: str,
    reason: str,
    purge_conflicts: bool = False,
) -> dict:
    """
    Add a custom exclusion rule.

    Returns:
        Dict with 'exclusion' and 'purged' (list of purged IOCs if purge_conflicts).
    """
    from app.services.edl_generator import generate_edl_file

    # Validate and determine type
    value = value.strip()
    excl_type = detect_exclusion_type(value)
    if excl_type is None:
        raise ValidationError(f"Invalid exclusion pattern: {value}")

    # Check for duplicate
    existing = await db.execute(
        select(Exclusion).where(Exclusion.value == value.lower())
    )
    if existing.scalar_one_or_none():
        raise DuplicateExclusionError(f"Exclusion '{value}' already exists")

    # Get conflicts before adding
    conflicts = await preview_exclusion_conflicts(db, value, excl_type) if purge_conflicts else []

    # Create exclusion
    exclusion = Exclusion(
        value=value.lower(),
        type=ExclusionType(excl_type),
        reason=reason,
        is_builtin=False,
    )
    db.add(exclusion)

    # Purge conflicts if requested
    purged = []
    if purge_conflicts and conflicts:
        affected_slugs = set()
        for conflict in conflicts:
            # Delete IOC
            ioc_result = await db.execute(
                select(IOC)
                .options(selectinload(IOC.list_iocs).selectinload(ListIOC.list))
                .where(IOC.value == conflict["value"])
            )
            ioc = ioc_result.scalar_one_or_none()
            if ioc:
                for li in ioc.list_iocs:
                    affected_slugs.add(li.list.slug)
                await db.delete(ioc)
                purged.append(conflict)

        await db.commit()

        # Regenerate affected EDLs
        for slug in affected_slugs:
            await generate_edl_file(db, slug)
    else:
        await db.commit()

    return {"exclusion": exclusion, "purged": purged}


async def remove_exclusion(db: AsyncSession, value: str) -> bool:
    """
    Remove a user-defined exclusion.

    Returns:
        True if removed, False if not found.

    Raises:
        BuiltinExclusionError: If trying to remove a builtin exclusion.
    """
    result = await db.execute(
        select(Exclusion).where(Exclusion.value == value.strip().lower())
    )
    exclusion = result.scalar_one_or_none()

    if not exclusion:
        return False

    if exclusion.is_builtin:
        raise BuiltinExclusionError(f"Cannot remove builtin exclusion: {value}")

    await db.delete(exclusion)
    await db.commit()
    return True
