"""Authenticated client for full AnyShare API access via cookie-based authentication.

Provides complete file management, user info, sharing, contacts,
departments, permissions, and more.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from anyshare_unofficial._base.client import BaseClient
from anyshare_unofficial.exceptions import AnyShareInputError
from anyshare_unofficial.models.auth import AuthConfig, LoginConfig, UserBasicInfo, UserInfo
from anyshare_unofficial.models.common import DocLibInfo
from anyshare_unofficial.models.contact import (
    ContactGroup,
    ContactGroupListResponse,
    ContactPersonListResponse,
    DepartmentInfo,
    DepartmentListResponse,
    DepartmentUserInfo,
    DepartmentUserListResponse,
)
from anyshare_unofficial.models.messages import NotificationListResult
from anyshare_unofficial.models.fileobj import FileItem, FileMetadata, FolderContent, ItemDetail
from anyshare_unofficial.models.operations import (
    DirCreateResult,
    DownloadAuth,
    MoveResult,
    OsDownloadResult,
    OsEndUploadResult,
    PreduploadResult,
)
from anyshare_unofficial.models.permission import AutoLockInfo, PermissionCheckResult, ShareDocConfig
from anyshare_unofficial.models.quota import QuotaInfo
from anyshare_unofficial.models.sharing import BlockedDocLibListResult, ShareListResult
from anyshare_unofficial.types.enums import DocLibType, ObjectMode, OnDup, SortDirection, SortField
from anyshare_unofficial.utils.file import LocalFile
from anyshare_unofficial.utils.gns import is_gns_path


class AuthenticatedClient(BaseClient):
    """Full AnyShare API access via cookie-based authentication.

    Requires a previously obtained authenticated session cookie.
    """

    def __init__(
        self,
        cookie_string: str,
        base_url: str | None = None,
    ) -> None:
        super().__init__(base_url=base_url)
        self._logger = logging.getLogger("AuthenticatedClient")
        self.set_cookie(cookie_string)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def set_cookie(self, cookie_string: str) -> None:
        """Parse and apply a provided cookie string."""
        self._set_cookies_from_string(cookie_string)
        self._update_authorization_header()

    def _update_authorization_header(self) -> None:
        """Update the Authorization header from cookies."""
        self._update_authorization_header_from_cookie(
            missing_message="Authorization cookie is missing from the provided cookie string"
        )

    def refresh_token(self, force: bool = False) -> None:
        """Refresh the OAuth2 token."""
        self._get("/anyshare/oauth2/login/refreshToken", params={"force": "true" if force else "false"})
        self._update_authorization_header()
        self._logger.debug("Token refreshed (force=%s)", force)

    # ------------------------------------------------------------------
    # User & Config
    # ------------------------------------------------------------------

    def get_config(self) -> AuthConfig:
        """Get configuration."""
        r = self._get("/api/eacp/v1/auth1/configs")
        return AuthConfig.model_validate(r.json())

    def get_login_config(self) -> LoginConfig:
        """Get login configuration."""
        r = self._get("/api/eacp/v1/auth1/login-configs")
        return LoginConfig.model_validate(r.json())

    def get_current_user(self) -> UserInfo:
        """Get the current authenticated user's information."""
        r = self._post("/api/eacp/v1/user/get")
        return UserInfo.model_validate(r.json())

    def get_user_basic_info(self, userid: str) -> UserBasicInfo:
        """Get basic information for a specific user."""
        r = self._post("/api/eacp/v1/user/getbasicinfo", json={"userid": userid})
        return UserBasicInfo.model_validate(r.json())

    # ------------------------------------------------------------------
    # Doc Libraries
    # ------------------------------------------------------------------

    def list_doc_libs(
        self,
        *,
        sort: str = "doc_lib_name",
        direction: SortDirection = SortDirection.ASC,
        type_: list[DocLibType] | None = None,
    ) -> list[DocLibInfo]:
        """List all document libraries accessible to the user."""
        params: dict[str, Any] = {"sort": sort, "direction": direction.value}
        if type_:
            params["type"] = ",".join(t.value for t in type_)

        r = self._get("/api/efast/v1/entry-doc-lib", params=params)
        data = r.json()
        if not isinstance(data, list):
            return []
        return [DocLibInfo.model_validate(d) for d in data]

    def list_classified_doc_libs(self) -> list[dict[str, Any]]:
        """List classified document libraries."""
        r = self._get("/api/efast/v1/classified-entry-doc-libs")
        data = r.json()
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # Folder Browsing
    # ------------------------------------------------------------------

    def browse_folder(
        self,
        gns_path: str,
        *,
        limit: int = 100,
        sort: SortField = SortField.NAME,
        direction: SortDirection = SortDirection.ASC,
        mode: ObjectMode = ObjectMode.ALL,
    ) -> FolderContent:
        """Browse the contents of a folder by GNS path."""
        if not is_gns_path(gns_path):
            raise AnyShareInputError(f"Not a valid GNS path: {gns_path}")

        r = self._get(
            f"/api/efast/v1/folders/{quote_plus(gns_path)}/sub_objects",
            params={
                "limit": limit,
                "sort": sort.value,
                "direction": direction.value,
                "permission_attributes_required": "false",
            },
        )
        return self._build_folder_content(r.json(), mode=mode)

    # ------------------------------------------------------------------
    # File Metadata
    # ------------------------------------------------------------------

    def get_file_metadata(self, docid: str) -> FileMetadata:
        """Get detailed metadata for a file."""
        r = self._post("/api/efast/v1/file/metadata", json={"docid": docid})
        return FileMetadata.model_validate(r.json())

    def get_item_detail(self, object_id: str) -> ItemDetail:
        """Get extended item detail by object ID."""
        r = self._get(f"/api/efast/v2/items/{quote_plus(object_id)}/all")
        return ItemDetail.model_validate(r.json())

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def get_download_url(
        self,
        docid: str,
        *,
        savename: str,
        authtype: str = "QUERY_STRING",
        use_https: bool = True,
        rev: str = "",
    ) -> tuple[DownloadAuth, OsDownloadResult]:
        """Get a pre-signed download URL for a file."""
        r = self._post(
            "/api/efast/v1/file/osdownload",
            json={"docid": docid, "authtype": authtype, "savename": savename, "use_https": use_https, "rev": rev},
        )
        result = OsDownloadResult.model_validate(r.json())
        download_auth = DownloadAuth.parse_auth_list(result.authrequest)
        return download_auth, result

    def download_file(
        self,
        docid: str,
        dest_path: str | Path,
        *,
        savename: str,
        chunk_size: int = 8192,
    ) -> Path:
        """Download a file to a local path.

        Convenience method combining get_download_url + streaming HTTP download.
        """
        dest_path = Path(dest_path)
        if dest_path.is_dir():
            dest_path = dest_path / savename

        auth, _result = self.get_download_url(docid, savename=savename)

        self._logger.info("Downloading to %s", dest_path)
        self._stream_download(auth.url, dest_path, chunk_size=chunk_size)

        self._logger.info("Downloaded to %s", dest_path)
        return dest_path

    # ------------------------------------------------------------------
    # File CRUD
    # ------------------------------------------------------------------

    def delete_file(self, docid: str) -> None:
        """Delete a file by its GNS docid."""
        self._post("/api/efast/v1/file/delete", json={"docid": docid})
        self._logger.debug("Deleted file: %s", docid)

    def move_file(
        self,
        docid: str,
        dest_parent: str,
        *,
        ondup: OnDup = OnDup.RENAME,
    ) -> MoveResult:
        """Move a file to a new parent directory."""
        r = self._post(
            "/api/efast/v1/file/move",
            json={
                "docid": docid,
                "destparent": dest_parent,
                "ondup": ondup.value,
            },
        )
        return MoveResult.model_validate(r.json())

    def get_suggest_name(self, docid: str, name: str) -> str:
        """Get a suggested name for a file."""
        r = self._post(
            "/api/efast/v1/file/getsuggestname",
            json={"docid": docid, "name": name},
        )
        data = r.json()
        return str(data.get("name", name))

    # ------------------------------------------------------------------
    # Directory CRUD
    # ------------------------------------------------------------------

    def create_directory(
        self,
        parent_docid: str,
        name: str,
        *,
        ondup: OnDup = OnDup.RENAME,
    ) -> DirCreateResult:
        """Create a new directory under the given parent."""
        r = self._post(
            "/api/efast/v1/dir/create",
            json={"docid": parent_docid, "name": name, "ondup": ondup.value},
        )
        return DirCreateResult.model_validate(r.json())

    def rename_directory(
        self,
        docid: str,
        new_name: str,
        *,
        ondup: OnDup = OnDup.RENAME,
    ) -> None:
        """Rename a directory.

        Raises AnyShareAPIError on 403 with conflict details.
        """
        self._post(
            "/api/efast/v1/dir/rename",
            json={"docid": docid, "name": new_name, "ondup": ondup.value},
        )
        self._logger.debug("Renamed directory %s to %s", docid, new_name)

    def get_suggest_dir_name(self, docid: str, name: str) -> str:
        """Get a suggested name for a directory."""
        r = self._post(
            "/api/efast/v1/dir/getsuggestname",
            json={"docid": docid, "name": name},
        )
        data = r.json()
        return str(data.get("name", name))

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_file_s3(
        self,
        local_path: str | Path,
        remote_gns_dir: str,
        *,
        ondup: OnDup = OnDup.RENAME,
    ) -> OsEndUploadResult:
        """Upload a file via the S3 upload flow."""
        if not is_gns_path(remote_gns_dir):
            raise AnyShareInputError(f"Not a valid GNS path: {remote_gns_dir}")

        local_file = LocalFile.from_path(local_path)
        try:
            upload_auth, begin_result = self._begin_upload(local_file, remote_gns_dir, ondup=ondup)
            self._do_upload(upload_auth, local_file)
            return self._end_upload(begin_result.docid, begin_result.rev)
        finally:
            local_file.close()

    def predupload_check(self, file_size: int, slice_md5: str) -> bool:
        """Check whether a file can be uploaded via predupload."""
        r = self._post(
            "/api/efast/v1/file/predupload",
            json={"slice_md5": slice_md5, "length": file_size},
        )
        result = PreduploadResult.model_validate(r.json())
        return result.match

    # ------------------------------------------------------------------
    # Quota
    # ------------------------------------------------------------------

    def get_quota(self) -> QuotaInfo:
        """Get current user's storage quota."""
        r = self._get("/api/efast/v1/quota/user")
        return QuotaInfo.model_validate(r.json())

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------

    def check_permission(self, docid: str, perm: str = "display") -> PermissionCheckResult:
        """Check whether the current user has a specific permission on an object."""
        r = self._post("/api/eacp/v1/perm1/check", json={"docid": docid, "perm": perm})
        return PermissionCheckResult.model_validate(r.json())

    def get_share_config(self) -> ShareDocConfig:
        """Get the sharing configuration for the current user."""
        r = self._post("/api/eacp/v1/perm1/getsharedocconfig")
        return ShareDocConfig.model_validate(r.json())

    def get_lock_info(self, docid: str) -> AutoLockInfo:
        """Check whether an object is auto-locked."""
        r = self._post("/api/eacp/v1/autolock/getlockinfo", json={"docid": docid})
        return AutoLockInfo.model_validate(r.json())

    # ------------------------------------------------------------------
    # Contacts
    # ------------------------------------------------------------------

    def get_contact_groups(self) -> list[ContactGroup]:
        """List all contact groups."""
        r = self._post("/api/eacp/v1/contactor/getgroups")
        return ContactGroupListResponse.model_validate(r.json()).groups

    def get_contact_persons(self, groupid: str, *, start: int = 0, limit: int = 30) -> list[dict[str, Any]]:
        """List persons in a contact group."""
        r = self._post(
            "/api/eacp/v1/contactor/getpersons",
            json={"groupid": groupid, "start": start, "limit": limit},
        )
        return ContactPersonListResponse.model_validate(r.json()).userinfos

    # ------------------------------------------------------------------
    # Departments
    # ------------------------------------------------------------------

    def get_department_roots(self) -> list[DepartmentInfo]:
        """List root-level departments."""
        r = self._post("/api/eacp/v1/department/getroots")
        return DepartmentListResponse.model_validate(r.json()).depinfos

    def get_sub_departments(self, depid: str) -> list[DepartmentInfo]:
        """List sub-departments of a given department."""
        r = self._post("/api/eacp/v1/department/getsubdeps", json={"depid": depid})
        return DepartmentListResponse.model_validate(r.json()).depinfos

    def get_department_users(self, depid: str) -> list[DepartmentUserInfo]:
        """List users in a department."""
        r = self._post("/api/eacp/v1/department/getsubusers", json={"depid": depid})
        return DepartmentUserListResponse.model_validate(r.json()).userinfos

    # ------------------------------------------------------------------
    # Share Management
    # ------------------------------------------------------------------

    def list_shares_with_users(self, *, offset: int = 0, limit: int = 20) -> ShareListResult:
        """List documents shared with other users."""
        r = self._get(
            "/api/doc-share/v1/docs-shared-with-users",
            params={"offset": offset, "limit": limit},
        )
        return ShareListResult.model_validate(r.json())

    def list_shares_with_anyone(self, *, offset: int = 0, limit: int = 20) -> ShareListResult:
        """List documents shared publicly (via links)."""
        r = self._get(
            "/api/doc-share/v1/docs-shared-with-anyone",
            params={"offset": offset, "limit": limit},
        )
        return ShareListResult.model_validate(r.json())

    def list_blocked_doc_libs(self, *, offset: int = 0, limit: int = 20) -> BlockedDocLibListResult:
        """List blocked document libraries."""
        r = self._get(
            "/api/doc-share/v1/blocked-doc-lib",
            params={"offset": offset, "limit": limit},
        )
        return BlockedDocLibListResult.model_validate(r.json())

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def get_notifications(self, *, read: bool = False, limit: int = 20) -> NotificationListResult:
        """Get system notifications."""
        r = self._get(
            "/api/message/v1/notifications",
            params={"read": str(read).lower(), "limit": limit},
        )
        return NotificationListResult.model_validate(r.json())

    # ------------------------------------------------------------------
    # Recursive folder traversal convenience
    # ------------------------------------------------------------------

    def walk_folder(
        self,
        gns_path: str,
        *,
        sort: SortField = SortField.NAME,
        direction: SortDirection = SortDirection.ASC,
    ) -> list[FileItem]:
        """Recursively walk a folder tree and collect all files.

        Returns a flat list of all FileItem objects found under the given path.
        Directories are traversed recursively; files are collected.
        """
        all_files: list[FileItem] = []
        content = self.browse_folder(gns_path, sort=sort, direction=direction)

        for folder in content.dirs:
            try:
                all_files.extend(self.walk_folder(folder.id, sort=sort, direction=direction))
            except Exception as exc:
                self._logger.warning("Failed to walk folder %s: %s", folder.id, exc)

        all_files.extend(content.files)
        return all_files
