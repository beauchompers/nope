from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import async_session_maker
from app.models import IOC, List, ListIOC
from app.services.ioc_service import (
    add_ioc,
    add_ioc_comment,
    bulk_add_iocs,
    bulk_remove_iocs,
    remove_ioc_from_list,
    delete_ioc,
    search_iocs,
    get_iocs_for_list,
    IOCExcludedError,
    IOCValidationError,
    ListNotFoundError,
)
from app.services.exclusion_service import (
    get_all_exclusions,
    preview_exclusion_conflicts,
    add_exclusion as add_exclusion_svc,
    remove_exclusion as remove_exclusion_svc,
    detect_exclusion_type,
    BuiltinExclusionError,
    DuplicateExclusionError,
)
from app.services.validation import ValidationError
from app.services.config_service import get_edl_base_url


def _get_added_by() -> str:
    """Get the added_by value for audit trail.

    Extracts the authenticated API key name from the HTTP request context
    and returns it in "mcp:{key_name}" format. Falls back to "mcp" if
    the key name is not available.
    """
    try:
        request = get_http_request()
        key_name = request.scope.get("state", {}).get("api_key_name")
        if key_name:
            return f"mcp:{key_name}"
    except RuntimeError:
        # No HTTP request context available
        pass
    return "mcp"

mcp = FastMCP("NOPE EDL Manager")


@mcp.tool()
async def block_ioc(
    value: str,
    list_slug: str,
    comment: str | None = None,
) -> str:
    """
    Add an IOC to a blocklist.

    Supports IPs, CIDR ranges (e.g., 203.0.113.0/24), domains, wildcard domains
    (e.g., *.example.com), and file hashes (SHA256, SHA1, MD5). IOC type is
    auto-detected. Private/reserved IP ranges (RFC1918, loopback, link-local)
    and TLDs are rejected per exclusion rules - use list_exclusions to see all
    rules. Adding an existing IOC is idempotent (no error, no duplicate).

    Args:
        value: The IOC to block (IP, CIDR, domain, wildcard, or hash)
        list_slug: The slug of the list to add it to
        comment: Optional reason for blocking

    Returns:
        Success message or error description
    """
    async with async_session_maker() as db:
        try:
            ioc = await add_ioc(
                db=db,
                value=value,
                list_slugs=[list_slug],
                comment=comment,
                source="mcp",
                added_by=_get_added_by(),
            )
            return f"Successfully added {ioc.value} ({ioc.type}) to list '{list_slug}'"
        except IOCValidationError as e:
            return f"Validation error: {e}"
        except IOCExcludedError as e:
            return f"Cannot block: {e.match.reason} (matches exclusion '{e.match.value}')"
        except ListNotFoundError as e:
            return f"Error: {e}"


@mcp.tool()
async def unblock_ioc(
    value: str,
    list_slug: str | None = None,
    all_lists: bool = False,
) -> str:
    """
    Remove an IOC from a specific blocklist or all blocklists.

    Supports all IOC types (IP, CIDR, domain, wildcard, hash). The IOC record
    is retained after removal and will still appear in search results. Provide
    list_slug to remove from one list, or all_lists=true to remove from all.

    Args:
        value: The IOC to unblock
        list_slug: The specific list to remove from (if not all_lists)
        all_lists: If True, remove from all lists

    Returns:
        Success message or error description
    """
    async with async_session_maker() as db:
        # Find the IOC
        result = await db.execute(
            select(IOC)
            .options(selectinload(IOC.list_iocs).selectinload(ListIOC.list))
            .where(IOC.value == value.strip().lower())
        )
        ioc = result.scalar_one_or_none()

        if not ioc:
            return f"IOC '{value}' not found"

        if all_lists:
            await delete_ioc(db, ioc.id)
            return f"Removed {value} from all lists"
        elif list_slug:
            removed = await remove_ioc_from_list(db, ioc.id, list_slug)
            if removed:
                return f"Removed {value} from list '{list_slug}'"
            else:
                return f"IOC '{value}' not found in list '{list_slug}'"
        else:
            return "Error: Must specify list_slug or set all_lists=True"


@mcp.tool()
async def search_ioc(
    value: str,
    list_slug: str | None = None,
) -> str:
    """
    Search for an IOC across all lists or a specific list.

    Supports partial matching (e.g., '203.0.113' matches both '203.0.113.50'
    and '203.0.113.0/24'). Results may include orphaned IOCs no longer on any
    list but retained in the database.

    Args:
        value: The IP, domain, or hash to search for (partial match supported)
        list_slug: Optional list slug to scope search to a specific list

    Returns:
        Information about matching IOCs including lists and comments
    """
    async with async_session_maker() as db:
        iocs = await search_iocs(db, value, list_slug=list_slug)

        if not iocs:
            return f"No IOCs found matching '{value}'"

        results = []
        for ioc in iocs:
            lists = [li.list.slug for li in ioc.list_iocs]
            comments = [c.comment for c in ioc.comments]

            result = f"- {ioc.value} ({ioc.type})"
            if lists:
                result += f"\n  Lists: {', '.join(lists)}"
            if comments:
                result += f"\n  Comments: {'; '.join(comments[:3])}"
            results.append(result)

        return f"Found {len(iocs)} IOC(s):\n" + "\n".join(results)


