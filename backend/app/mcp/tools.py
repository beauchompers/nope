from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
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


# ── Response models ───────────────────────────────────────────────────


class IOCMatch(BaseModel):
    """An IOC found in search results."""

    value: str = Field(description="IOC value")
    ioc_type: str = Field(
        description="IOC type (ip, cidr, domain, wildcard, md5, sha1, sha256)"
    )
    lists: list[str] = Field(description="List slugs containing this IOC")
    comments: list[str] = Field(
        description="Comments on this IOC (up to 3 most recent)"
    )


class IOCEntry(BaseModel):
    """A single IOC on a list."""

    value: str = Field(description="IOC value")
    ioc_type: str = Field(
        description="IOC type (ip, cidr, domain, wildcard, md5, sha1, sha256)"
    )


class ListSummary(BaseModel):
    """Summary of a blocklist."""

    name: str = Field(description="Display name")
    slug: str = Field(description="URL slug identifier")
    url: str = Field(description="Full EDL URL for firewall consumption")
    ioc_count: int = Field(description="Number of IOCs on the list")
    description: str | None = Field(None, description="List description")


class ExclusionEntry(BaseModel):
    """An active exclusion rule."""

    value: str = Field(description="Exclusion pattern")
    exclusion_type: str = Field(
        description="Pattern type (ip, cidr, domain, wildcard)"
    )
    reason: str | None = Field(
        None, description="Human-readable reason for the exclusion"
    )
    builtin: bool = Field(
        description="Whether this is a built-in exclusion that cannot be removed"
    )


class ExclusionConflict(BaseModel):
    """An existing IOC that conflicts with a proposed exclusion."""

    value: str = Field(description="Conflicting IOC value")
    ioc_type: str = Field(description="IOC type")
    lists: list[str] = Field(description="Lists containing this IOC")


class FailedIOC(BaseModel):
    """An IOC that failed during a bulk operation."""

    value: str = Field(description="The IOC value that failed")
    reason: str = Field(
        description="Why it failed (excluded, invalid, etc.)"
    )


class BlockIOCResult(BaseModel):
    """Result of adding an IOC to a blocklist."""

    success: bool = Field(description="Whether the IOC was successfully added")
    message: str = Field(description="Human-readable result message")
    value: str | None = Field(None, description="The normalized IOC value")
    ioc_type: str | None = Field(None, description="Detected IOC type")
    list_slug: str | None = Field(
        None, description="The list the IOC was added to"
    )


class UnblockIOCResult(BaseModel):
    """Result of removing an IOC from blocklist(s)."""

    success: bool = Field(
        description="Whether the IOC was successfully removed"
    )
    message: str = Field(description="Human-readable result message")


class SearchIOCResult(BaseModel):
    """IOC search results."""

    matches: list[IOCMatch] = Field(
        description="IOCs matching the search query"
    )
    total: int = Field(description="Total number of matches")


class ListListsResult(BaseModel):
    """All available blocklists."""

    lists: list[ListSummary] = Field(
        description="Available blocklists with summary info"
    )


class GetListResult(BaseModel):
    """Detailed information about a specific blocklist."""

    found: bool = Field(description="Whether the list was found")
    message: str = Field(description="Human-readable summary or error")
    name: str | None = Field(None, description="Display name")
    slug: str | None = Field(None, description="URL slug")
    url: str | None = Field(None, description="Full EDL URL")
    ioc_count: int | None = Field(None, description="Total number of IOCs")
    description: str | None = Field(None, description="List description")
    tags: list[str] = Field(default_factory=list, description="List tags")
    sample_iocs: list[str] = Field(
        default_factory=list,
        description="First 10 IOC values on the list",
    )


class CreateListResult(BaseModel):
    """Result of creating a new blocklist."""

    success: bool = Field(description="Whether the list was created")
    message: str = Field(description="Human-readable result message")
    name: str | None = Field(None, description="Display name of the list")
    slug: str | None = Field(None, description="URL slug")
    url: str | None = Field(None, description="Full EDL URL")


class DeleteListResult(BaseModel):
    """Result of deleting a blocklist."""

    success: bool = Field(description="Whether the list was deleted")
    message: str = Field(description="Human-readable result message")


