"""Shared / common data models used across multiple API groups."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UserIdentity(BaseModel):
    """Represents a user (creator or modifier) of a file system object."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    type: Literal["user", "anonymous", "department"]


class DocLibBrief(BaseModel):
    """Lightweight document library reference (e.g. embedded in folder listings)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str  # gns://...
    name: str
    type: Literal["user_doc_lib", "shared_user_doc_lib", "group_doc_lib"] = "user_doc_lib"


class DocLibInfo(BaseModel):
    """Full document library information from entry-doc-lib."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    type: Literal["user_doc_lib", "shared_user_doc_lib", "group_doc_lib"]
    rev: str
    attr: int = 0
    created_at: datetime
    modified_at: datetime
    created_by: UserIdentity
    modified_by: UserIdentity


class DepInfo(BaseModel):
    """Department reference, embedded in user info responses."""

    model_config = ConfigDict(populate_by_name=True)

    depid: str
    name: str
    deppath: str | None = Field(default=None)  # optional department path when present

    @property
    def id(self) -> str:
        return self.depid