@mcp.tool()
async def list_lists(tag: str | None = None) -> str:
    """
    Get all blocklists with summary information.

    Lists are served as EDLs at /edl/{slug} for firewall consumption.

    Args:
        tag: Optional tag to filter lists by

    Returns:
        List of all lists (or filtered by tag) with their IOC counts
    """
    async with async_session_maker() as db:
        stmt = (
            select(List)
            .options(selectinload(List.list_iocs))
            .order_by(List.name)
        )

        if tag:
            stmt = stmt.where(List.tags.contains([tag]))

        result = await db.execute(stmt)
        lists = result.scalars().all()
        base_url = await get_edl_base_url(db)

        if not lists:
            if tag:
                return f"No lists found with tag '{tag}'."
            return "No lists found. Create one with create_list."

        lines = [f"Available lists{f' (tag: {tag})' if tag else ''}:"]
        for lst in lists:
            count = len(lst.list_iocs)
            desc = f" - {lst.description}" if lst.description else ""
            lines.append(f"- {lst.name} ({base_url}/edl/{lst.slug}): {count} IOCs{desc}")

        return "\n".join(lines)


@mcp.tool()
async def get_list(slug: str) -> str:
    """
    Get detailed information about a specific list.

    Lists are served as EDLs at /edl/{slug} for firewall consumption.

    Args:
        slug: The list slug

    Returns:
        List details including IOC count and tags
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(List)
            .options(selectinload(List.list_iocs).selectinload(ListIOC.ioc))
            .where(List.slug == slug)
        )
        lst = result.scalar_one_or_none()

        if not lst:
            return f"List '{slug}' not found"

        base_url = await get_edl_base_url(db)

        info = [
            f"Name: {lst.name}",
            f"Slug: {lst.slug}",
            f"URL: {base_url}/edl/{lst.slug}",
            f"IOC Count: {len(lst.list_iocs)}",
        ]

        if lst.description:
            info.append(f"Description: {lst.description}")
        if lst.tags:
            info.append(f"Tags: {', '.join(lst.tags)}")

        # Show first 10 IOCs
        if lst.list_iocs:
            iocs = [li.ioc.value for li in lst.list_iocs[:10]]
            info.append(f"Sample IOCs: {', '.join(iocs)}")
            if len(lst.list_iocs) > 10:
                info.append(f"  ... and {len(lst.list_iocs) - 10} more")

        return "\n".join(info)


@mcp.tool()
async def create_list(
    name: str,
    description: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """
    Create a new blocklist.

    Args:
        name: Display name for the list
        description: Optional description
        tags: Optional list of tags

    Returns:
        Success message with the list slug
    """
    async with async_session_maker() as db:
        slug = List.generate_slug(name)

        # Check for duplicate
        existing = await db.execute(select(List).where(List.slug == slug))
        if existing.scalar_one_or_none():
            return f"Error: List with slug '{slug}' already exists"

        lst = List(
            name=name,
            slug=slug,
            description=description,
            tags=tags,
        )
        db.add(lst)
        await db.commit()
        base_url = await get_edl_base_url(db)

        return f"Created list '{name}' (slug: {slug}, URL: {base_url}/edl/{slug})"


@mcp.tool()
async def delete_list(slug: str) -> str:
    """
    Delete a blocklist and remove all IOC-to-list associations.

    IOC records are retained in the database and may still appear in search
    results.

    Args:
        slug: The list slug to delete

    Returns:
        Success or error message
    """
    async with async_session_maker() as db:
        result = await db.execute(select(List).where(List.slug == slug))
        lst = result.scalar_one_or_none()

        if not lst:
            return f"List '{slug}' not found"

        await db.delete(lst)
        await db.commit()

        return f"Deleted list '{slug}'"


@mcp.tool()
async def list_iocs(
    slug: str,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """
    List all IOCs on a specific blocklist with pagination.

    Args:
        slug: The list slug
        limit: Maximum number of IOCs to return (1-500, default 100)
        offset: Number of IOCs to skip for pagination (default 0)

    Returns:
        IOC list with values, types, and total count for pagination
    """
    # Clamp limit
    limit = max(1, min(500, limit))

    async with async_session_maker() as db:
        iocs, total = await get_iocs_for_list(db, slug, limit=limit, offset=offset)

        if iocs is None:
            return f"List '{slug}' not found"

        if not iocs:
            return f"List '{slug}' has no IOCs"

        start = offset + 1
        end = offset + len(iocs)
        lines = [f"IOCs on '{slug}' (showing {start}-{end} of {total}):"]
        lines.append("")

        for ioc in iocs:
            lines.append(f"- {ioc.value} ({ioc.type})")

        if end < total:
            lines.append("")
            lines.append(f"Use offset={end} to see next page.")

        return "\n".join(lines)


@mcp.tool()
async def update_ioc(
    value: str,
    comment: str,
) -> str:
    """
    Add a comment to an existing IOC.

    Comments are append-only to preserve audit history. Each comment records
    when it was added and by whom.

    Args:
        value: The IOC value to update
        comment: Comment to add

    Returns:
        Success message or error if IOC not found
    """
    async with async_session_maker() as db:
        success = await add_ioc_comment(
            db, value, comment, source="mcp"
        )

        if success:
            return f"Comment added to {value}"
        else:
            return f"IOC '{value}' not found"


@mcp.tool()
async def update_list(
    slug: str,
    name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """
    Update a blocklist's metadata.

    Only provided fields are updated. The slug cannot be changed as it's the
    immutable identifier used in EDL URLs.

    Args:
        slug: The list slug to update
        name: New display name (optional)
        description: New description (optional)
        tags: New tags list - replaces existing tags (optional)

    Returns:
        Success message with updated fields or error
    """
    if name is None and description is None and tags is None:
        return "No updates provided. Specify name, description, or tags to update."

    async with async_session_maker() as db:
        result = await db.execute(select(List).where(List.slug == slug))
        lst = result.scalar_one_or_none()

        if not lst:
            return f"List '{slug}' not found"

        updates = []
        if name is not None:
            lst.name = name
            updates.append(f"name='{name}'")
        if description is not None:
            lst.description = description
            updates.append(f"description='{description}'")
        if tags is not None:
            lst.tags = tags
            updates.append(f"tags={tags}")

        await db.commit()

        return f"Updated list '{slug}': {', '.join(updates)}"


@mcp.tool()
async def bulk_block_ioc(
    values: list[str],
    list_slug: str,
    comment: str | None = None,
) -> str:
    """
    Add multiple IOCs to a blocklist in a single operation.

    Args:
        values: List of IOC values to add (max 500)
        list_slug: The target list slug
        comment: Optional comment applied to all IOCs

    Returns:
        Summary with counts of added, skipped (duplicates), and failed (excluded)
    """
    if len(values) > 500:
        return f"Maximum 500 IOCs per request (received {len(values)})"

    if not values:
        return "No IOCs provided"

    async with async_session_maker() as db:
        try:
            added_by = _get_added_by()
            results = await bulk_add_iocs(
                db, values, list_slug, comment=comment, source="mcp", added_by=added_by
            )

            lines = ["Bulk add complete:"]
            lines.append(f"- Added: {len(results['added'])}")
            lines.append(f"- Skipped (duplicates): {len(results['skipped'])}")
            lines.append(f"- Failed (excluded/invalid): {len(results['failed'])}")

            if results["failed"]:
                lines.append("")
                lines.append("Failed items:")
                for value, reason in results["failed"][:10]:
                    lines.append(f"  - {value}: {reason}")
                if len(results["failed"]) > 10:
                    lines.append(f"  ... and {len(results['failed']) - 10} more")

            return "\n".join(lines)

        except ListNotFoundError as e:
            return str(e)


@mcp.tool()
async def bulk_unblock_ioc(
    values: list[str],
    list_slug: str | None = None,
    all_lists: bool = False,
) -> str:
    """
    Remove multiple IOCs from blocklist(s) in a single operation.

    Args:
        values: List of IOC values to remove (max 500)
        list_slug: Remove from this specific list (if not all_lists)
        all_lists: If True, remove from all lists (deletes IOC records)

    Returns:
        Summary with counts of removed and not found
    """
    if len(values) > 500:
        return f"Maximum 500 IOCs per request (received {len(values)})"

    if not values:
        return "No IOCs provided"

    if not list_slug and not all_lists:
        return "Must specify list_slug or set all_lists=True"

    async with async_session_maker() as db:
        results = await bulk_remove_iocs(db, values, list_slug=list_slug, all_lists=all_lists)

        target = "all lists" if all_lists else f"'{list_slug}'"
        lines = [f"Bulk remove from {target} complete:"]
        lines.append(f"- Removed: {len(results['removed'])}")
        lines.append(f"- Not found: {len(results['not_found'])}")

        if results["not_found"] and len(results["not_found"]) <= 10:
            lines.append("")
            lines.append("Not found:")
            for value in results["not_found"]:
                lines.append(f"  - {value}")

        return "\n".join(lines)


@mcp.tool()
async def list_exclusions() -> str:
    """
    List all active exclusion rules that prevent IOCs from being added.

    Returns:
        All exclusions with pattern, type, reason, and whether builtin or user-defined.
    """
    async with async_session_maker() as db:
        exclusions = await get_all_exclusions(db)

        builtin = exclusions["builtin"]
        user_defined = exclusions["user_defined"]
        total = len(builtin) + len(user_defined)

        lines = [f"Exclusion rules ({total} total):", ""]

        if builtin:
            lines.append(f"Built-in ({len(builtin)}, cannot be removed):")
            for e in builtin:
                reason = f" - {e.reason}" if e.reason else ""
                lines.append(f"- {e.value} ({e.type}){reason}")
            lines.append("")

        if user_defined:
            lines.append(f"User-defined ({len(user_defined)}):")
            for e in user_defined:
                reason = f" - {e.reason}" if e.reason else ""
                lines.append(f"- {e.value} ({e.type}){reason}")
        elif not builtin:
            lines.append("No exclusion rules defined.")

        return "\n".join(lines)


@mcp.tool()
async def preview_exclusion(value: str) -> str:
    """
    Preview the impact of adding an exclusion rule without committing it.

    Shows existing IOCs that would conflict with the proposed exclusion.

    Args:
        value: Proposed exclusion pattern (IP, CIDR, domain, wildcard)

    Returns:
        List of conflicting IOCs with their list associations, or confirmation if none
    """
    excl_type = detect_exclusion_type(value)
    if excl_type is None:
        return f"Invalid exclusion pattern: '{value}'"

    async with async_session_maker() as db:
        conflicts = await preview_exclusion_conflicts(db, value, excl_type)

        if not conflicts:
            return f"Preview: Adding exclusion '{value}'\n\nNo conflicts with existing IOCs. Safe to add."

        lines = [f"Preview: Adding exclusion '{value}'", ""]
        lines.append(f"Would conflict with {len(conflicts)} existing IOC(s):")

        for c in conflicts[:20]:  # Show first 20
            lists_str = ", ".join(c["lists"]) if c["lists"] else "(no lists)"
            lines.append(f"- {c['value']} ({c['type']}) on lists: {lists_str}")

        if len(conflicts) > 20:
            lines.append(f"... and {len(conflicts) - 20} more")

        lines.append("")
        lines.append("Use add_exclusion with purge_conflicts=true to add and remove conflicts,")
        lines.append("or purge_conflicts=false to add exclusion only (existing IOCs remain).")

        return "\n".join(lines)


@mcp.tool()
async def add_exclusion(
    value: str,
    reason: str,
    purge_conflicts: bool = False,
) -> str:
    """
    Add a custom exclusion rule to prevent matching IOCs from being blocked.

    Args:
        value: Pattern to exclude (IP, CIDR, domain, wildcard) - type auto-detected
        reason: Human-readable reason for this exclusion
        purge_conflicts: If True, remove existing IOCs matching this pattern from all lists

    Returns:
        Success message, optionally with list of purged IOCs
    """
    async with async_session_maker() as db:
        try:
            result = await add_exclusion_svc(db, value, reason, purge_conflicts=purge_conflicts)

            lines = [f"Added exclusion '{result['exclusion'].value}' ({result['exclusion'].type})"]
            lines.append(f"Reason: {reason}")

            if result["purged"]:
                lines.append("")
                lines.append(f"Purged {len(result['purged'])} conflicting IOC(s):")
                for p in result["purged"][:10]:
                    lists_str = ", ".join(p["lists"]) if p["lists"] else "(no lists)"
                    lines.append(f"- {p['value']} removed from: {lists_str}")
                if len(result["purged"]) > 10:
                    lines.append(f"... and {len(result['purged']) - 10} more")

            return "\n".join(lines)

        except DuplicateExclusionError as e:
            return str(e)
        except ValidationError as e:
            return f"Invalid pattern: {e}"


@mcp.tool()
async def remove_exclusion(value: str) -> str:
    """
    Remove a user-defined exclusion rule. Built-in exclusions cannot be removed.

    Args:
        value: The exclusion pattern to remove

    Returns:
        Success message or error if not found or built-in
    """
    async with async_session_maker() as db:
        try:
            removed = await remove_exclusion_svc(db, value)

            if removed:
                return f"Removed exclusion '{value}'"
            else:
                return f"Exclusion '{value}' not found"

        except BuiltinExclusionError:
            return f"Cannot remove built-in exclusion '{value}'"