class ListIOCsResult(BaseModel):
    """Paginated list of IOCs on a blocklist."""

    found: bool = Field(description="Whether the list was found")
    message: str = Field(description="Human-readable summary or error")
    slug: str = Field(description="List slug queried")
    iocs: list[IOCEntry] = Field(
        default_factory=list, description="IOCs on the list for this page"
    )
    total: int = Field(0, description="Total IOC count across all pages")
    offset: int = Field(0, description="Current pagination offset")
    limit: int = Field(100, description="Current pagination limit")
    has_more: bool = Field(
        False, description="Whether more IOCs exist beyond this page"
    )


class UpdateIOCResult(BaseModel):
    """Result of adding a comment to an IOC."""

    success: bool = Field(description="Whether the comment was added")
    message: str = Field(description="Human-readable result message")


class UpdateListResult(BaseModel):
    """Result of updating a blocklist's metadata."""

    success: bool = Field(description="Whether the update succeeded")
    message: str = Field(description="Human-readable result message")
    updated_fields: list[str] = Field(
        default_factory=list,
        description="Names of fields that were updated",
    )


class BulkBlockResult(BaseModel):
    """Result of adding multiple IOCs to a blocklist."""

    added: int = Field(description="Number of IOCs successfully added")
    skipped: int = Field(
        description="Number of IOCs skipped (already on list)"
    )
    failed: int = Field(
        description="Number of IOCs that failed validation or exclusion"
    )
    failed_items: list[FailedIOC] = Field(
        default_factory=list,
        description="Details of failed IOCs (first 10)",
    )
    message: str = Field(description="Human-readable summary")


class BulkUnblockResult(BaseModel):
    """Result of removing multiple IOCs from blocklist(s)."""

    removed: int = Field(description="Number of IOCs successfully removed")
    not_found: int = Field(description="Number of IOCs not found")
    not_found_items: list[str] = Field(
        default_factory=list,
        description="Values not found (first 10)",
    )
    message: str = Field(description="Human-readable summary")


class ListExclusionsResult(BaseModel):
    """All active exclusion rules."""

    exclusions: list[ExclusionEntry] = Field(
        description="All exclusion rules, both built-in and user-defined"
    )
    total: int = Field(description="Total number of exclusion rules")


class PreviewExclusionResult(BaseModel):
    """Preview of adding an exclusion rule."""

    pattern: str = Field(description="The proposed exclusion pattern")
    safe_to_add: bool = Field(
        description="True if no existing IOCs conflict with this pattern"
    )
    conflicts: list[ExclusionConflict] = Field(
        description="Existing IOCs that would conflict (first 20)"
    )
    message: str = Field(description="Human-readable summary")


class AddExclusionResult(BaseModel):
    """Result of adding a custom exclusion rule."""

    success: bool = Field(description="Whether the exclusion was added")
    message: str = Field(description="Human-readable result message")
    value: str | None = Field(None, description="The exclusion pattern")
    exclusion_type: str | None = Field(
        None, description="Detected pattern type"
    )
    purged: list[ExclusionConflict] = Field(
        default_factory=list,
        description="IOCs removed from lists due to the new exclusion",
    )


class RemoveExclusionResult(BaseModel):
    """Result of removing an exclusion rule."""

    success: bool = Field(description="Whether the exclusion was removed")
    message: str = Field(description="Human-readable result message")


# ── Helpers ────────────────────────────────────────────────────────────


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


