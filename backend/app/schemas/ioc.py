from datetime import datetime
from pydantic import BaseModel, Field
from app.models.ioc import IOCType


class IOCCreate(BaseModel):
    value: str = Field(..., min_length=1, max_length=255)
    list_slugs: list[str] = Field(default_factory=list)  # Now optional
    comment: str | None = None
    source: str | None = None


class IOCCommentResponse(BaseModel):
    id: int
    comment: str
    source: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ListRef(BaseModel):
    """Reference to a list with slug and name."""
    slug: str
    name: str


class IOCResponse(BaseModel):
    id: int
    value: str
    ioc_type: str
    lists: list[ListRef]
    comments: list[IOCCommentResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IOCSearchResult(BaseModel):
    id: int
    value: str
    ioc_type: str
    lists: list[ListRef]
    comment: str | None = None  # First comment
    created_at: datetime

    class Config:
        from_attributes = True


class ListIOCItem(BaseModel):
    """IOC item for list detail view."""
    id: int
    value: str
    ioc_type: str
    comment: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class IOCAuditEntry(BaseModel):
    id: int
    action: str
    list_slug: str | None = None
    list_name: str | None = None
    content: str | None = None
    performed_by: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class IOCDetailResponse(BaseModel):
    id: int
    value: str
    ioc_type: str
    lists: list[ListRef]
    audit_history: list[IOCAuditEntry]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
