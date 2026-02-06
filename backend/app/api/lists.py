from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import List, ListIOC, IOC, IOCComment
from app.schemas import ListCreate, ListUpdate, ListResponse, ListSummary, ListIOCItem
from app.services.validation import is_ioc_type_allowed
from app.api.auth import get_current_user

router = APIRouter(prefix="/api/lists", tags=["lists"])


@router.get("", response_model=list[ListSummary])
async def get_lists(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Get all lists with IOC counts."""
    # Subquery for IOC counts
    ioc_count_subq = (
        select(ListIOC.list_id, func.count(ListIOC.id).label("ioc_count"))
        .group_by(ListIOC.list_id)
        .subquery()
    )

    result = await db.execute(
        select(
            List,
            func.coalesce(ioc_count_subq.c.ioc_count, 0).label("ioc_count")
        )
        .outerjoin(ioc_count_subq, List.id == ioc_count_subq.c.list_id)
        .order_by(List.name)
    )

    lists = []
    for row in result:
        list_obj = row[0]
        lists.append(ListSummary(
            id=list_obj.id,
            name=list_obj.name,
            slug=list_obj.slug,
            description=list_obj.description,
            tags=list_obj.tags,
            list_type=list_obj.list_type,
            ioc_count=row[1],
            created_at=list_obj.created_at,
            updated_at=list_obj.updated_at,
        ))

    return lists


@router.post("", response_model=ListResponse, status_code=status.HTTP_201_CREATED)
async def create_list(
    data: ListCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Create a new list."""
    slug = List.generate_slug(data.name)

    # Check for duplicate slug
    existing = await db.execute(select(List).where(List.slug == slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"List with slug '{slug}' already exists",
        )

    list_obj = List(
        name=data.name,
        slug=slug,
        description=data.description,
        tags=data.tags,
        list_type=data.list_type,
    )
    db.add(list_obj)
    await db.commit()
    await db.refresh(list_obj)

    return ListResponse(
        id=list_obj.id,
        name=list_obj.name,
        slug=list_obj.slug,
        description=list_obj.description,
        tags=list_obj.tags,
        list_type=list_obj.list_type,
        ioc_count=0,
        created_at=list_obj.created_at,
        updated_at=list_obj.updated_at,
    )


@router.get("/{slug}", response_model=ListResponse)
async def get_list(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Get a list by slug."""
    result = await db.execute(
        select(List)
        .options(selectinload(List.list_iocs))
        .where(List.slug == slug)
    )
    list_obj = result.scalar_one_or_none()

    if not list_obj:
        raise HTTPException(status_code=404, detail="List not found")

    return ListResponse(
        id=list_obj.id,
        name=list_obj.name,
        slug=list_obj.slug,
        description=list_obj.description,
        tags=list_obj.tags,
        list_type=list_obj.list_type,
        ioc_count=len(list_obj.list_iocs),
        created_at=list_obj.created_at,
        updated_at=list_obj.updated_at,
    )


@router.patch("/{slug}", response_model=ListResponse)
async def update_list(
    slug: str,
    data: ListUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Update a list."""
    result = await db.execute(
        select(List)
        .options(selectinload(List.list_iocs).selectinload(ListIOC.ioc))
        .where(List.slug == slug)
    )
    list_obj = result.scalar_one_or_none()

    if not list_obj:
        raise HTTPException(status_code=404, detail="List not found")

    # Validate list_type change won't invalidate existing IOCs
    if data.list_type is not None and data.list_type != list_obj.list_type:
        # Count IOCs that would become invalid under the new type
        invalid_counts: dict[str, int] = {}
        for list_ioc in list_obj.list_iocs:
            ioc = list_ioc.ioc
            ioc_type = ioc.type.value if hasattr(ioc.type, 'value') else ioc.type
            if not is_ioc_type_allowed(ioc_type, data.list_type):
                invalid_counts[ioc_type] = invalid_counts.get(ioc_type, 0) + 1

        if invalid_counts:
            # Find the most common incompatible type for the error message
            incompatible_type = max(invalid_counts, key=lambda k: invalid_counts[k])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change to '{data.list_type}' type: list contains {invalid_counts[incompatible_type]} {incompatible_type} IOCs",
            )

    if data.name is not None:
        new_slug = List.generate_slug(data.name)
        if new_slug != list_obj.slug:
            # Check for duplicate
            existing = await db.execute(select(List).where(List.slug == new_slug))
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"List with slug '{new_slug}' already exists",
                )
            list_obj.slug = new_slug
        list_obj.name = data.name

    if data.description is not None:
        list_obj.description = data.description

    if data.tags is not None:
        list_obj.tags = data.tags

    if data.list_type is not None:
        list_obj.list_type = data.list_type

    await db.commit()
    await db.refresh(list_obj)

    return ListResponse(
        id=list_obj.id,
        name=list_obj.name,
        slug=list_obj.slug,
        description=list_obj.description,
        tags=list_obj.tags,
        list_type=list_obj.list_type,
        ioc_count=len(list_obj.list_iocs),
        created_at=list_obj.created_at,
        updated_at=list_obj.updated_at,
    )


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_list(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Delete a list."""
    result = await db.execute(select(List).where(List.slug == slug))
    list_obj = result.scalar_one_or_none()

    if not list_obj:
        raise HTTPException(status_code=404, detail="List not found")

    await db.delete(list_obj)
    await db.commit()


@router.get("/{slug}/iocs", response_model=list[ListIOCItem])
async def get_list_iocs(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Get all IOCs in a list."""
    result = await db.execute(
        select(List)
        .options(
            selectinload(List.list_iocs)
            .selectinload(ListIOC.ioc)
            .selectinload(IOC.comments)
        )
        .where(List.slug == slug)
    )
    list_obj = result.scalar_one_or_none()

    if not list_obj:
        raise HTTPException(status_code=404, detail="List not found")

    # Build response with IOC details
    iocs = []
    for list_ioc in list_obj.list_iocs:
        ioc = list_ioc.ioc
        # Get first comment if any
        comment = None
        if ioc.comments:
            comment = ioc.comments[0].comment

        iocs.append(ListIOCItem(
            id=ioc.id,
            value=ioc.value,
            ioc_type=ioc.type,
            comment=comment,
            created_at=ioc.created_at,
        ))

    return iocs