# ── Tools ──────────────────────────────────────────────────────────────


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
async def block_ioc(
    value: Annotated[
        str,
        Field(description="The IOC to block (IP, CIDR, domain, wildcard, or hash)"),
    ],
    list_slug: Annotated[
        str,
        Field(description="Slug of the target blocklist"),
    ],
    comment: Annotated[
        str | None,
        Field(description="Optional reason for blocking"),
    ] = None,
) -> BlockIOCResult:
    """Add an IOC to a blocklist.

    Supports IPs, CIDR ranges (e.g., 203.0.113.0/24), domains, wildcard domains
    (e.g., *.example.com), and file hashes (SHA256, SHA1, MD5). IOC type is
    auto-detected. Private/reserved IP ranges (RFC1918, loopback, link-local)
    and TLDs are rejected per exclusion rules - use list_exclusions to see all
    rules. Adding an existing IOC is idempotent (no error, no duplicate).
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
            return BlockIOCResult(
                success=True,
                message=f"Successfully added {ioc.value} ({ioc.type}) to list '{list_slug}'",
                value=ioc.value,
                ioc_type=ioc.type,
                list_slug=list_slug,
            )
        except IOCValidationError as e:
            return BlockIOCResult(
                success=False, message=f"Validation error: {e}"
            )
        except IOCExcludedError as e:
            return BlockIOCResult(
                success=False,
                message=f"Cannot block: {e.match.reason} (matches exclusion '{e.match.value}')",
            )
        except ListNotFoundError as e:
            return BlockIOCResult(success=False, message=f"Error: {e}")


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True))
async def unblock_ioc(
    value: Annotated[
        str,
        Field(description="The IOC value to unblock"),
    ],
    list_slug: Annotated[
        str | None,
        Field(description="Specific list to remove from (required unless all_lists is true)"),
    ] = None,
    all_lists: Annotated[
        bool,
        Field(description="If true, remove from all lists and delete the IOC record"),
    ] = False,
) -> UnblockIOCResult:
    """Remove an IOC from a specific blocklist or all blocklists.

    Supports all IOC types (IP, CIDR, domain, wildcard, hash). The IOC record
    is retained after removal from a single list and will still appear in search
    results. Provide list_slug to remove from one list, or all_lists=true to
    remove from all and delete the record.
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(IOC)
            .options(selectinload(IOC.list_iocs).selectinload(ListIOC.list))
            .where(IOC.value == value.strip().lower())
        )
        ioc = result.scalar_one_or_none()

        if not ioc:
            return UnblockIOCResult(
                success=False, message=f"IOC '{value}' not found"
            )

        if all_lists:
            await delete_ioc(db, ioc.id)
            return UnblockIOCResult(
                success=True, message=f"Removed {value} from all lists"
            )
        elif list_slug:
            removed = await remove_ioc_from_list(db, ioc.id, list_slug)
            if removed:
                return UnblockIOCResult(
                    success=True,
                    message=f"Removed {value} from list '{list_slug}'",
                )
            else:
                return UnblockIOCResult(
                    success=False,
                    message=f"IOC '{value}' not found in list '{list_slug}'",
                )
        else:
            return UnblockIOCResult(
                success=False,
                message="Must specify list_slug or set all_lists=true",
            )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def search_ioc(
    value: Annotated[
        str,
        Field(description="IP, domain, or hash to search for (partial match supported)"),
    ],
    list_slug: Annotated[
        str | None,
        Field(description="Optional list slug to scope search to a specific list"),
    ] = None,
) -> SearchIOCResult:
    """Search for an IOC across all lists or a specific list.

    Supports partial matching (e.g., '203.0.113' matches both '203.0.113.50'
    and '203.0.113.0/24'). Results may include orphaned IOCs no longer on any
    list but retained in the database.
    """
    async with async_session_maker() as db:
        iocs = await search_iocs(db, value, list_slug=list_slug)

        matches = []
        for ioc in iocs:
            matches.append(
                IOCMatch(
                    value=ioc.value,
                    ioc_type=ioc.type,
                    lists=[li.list.slug for li in ioc.list_iocs],
                    comments=[c.comment for c in ioc.comments][:3],
                )
            )

        return SearchIOCResult(matches=matches, total=len(matches))


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_lists(
    tag: Annotated[
        str | None,
        Field(description="Optional tag to filter lists by"),
    ] = None,
) -> ListListsResult:
    """Get all blocklists with summary information.

    Lists are served as EDLs at /edl/{slug} for firewall consumption.
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

        return ListListsResult(
            lists=[
                ListSummary(
                    name=lst.name,
                    slug=lst.slug,
                    url=f"{base_url}/edl/{lst.slug}",
                    ioc_count=len(lst.list_iocs),
                    description=lst.description,
                )
                for lst in lists
            ]
        )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def get_list(
    slug: Annotated[
        str,
        Field(description="The list slug to look up"),
    ],
) -> GetListResult:
    """Get detailed information about a specific list including sample IOCs.

    Lists are served as EDLs at /edl/{slug} for firewall consumption.
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(List)
            .options(selectinload(List.list_iocs).selectinload(ListIOC.ioc))
            .where(List.slug == slug)
        )
        lst = result.scalar_one_or_none()

        if not lst:
            return GetListResult(
                found=False, message=f"List '{slug}' not found"
            )

        base_url = await get_edl_base_url(db)

        return GetListResult(
            found=True,
            message=f"List '{lst.name}' with {len(lst.list_iocs)} IOCs",
            name=lst.name,
            slug=lst.slug,
            url=f"{base_url}/edl/{lst.slug}",
            ioc_count=len(lst.list_iocs),
            description=lst.description,
            tags=lst.tags or [],
            sample_iocs=[li.ioc.value for li in lst.list_iocs[:10]],
        )


