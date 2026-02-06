from datetime import datetime
from pydantic import BaseModel, Field
from app.models.exclusion import ExclusionType


class ExclusionCreate(BaseModel):
    value: str = Field(..., min_length=1, max_length=255)
    type: ExclusionType
    reason: str | None = None


class ExclusionResponse(BaseModel):
    id: int
    value: str
    type: ExclusionType
    reason: str | None
    is_builtin: bool
    created_at: datetime

    class Config:
        from_attributes = True
