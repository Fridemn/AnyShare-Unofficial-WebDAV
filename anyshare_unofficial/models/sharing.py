"""Shared document and link configuration models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from anyshare_unofficial.models.common import UserIdentity
from anyshare_unofficial.types.enums import DocLibType, PermissionType


class LinkConfig(BaseModel):
    """Configuration of a sharing link."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = ""
    allow: list[PermissionType] = Field(default_factory=list)
    password: str | None = None
    accessed_times: int = 0
    id: str = ""
    expires_at: datetime
    limited_times: int = 0
    verify_mobile: bool = False

    def has_no_expire_time(self) -> bool:
        """Check if the link never expires."""
        return self.expires_at <= datetime(1970, 1, 1, 0, 0, tzinfo=None)

    def has_no_times_limit(self) -> bool:
        """Check if the link has no access times limit."""
        return self.limited_times < 0

    def is_expired(self, current_time: datetime | None = None) -> bool:
        """Check if the link is expired based on the current time."""
        if current_time is None:
            current_time = datetime.now(tz=self.expires_at.tzinfo)
        return not self.has_no_expire_time() and current_time >= self.expires_at

    def is_exceeded_times_limit(self) -> bool:
        """Check if the link has exceeded its access times limit."""
        return not self.has_no_times_limit() and self.accessed_times >= self.limited_times


class PermConfig(BaseModel):
    """Permission configuration for sharing with users.

    Note: ``accessible_by`` may be a single object or a list in the API response;
    a validator normalizes singletons into a list.
    """

    model_config = ConfigDict(populate_by_name=True)

    allow: list[PermissionType] = Field(default_factory=list)
    deny: list[PermissionType] = Field(default_factory=list)
    created_at: datetime | None = None
    modified_at: datetime | None = None
    expires_at: datetime | None = None
    accessible_by: list[UserIdentity] = Field(default_factory=list)

    def can(self, perm: PermissionType, *, default: bool = False) -> bool | None:
        """Check if the permission is allowed."""
        if perm in self.deny:
            return False
        if perm in self.allow:
            return True
        return default

    @field_validator("accessible_by", mode="before")
    @classmethod
    def _normalize_accessible_by(cls, v: object) -> list[dict[str, object]]:
        """Wrap a single dict into a list so both forms are accepted."""
        if v is None:
            return []
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            return v  # type: ignore[return-value]
        return []


class ShareEntry(BaseModel):
    """A single entry in the shared documents list."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = ""
    doc: dict[str, Any] = Field(default_factory=dict)
    link_configs: list[LinkConfig] = Field(default_factory=list, alias="link_configs")
    perm_configs: list[PermConfig] = Field(default_factory=list, alias="perm_configs")


class BlockedDocLib(BaseModel):
    """A document library blocked from public sharing."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = ""
    name: str = ""
    doc_lib_type: DocLibType = DocLibType.USER


class ShareListResult(BaseModel):
    """Response from list-shared endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    entries: list[ShareEntry] = Field(default_factory=list)
    total_count: int = 0


class BlockedDocLibListResult(BaseModel):
    """Response from GET /api/doc-share/v1/blocked-doc-lib."""

    model_config = ConfigDict(populate_by_name=True)

    entries: list[BlockedDocLib] = Field(default_factory=list)
    total_count: int = 0