@mcp.tool()
async def create_list(
    name: Annotated[
        str,
        Field(description="Display name for the list"),
    ],
    description: Annotated[
        str | None,
        Field(description="Optional description of the list's purpose"),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Field(description="Optional tags for categorization"),
    ] = None,
) -> CreateListResult:
    """Create a new blocklist.

    The slug is auto-generated from the name and used as the immutable
    identifier in the EDL URL (/edl/{slug}).
    """
    async with async_session_maker() as db:
        slug = List.generate_slug(name)

        existing = await db.execute(select(List).where(List.slug == slug))
        if existing.scalar_one_or_none():
            return CreateListResult(
                success=False,
                message=f"List with slug '{slug}' already exists",
            )

        lst = List(
            name=name,
            slug=slug,
            description=description,
            tags=tags,
        )
        db.add(lst)
        await db.commit()
        base_url = await get_edl_base_url(db)

        return CreateListResult(
            success=True,
            message=f"Created list '{name}'",
            name=name,
            slug=slug,
            url=f"{base_url}/edl/{slug}",
        )


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True))
async def delete_list(
    slug: Annotated[
        str,
        Field(description="The list slug to delete"),
    ],
) -> DeleteListResult:
    """Delete a blocklist and remove all IOC-to-list associations.

    IOC records are retained in the database and may still appear in search
    results.
    """
    async with async_session_maker() as db:
        result = await db.execute(select(List).where(List.slug == slug))
        lst = result.scalar_one_or_none()

        if not lst:
            return DeleteListResult(
                success=False, message=f"List '{slug}' not found"
            )

        await db.delete(lst)
        await db.commit()

        return DeleteListResult(
            success=True, message=f"Deleted list '{slug}'"
        )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_iocs(
    slug: Annotated[
        str,
        Field(description="The list slug to retrieve IOCs from"),
    ],
    limit: Annotated[
        int,
        Field(description="Maximum number of IOCs to return (1-500)"),
    ] = 100,
    offset: Annotated[
        int,
        Field(description="Number of IOCs to skip for pagination"),
    ] = 0,
) -> ListIOCsResult:
    """List all IOCs on a specific blocklist with pagination."""
    limit = max(1, min(500, limit))

    async with async_session_maker() as db:
        iocs, total = await get_iocs_for_list(
            db, slug, limit=limit, offset=offset
        )

        if iocs is None:
            return ListIOCsResult(
                found=False,
                message=f"List '{slug}' not found",
                slug=slug,
            )

        end = offset + len(iocs)
        return ListIOCsResult(
            found=True,
            message=f"Showing {offset + 1}-{end} of {total} IOCs"
            if iocs
            else f"List '{slug}' has no IOCs",
            slug=slug,
            iocs=[
                IOCEntry(value=ioc.value, ioc_type=ioc.type) for ioc in iocs
            ],
            total=total,
            offset=offset,
            limit=limit,
            has_more=end < total,
        )


@mcp.tool()
async def update_ioc(
    value: Annotated[
        str,
        Field(description="The IOC value to add a comment to"),
    ],
    comment: Annotated[
        str,
        Field(description="Comment text to append"),
    ],
) -> UpdateIOCResult:
    """Add a comment to an existing IOC.

    Comments are append-only to preserve audit history. Each comment records
    when it was added and by whom.
    """
    async with async_session_maker() as db:
        success = await add_ioc_comment(db, value, comment, source="mcp")

        if success:
            return UpdateIOCResult(
                success=True, message=f"Comment added to {value}"
            )
        else:
            return UpdateIOCResult(
                success=False, message=f"IOC '{value}' not found"
            )


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
async def update_list(
    slug: Annotated[
        str,
        Field(description="The list slug to update"),
    ],
    name: Annotated[
        str | None,
        Field(description="New display name"),
    ] = None,
    description: Annotated[
        str | None,
        Field(description="New description"),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Field(description="New tags list (replaces existing tags)"),
    ] = None,
) -> UpdateListResult:
    """Update a blocklist's metadata.

    Only provided fields are updated. The slug cannot be changed as it's the
    immutable identifier used in EDL URLs.
    """
    if name is None and description is None and tags is None:
        return UpdateListResult(
            success=False,
            message="No updates provided. Specify name, description, or tags.",
        )

    async with async_session_maker() as db:
        result = await db.execute(select(List).where(List.slug == slug))
        lst = result.scalar_one_or_none()

        if not lst:
            return UpdateListResult(
                success=False, message=f"List '{slug}' not found"
            )

        updated = []
        if name is not None:
            lst.name = name
            updated.append("name")
        if description is not None:
            lst.description = description
            updated.append("description")
        if tags is not None:
            lst.tags = tags
            updated.append("tags")

        await db.commit()

        return UpdateListResult(
            success=True,
            message=f"Updated list '{slug}': {', '.join(updated)}",
            updated_fields=updated,
        )


