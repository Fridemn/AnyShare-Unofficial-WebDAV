"""Message and notification models (lower priority endpoints)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NotificationEntry(BaseModel):
    """A single notification from the message center."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = ""
    title: str = ""
    content: str = ""
    read: bool = False
    channel: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class NotificationListResult(BaseModel):
    """Response from GET /api/message/v1/notifications."""

    model_config = ConfigDict(populate_by_name=True)

    entries: list[NotificationEntry] = Field(default_factory=list)
    total_count: int = 0
    next_marker: str = ""
