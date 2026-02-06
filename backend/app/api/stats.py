from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import List, IOC, AuditLog
from app.api.auth import get_current_user

router = APIRouter(prefix="/api/stats", tags=["stats"])


class DashboardStats(BaseModel):
    total_lists: int
    total_iocs: int
    recent_activity: list[dict] = []


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Get dashboard statistics."""
    # Count lists
    lists_result = await db.execute(select(func.count(List.id)))
    total_lists = lists_result.scalar() or 0

    # Count IOCs
    iocs_result = await db.execute(select(func.count(IOC.id)))
    total_iocs = iocs_result.scalar() or 0

    # Get recent activity from audit log
    recent_result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    recent_logs = recent_result.scalars().all()

    recent_activity = [
        {
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_value": log.entity_value,
            "timestamp": log.created_at.isoformat() if log.created_at else None,
        }
        for log in recent_logs
    ]

    return DashboardStats(
        total_lists=total_lists,
        total_iocs=total_iocs,
        recent_activity=recent_activity,
    )