@mcp.tool(annotations=ToolAnnotations(idempotentHint=True))
async def bulk_block_ioc(
    values: Annotated[
        list[str],
        Field(description="IOC values to add (max 500)"),
    ],
    list_slug: Annotated[
        str,
        Field(description="Slug of the target blocklist"),
    ],
    comment: Annotated[
        str | None,
        Field(description="Optional comment applied to all IOCs"),
    ] = None,
) -> BulkBlockResult:
    """Add multiple IOCs to a blocklist in a single operation.

    Supports all IOC types. Each IOC is independently validated and checked
    against exclusion rules. Duplicates are silently skipped.
    """
    if len(values) > 500:
        return BulkBlockResult(
            added=0,
            skipped=0,
            failed=len(values),
            message=f"Maximum 500 IOCs per request (received {len(values)})",
        )

    if not values:
        return BulkBlockResult(
            added=0, skipped=0, failed=0, message="No IOCs provided"
        )

    async with async_session_maker() as db:
        try:
            added_by = _get_added_by()
            results = await bulk_add_iocs(
                db,
                values,
                list_slug,
                comment=comment,
                source="mcp",
                added_by=added_by,
            )

            failed_items = [
                FailedIOC(value=v, reason=r)
                for v, r in results["failed"][:10]
            ]

            return BulkBlockResult(
                added=len(results["added"]),
                skipped=len(results["skipped"]),
                failed=len(results["failed"]),
                failed_items=failed_items,
                message=(
                    f"Added {len(results['added'])}, "
                    f"skipped {len(results['skipped'])}, "
                    f"failed {len(results['failed'])}"
                ),
            )

        except ListNotFoundError as e:
            return BulkBlockResult(
                added=0,
                skipped=0,
                failed=len(values),
                message=str(e),
            )


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True))
async def bulk_unblock_ioc(
    values: Annotated[
        list[str],
        Field(description="IOC values to remove (max 500)"),
    ],
    list_slug: Annotated[
        str | None,
        Field(description="Specific list to remove from (required unless all_lists is true)"),
    ] = None,
    all_lists: Annotated[
        bool,
        Field(description="If true, remove from all lists and delete IOC records"),
    ] = False,
) -> BulkUnblockResult:
    """Remove multiple IOCs from blocklist(s) in a single operation."""
    if len(values) > 500:
        return BulkUnblockResult(
            removed=0,
            not_found=len(values),
            message=f"Maximum 500 IOCs per request (received {len(values)})",
        )

    if not values:
        return BulkUnblockResult(
            removed=0, not_found=0, message="No IOCs provided"
        )

    if not list_slug and not all_lists:
        return BulkUnblockResult(
            removed=0,
            not_found=0,
            message="Must specify list_slug or set all_lists=true",
        )

    async with async_session_maker() as db:
        results = await bulk_remove_iocs(
            db, values, list_slug=list_slug, all_lists=all_lists
        )

        target = "all lists" if all_lists else f"'{list_slug}'"
        return BulkUnblockResult(
            removed=len(results["removed"]),
            not_found=len(results["not_found"]),
            not_found_items=results["not_found"][:10],
            message=(
                f"Removed {len(results['removed'])} from {target}, "
                f"{len(results['not_found'])} not found"
            ),
        )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def list_exclusions() -> ListExclusionsResult:
    """List all active exclusion rules that prevent IOCs from being added.

    Includes both built-in rules (RFC1918, TLDs, etc.) and user-defined rules.
    Built-in rules cannot be removed.
    """
    async with async_session_maker() as db:
        exclusions = await get_all_exclusions(db)

        entries = []
        for e in exclusions["builtin"]:
            entries.append(
                ExclusionEntry(
                    value=e.value,
                    exclusion_type=e.type,
                    reason=e.reason,
                    builtin=True,
                )
            )
        for e in exclusions["user_defined"]:
            entries.append(
                ExclusionEntry(
                    value=e.value,
                    exclusion_type=e.type,
                    reason=e.reason,
                    builtin=False,
                )
            )

        return ListExclusionsResult(
            exclusions=entries, total=len(entries)
        )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
