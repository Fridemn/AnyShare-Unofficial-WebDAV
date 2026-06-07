"""Data models for the AnyShare Unofficial library."""

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

__all__ = [
    # auth
    "AuthConfig",
    "LoginConfig",
    "ThirdAuthConfig",
    "UserBasicDepInfo",
    "UserBasicInfo",
    "UserInfo",
    # common
    "DepInfo",
    "DocLibBrief",
    "DocLibInfo",
    "UserIdentity",
    # contact
    "ContactGroup",
    "ContactGroupListResponse",
    "ContactPersonListResponse",
    "DepartmentInfo",
    "DepartmentUserInfo",
    "DepartmentUserListResponse",
    # fileobj
    "AnyObject",
    "FileItem",
    "FileMetadata",
    "FolderContent",
    "FolderItem",
    "ItemDetail",
    # messages
    "NotificationEntry",
    "NotificationListResult",
    # operations
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
    # permission
    "AutoLockInfo",
    "PermissionCheckResult",
    "ShareDocConfig",
    # quota
    "QuotaInfo",
    # sharing
    "BlockedDocLib",
    "BlockedDocLibListResult",
    "LinkConfig",
    "PermConfig",
    "ShareEntry",
    "ShareListResult",
]
