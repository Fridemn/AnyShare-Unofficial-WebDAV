"""AnyShare Unofficial API Client Library.

Provides programmatic access to AiShu AnyShare cloud drive services
via two client interfaces:

- AnonymousClient: Access shared content via sharing links
- AuthenticatedClient: Full access via Cookie-based authentication
"""

from anyshare_unofficial._anonymous.client import AnonymousClient
from anyshare_unofficial._authenticated.client import AuthenticatedClient
from anyshare_unofficial._base.client import BaseClient
from anyshare_unofficial.exceptions import (
    AnyShareAPIError,
    AnyShareAuthError,
    AnyShareError,
    AnyShareInputError,
    AnyShareNetworkError,
)
from anyshare_unofficial.models.auth import (
    AuthConfig,
    LoginConfig,
    ThirdAuthConfig,
    UserBasicDepInfo,
    UserBasicInfo,
    UserInfo,
)
from anyshare_unofficial.models.common import DepInfo, DocLibBrief, DocLibInfo, UserIdentity
from anyshare_unofficial.models.contact import (
    ContactGroup,
    ContactGroupListResponse,
    ContactPersonListResponse,
    DepartmentInfo,
    DepartmentUserInfo,
    DepartmentUserListResponse,
)
from anyshare_unofficial.models.fileobj import AnyObject, FileItem, FileMetadata, FolderContent, FolderItem, ItemDetail
from anyshare_unofficial.models.messages import NotificationEntry, NotificationListResult
from anyshare_unofficial.models.operations import (
    DirCreateResult,
    DirRenameResult,
    DownloadAuth,
    MoveResult,
    OsBeginUploadResult,
    OsDownloadResult,
    OsEndUploadResult,
    PreduploadResult,
    SuggestNameResult,
    UploadAuth,
)
from anyshare_unofficial.models.permission import AutoLockInfo, PermissionCheckResult, ShareDocConfig
from anyshare_unofficial.models.quota import QuotaInfo
from anyshare_unofficial.models.sharing import (
    BlockedDocLib,
    BlockedDocLibListResult,
    LinkConfig,
    PermConfig,
    ShareEntry,
    ShareListResult,
)
from anyshare_unofficial.types.enums import (
    CsfLevel,
    DocLibType,
    ObjectMode,
    OnDup,
    PermissionType,
    SortDirection,
    SortField,
)

__all__ = [
    # Clients
    "AnonymousClient",
    "AuthenticatedClient",
    "BaseClient",
    # Exceptions
    "AnyShareAPIError",
    "AnyShareAuthError",
    "AnyShareError",
    "AnyShareInputError",
    "AnyShareNetworkError",
    # Enums
    "CsfLevel",
    "DocLibType",
    "ObjectMode",
    "OnDup",
    "PermissionType",
    "SortDirection",
    "SortField",
    # Models - auth
    "AuthConfig",
    "LoginConfig",
    "ThirdAuthConfig",
    "UserBasicDepInfo",
    "UserBasicInfo",
    "UserInfo",
    # Models - common
    "DepInfo",
    "DocLibBrief",
    "DocLibInfo",
    "UserIdentity",
    # Models - contact
    "ContactGroup",
    "ContactGroupListResponse",
    "ContactPersonListResponse",
    "DepartmentInfo",
    "DepartmentUserInfo",
    "DepartmentUserListResponse",
    # Models - fileobj
    "AnyObject",
    "FileItem",
    "FileMetadata",
    "FolderContent",
    "FolderItem",
    "ItemDetail",
    # Models - messages
    "NotificationEntry",
    "NotificationListResult",
    # Models - operations
    "DirCreateResult",
    "DirRenameResult",
    "DownloadAuth",
    "MoveResult",
    "OsBeginUploadResult",
    "OsDownloadResult",
    "OsEndUploadResult",
    "PreduploadResult",
    "SuggestNameResult",
    "UploadAuth",
    # Models - permission
    "AutoLockInfo",
    "PermissionCheckResult",
    "ShareDocConfig",
    # Models - quota
    "QuotaInfo",
    # Models - sharing
    "BlockedDocLib",
    "BlockedDocLibListResult",
    "LinkConfig",
    "PermConfig",
    "ShareEntry",
    "ShareListResult",
]
