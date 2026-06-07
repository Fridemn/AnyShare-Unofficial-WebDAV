"""File and folder object models for the AnyShare API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from anyshare_unofficial.models.common import DocLibBrief, UserIdentity


class FileItem(BaseModel):
    """A single file entry returned from folder browsing."""

    model_config = ConfigDict(populate_by_name=True)

    id: str  # gns://... docid (alias for "id" in JSON)
    name: str
    size: int  # bytes, always >= 0 for files
    rev: str  # uuid, lowercase
    created_at: datetime
    modified_at: datetime
    created_by: UserIdentity | None = None
    modified_by: UserIdentity | None = None
    custom_metadata: dict[str, Any] = Field(default_factory=dict)
    storage_name: str = ""
    security_classification: int = 0

    @property
    def is_dir(self) -> bool:
        """Returns False for files (explicit type narrowing)."""
        return False


class FolderItem(BaseModel):
    """A single folder entry returned from folder browsing."""

    model_config = ConfigDict(populate_by_name=True)

    id: str  # gns://... docid
    name: str
    size: int = -1  # always -1 for folders
    rev: str  # uuid, lowercase
    created_at: datetime
    modified_at: datetime
    created_by: UserIdentity | None = None
    modified_by: UserIdentity | None = None

    @property
    def is_dir(self) -> bool:
        """Returns True for folders (explicit type narrowing)."""
        return True


# Union type for operations that can return either
AnyObject = FileItem | FolderItem


class FolderContent(BaseModel):
    """Response from GET /api/efast/v1/folders/{path}/sub_objects."""

    model_config = ConfigDict(populate_by_name=True)

    next_marker: str = ""
    dirs: list[FolderItem] = Field(default_factory=list)
    files: list[FileItem] = Field(default_factory=list)
    doc_lib: DocLibBrief | None = None


class FileMetadata(BaseModel):
    """Response from POST /api/efast/v1/file/metadata.

    Contains detailed technical metadata about a single file.
    """

    model_config = ConfigDict(populate_by_name=True)

    docid: str
    name: str  # storage (encoded) name
    file_name: str = ""  # original filename
    size: int
    rev: str
    editor: str = ""
    modified: int = 0  # epoch microseconds
    client_mtime: int = 0  # epoch microseconds
    doc_lib_type: str = ""
    storage_name: str = ""
    needdownloadwatermark: bool = False


class ItemDetail(BaseModel):
    """Response from GET /api/efast/v2/items/{object_id}/all.

    Provides extended details including human-readable path.
    """

    model_config = ConfigDict(populate_by_name=True)

    object_id: str
    doc_id: str  # gns://... full path
    name: str
    type: Literal["file", "folder"]
    size: int
    path: str  # human-readable path like "/My Docs/folder/file.txt"
    rev: str
    created_at: datetime
    modified_at: datetime
    created_by: UserIdentity
    modified_by: UserIdentity
    doc_lib: DocLibBrief
    storage_name: str = ""
    security_classification: int = 0
    custom_metadata: dict[str, Any] = Field(default_factory=dict)
