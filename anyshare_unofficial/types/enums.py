"""Enumeration types for AnyShare API parameters."""

from __future__ import annotations

from enum import Enum, IntEnum


class SortField(str, Enum):
    """Sort field for listing operations."""

    NAME = "name"
    TIME = "time"
    SIZE = "size"


class SortDirection(str, Enum):
    """Sort direction for listing operations."""

    ASC = "asc"
    DESC = "desc"


class ObjectMode(str, Enum):
    """Filter mode for browsing folder contents."""

    ALL = "all"
    FILES = "files"
    DIRS = "dirs"


class DocLibType(str, Enum):
    """Type of document library."""

    USER = "user_doc_lib"
    SHARED_USER = "shared_user_doc_lib"
    GROUP = "group_doc_lib"


class OnDup(int, Enum):
    """Conflict resolution strategy when a name collision occurs."""

    FORBID = 0
    RENAME = 1
    OVERWRITE = 3


class CsfLevel(int, Enum):
    """Security classification level for documents."""

    LOW = 0
    INTERNAL = 5
    CONFIDENTIAL = 6
    SECRET = 7
    TOP_SECRET = 8


class PermissionType(str, Enum):
    """Permission type for permission check requests."""

    DISPLAY = "display"
    PREVIEW = "preview"
    DOWNLOAD = "download"
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    CACHE = "cache"
