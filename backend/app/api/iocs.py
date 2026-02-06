from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

from app.db import get_db
from app.models import IOC, ListIOC, List
from app.models.ioc_audit import IOCAuditLog
from app.schemas.ioc import IOCCreate, IOCResponse, IOCCommentResponse, IOCSearchResult, ListRef, IOCDetailResponse, IOCAuditEntry
from app.api.auth import get_current_user
from app.services.ioc_service import (
    add_ioc,
    remove_ioc_from_list,
    delete_ioc,
    search_iocs,
    IOCExcludedError,
    IOCValidationError,
    ListNotFoundError,
    ListTypeMismatchError,
)
from app.services.audit_service import log_ioc_added_to_list, log_ioc_comment
from app.services.validation import is_ioc_type_allowed


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


router = APIRouter(prefix="/api/iocs", tags=["iocs"])


def _ioc_to_response(ioc: IOC) -> IOCResponse:
    """Convert IOC model to response schema."""
    return IOCResponse(
        id=ioc.id,
        value=ioc.value,
        ioc_type=ioc.type,
        lists=[ListRef(slug=li.list.slug, name=li.list.name) for li in ioc.list_iocs],
        comments=[
            IOCCommentResponse(
                id=c.id,
                comment=c.comment,
                source=c.source,
                created_at=c.created_at,
            )
            for c in ioc.comments
        ],
        created_at=ioc.created_at,
        updated_at=ioc.updated_at,
    )


@router.get("", response_model=list[IOCSearchResult])
async def list_iocs(
    q: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """List all IOCs, optionally filtered by search query."""
    if q:
        iocs = await search_iocs(db, q)
    else:
        result = await db.execute(
            select(IOC)
            .options(
                selectinload(IOC.list_iocs).selectinload(ListIOC.list),
                selectinload(IOC.comments),
            )
            .order_by(IOC.created_at.desc())
            .limit(100)
        )
        iocs = list(result.scalars().all())

    return [
        IOCSearchResult(
            id=ioc.id,
            value=ioc.value,
            ioc_type=ioc.type,
            lists=[ListRef(slug=li.list.slug, name=li.list.name) for li in ioc.list_iocs],
            comment=ioc.comments[0].comment[:100] if ioc.comments else None,
            created_at=ioc.created_at,
        )
        for ioc in iocs
    ]


@router.post("", response_model=IOCResponse, status_code=status.HTTP_201_CREATED)
async def create_ioc(
    data: IOCCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Add an IOC to one or more lists."""
    try:
        ioc = await add_ioc(
            db=db,
            value=data.value,
            list_slugs=data.list_slugs,
            comment=data.comment,
            source=data.source,
            added_by="api",  # TODO: Get from auth
        )
    except IOCValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except IOCExcludedError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot add IOC: {e.match.reason} (matches exclusion '{e.match.value}')",
        )
    except ListNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ListTypeMismatchError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Reload with relationships
    result = await db.execute(
        select(IOC)
        .options(
            selectinload(IOC.list_iocs).selectinload(ListIOC.list),
            selectinload(IOC.comments),
        )
        .where(IOC.id == ioc.id)
    )
    ioc = result.scalar_one()

    return _ioc_to_response(ioc)


@router.get("/{ioc_id}", response_model=IOCDetailResponse)
async def get_ioc(
    ioc_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Get IOC details with audit history."""
    result = await db.execute(
        select(IOC)
        .options(
            selectinload(IOC.list_iocs).selectinload(ListIOC.list),
            selectinload(IOC.comments),
            selectinload(IOC.audit_logs).selectinload(IOCAuditLog.list),
        )
        .where(IOC.id == ioc_id)
    )
    ioc = result.scalar_one_or_none()

    if not ioc:
        raise HTTPException(status_code=404, detail="IOC not found")

    return IOCDetailResponse(
        id=ioc.id,
        value=ioc.value,
        ioc_type=ioc.type,
        lists=[ListRef(slug=li.list.slug, name=li.list.name) for li in ioc.list_iocs],
        audit_history=[
            IOCAuditEntry(
                id=log.id,
                action=log.action,
                list_slug=log.list.slug if log.list else None,
                list_name=log.list.name if log.list else None,
                content=log.content,
                performed_by=log.performed_by,
                created_at=log.created_at,
            )
            for log in sorted(ioc.audit_logs, key=lambda x: x.created_at, reverse=True)
        ],
        created_at=ioc.created_at,
        updated_at=ioc.updated_at,
    )


@router.delete("/{ioc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ioc_endpoint(
    ioc_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Delete an IOC from all lists."""
    deleted = await delete_ioc(db, ioc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="IOC not found")


@router.delete("/{ioc_id}/lists/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_list(
    ioc_id: int,
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Remove an IOC from a specific list."""
    removed = await remove_ioc_from_list(db, ioc_id, slug)
    if not removed:
        raise HTTPException(status_code=404, detail="IOC not found in list")


@router.post("/{ioc_id}/lists/{slug}", status_code=status.HTTP_201_CREATED)
async def add_ioc_to_list(
    ioc_id: int,
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Add an existing IOC to a list."""
    result = await db.execute(
        select(IOC).options(selectinload(IOC.list_iocs)).where(IOC.id == ioc_id)
    )
    ioc = result.scalar_one_or_none()
    if not ioc:
        raise HTTPException(status_code=404, detail="IOC not found")

    list_result = await db.execute(select(List).where(List.slug == slug))
    lst = list_result.scalar_one_or_none()
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    # Validate IOC type is allowed for this list type
    if not is_ioc_type_allowed(ioc.type, lst.list_type):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot add {ioc.type} IOC to a {lst.list_type}-only list",
        )

    existing_list_ids = {li.list_id for li in ioc.list_iocs}
    if lst.id in existing_list_ids:
        raise HTTPException(status_code=409, detail="IOC already in list")

    list_ioc = ListIOC(list_id=lst.id, ioc_id=ioc.id, added_by="api")
    db.add(list_ioc)
    await log_ioc_added_to_list(db, ioc.id, lst.id, "api")
    await db.commit()

    from app.services.edl_generator import generate_edl_file
    await generate_edl_file(db, slug)

    return {"message": f"IOC added to {slug}"}


@router.post("/{ioc_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    ioc_id: int,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Add a standalone comment to an IOC."""
    result = await db.execute(select(IOC).where(IOC.id == ioc_id))
    ioc = result.scalar_one_or_none()
    if not ioc:
        raise HTTPException(status_code=404, detail="IOC not found")

    await log_ioc_comment(db, ioc_id, data.content, "api")
    await db.commit()

    return {"message": "Comment added"}