async def preview_exclusion(
    value: Annotated[
        str,
        Field(description="Proposed exclusion pattern (IP, CIDR, domain, wildcard)"),
    ],
) -> PreviewExclusionResult:
    """Preview the impact of adding an exclusion rule without committing it.

    Shows existing IOCs that would conflict with the proposed exclusion.
    Use this before add_exclusion to understand the impact.
    """
    excl_type = detect_exclusion_type(value)
    if excl_type is None:
        return PreviewExclusionResult(
            pattern=value,
            safe_to_add=False,
            conflicts=[],
            message=f"Invalid exclusion pattern: '{value}'",
        )

    async with async_session_maker() as db:
        conflicts = await preview_exclusion_conflicts(db, value, excl_type)

        conflict_entries = [
            ExclusionConflict(
                value=c["value"],
                ioc_type=c["type"],
                lists=c["lists"],
            )
            for c in conflicts[:20]
        ]

        if not conflicts:
            msg = f"No conflicts with existing IOCs. Safe to add '{value}'."
        else:
            msg = (
                f"Would conflict with {len(conflicts)} existing IOC(s). "
                "Use add_exclusion with purge_conflicts=true to add and "
                "remove conflicts, or purge_conflicts=false to add the "
                "exclusion only (existing IOCs remain)."
            )

        return PreviewExclusionResult(
            pattern=value,
            safe_to_add=len(conflicts) == 0,
            conflicts=conflict_entries,
            message=msg,
        )


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True))
async def add_exclusion(
    value: Annotated[
        str,
        Field(description="Pattern to exclude (IP, CIDR, domain, wildcard) - type auto-detected"),
    ],
    reason: Annotated[
        str,
        Field(description="Human-readable reason for this exclusion"),
    ],
    purge_conflicts: Annotated[
        bool,
        Field(description="If true, remove existing IOCs matching this pattern from all lists"),
    ] = False,
) -> AddExclusionResult:
    """Add a custom exclusion rule to prevent matching IOCs from being blocked.

    Use preview_exclusion first to check for conflicts. Duplicate patterns
    are rejected.
    """
    async with async_session_maker() as db:
        try:
            result = await add_exclusion_svc(
                db, value, reason, purge_conflicts=purge_conflicts
            )

            purged_entries = [
                ExclusionConflict(
                    value=p["value"],
                    ioc_type=p.get("type", "unknown"),
                    lists=p.get("lists", []),
                )
                for p in result["purged"][:10]
            ]

            excl = result["exclusion"]
            msg = f"Added exclusion '{excl.value}' ({excl.type})"
            if purged_entries:
                msg += f", purged {len(result['purged'])} conflicting IOC(s)"

            return AddExclusionResult(
                success=True,
                message=msg,
                value=excl.value,
                exclusion_type=excl.type,
                purged=purged_entries,
            )

        except DuplicateExclusionError as e:
            return AddExclusionResult(success=False, message=str(e))
        except ValidationError as e:
            return AddExclusionResult(
                success=False, message=f"Invalid pattern: {e}"
            )


@mcp.tool(annotations=ToolAnnotations(destructiveHint=True, idempotentHint=True))
async def remove_exclusion(
    value: Annotated[
        str,
        Field(description="The exclusion pattern to remove"),
    ],
) -> RemoveExclusionResult:
    """Remove a user-defined exclusion rule. Built-in exclusions cannot be removed."""
    async with async_session_maker() as db:
        try:
            removed = await remove_exclusion_svc(db, value)

            if removed:
                return RemoveExclusionResult(
                    success=True, message=f"Removed exclusion '{value}'"
                )
            else:
                return RemoveExclusionResult(
                    success=False,
                    message=f"Exclusion '{value}' not found",
                )

        except BuiltinExclusionError:
            return RemoveExclusionResult(
                success=False,
                message=f"Cannot remove built-in exclusion '{value}'",
            )
