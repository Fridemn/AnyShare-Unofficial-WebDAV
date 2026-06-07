"""Anonymous client for AnyShare sharing link access.

Provides download, upload, and browse capabilities for content shared
via AnyShare sharing links, without requiring user authentication.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote_plus

from anyshare_unofficial._base.client import BaseClient
from anyshare_unofficial.exceptions import AnyShareAuthError, AnyShareInputError
from anyshare_unofficial.models.fileobj import FileItem, FolderContent, FolderItem
from anyshare_unofficial.models.operations import DownloadAuth, OsDownloadResult, OsEndUploadResult
from anyshare_unofficial.types.enums import ObjectMode, OnDup, SortDirection, SortField
from anyshare_unofficial.utils.file import LocalFile
from anyshare_unofficial.utils.gns import is_gns_path


class AnonymousClient(BaseClient):
    """Access shared AnyShare content via a sharing link."""

    def __init__(
        self,
        sharing_link: str,
        base_url: str | None = None,
    ) -> None:
        self._sharing_link = sharing_link
        super().__init__(base_url=base_url)
        self._sharing_id: str | None = None
        self._visit_sharing_link()
        self._logger.debug("Initialized AnonymousClient for sharing link: %s", sharing_link)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _visit_sharing_link(self) -> None:
        """Visit the sharing link to extract the anonymous token.

        The sharing link redirects and sets a cookie named
        'link_token:{sharing_id}' whose value serves as the Bearer token.
        """
        if not self._sharing_link.startswith(f"{self._base_url}/link/"):
            raise AnyShareInputError(f"Invalid sharing link: must start with {self._base_url}/link/")

        r = self._client.get(self._sharing_link, follow_redirects=False)
        if not (200 <= r.status_code < 400):
            r.raise_for_status()

        # Extract sharing ID from the redirect URL
        sharing_id = str(r.url).split("/")[-1]
        if not re.match(r"^[A-Za-z0-9]{16,64}$", sharing_id):
            raise AnyShareInputError(f"Invalid sharing ID format extracted from URL: {sharing_id}")
        self._sharing_id = sharing_id

        token_name = f"link_token:{sharing_id}"
        token_value = self._client.cookies.get(token_name)
        if not token_value:
            # Also try reading from response cookies
            for cookie in self._client.cookies.jar:
                if cookie.name == token_name:
                    token_value = cookie.value
                    break
        if not token_value:
            raise AnyShareAuthError(
                f"Failed to obtain anonymous token from sharing link " f"(expected cookie '{token_name}')"
            )
        self._client.headers["Authorization"] = f"Bearer {token_value}"
        self._logger.debug("Extracted anonymous token for sharing_id=%s", sharing_id)

    # ------------------------------------------------------------------
    # Entry listing
    # ------------------------------------------------------------------

    def list_entries(self) -> list[FileItem | FolderItem]:
        """List top-level entries visible through the sharing link."""
        r = self._get("/api/efast/v1/entry-item")
        data = r.json()
        if not isinstance(data, list):
            raise AnyShareInputError(f"Unexpected entry-item response type: {type(data).__name__}, expected list")

        self._logger.debug("Got %d entries from sharing link", len(data))
        return [_parse_entry_item(d) for d in data]

    def get_first_entry(self) -> FileItem | FolderItem:
        """Return the first entry in the sharing link."""
        return self.list_entries()[0]

    # ------------------------------------------------------------------
    # Folder browsing
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
        """Browse the contents of a folder by its GNS path.

        Parameters:
            gns_path: The GNS path of the folder (e.g. "gns://A/B/C").
            limit: Maximum number of items to return.
            sort: Field to sort by.
            direction: Sort direction.
            mode: Filter to files, dirs, or all.

        Returns:
            FolderContent with dirs, files, and optional doc_lib info.
        """
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
        data: dict = r.json()
        return self._build_folder_content(data, mode=mode)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def get_download_url(
        self,
        file: FileItem,
        *,
        savename: str | None = None,
        authtype: str = "QUERY_STRING",
        use_https: bool = True,
    ) -> tuple[DownloadAuth, OsDownloadResult]:
        """Get a pre-signed download URL for a file.

        Parameters:
            file: The FileItem to download.
            savename: Purified save name (if None, derived from file.name).
            authtype: Auth type for the download URL.
            use_https: Whether to request an HTTPS download URL.

        Returns:
            Tuple of (DownloadAuth with parsed URL, full OsDownloadResult).
        """
        if file.is_dir:
            raise AnyShareInputError("Cannot get download URL for a directory")

        if savename is None:
            savename = re.sub(r'[\\/:\*\?"<>|]', "_", file.name)

        self._logger.debug("Requesting download URL for %s (savename=%s)", file.id, savename)
        r = self._post(
            "/api/efast/v1/file/osdownload",
            json={
                "docid": file.id,
                "authtype": authtype,
                "savename": savename,
                "use_https": use_https,
                "rev": file.rev,
            },
        )
        result = OsDownloadResult.model_validate(r.json())
        download_auth = DownloadAuth.parse_auth_list(result.authrequest)
        self._logger.debug("Got download URL: %s", download_auth.url)
        return download_auth, result

    def download_file(
        self,
        file: FileItem,
        dest_path: str | Path,
        *,
        savename: str | None = None,
        chunk_size: int = 8192,
    ) -> Path:
        """Convenience: download a file to a local path.

        Parameters:
            file: The FileItem to download.
            dest_path: Local destination path (directory or file path).
            savename: Purified save name (defaults to file.name).
            chunk_size: Stream chunk size in bytes.

        Returns:
            Path to the downloaded file.
        """
        dest_path = Path(dest_path)
        if dest_path.is_dir():
            dest_path = dest_path / (savename or file.name)

        auth, _result = self.get_download_url(file, savename=savename)

        self._logger.info("Downloading %s to %s", auth.url, dest_path)
        self._stream_download(auth.url, dest_path, chunk_size=chunk_size)

        self._logger.info("Downloaded to %s", dest_path)
        return dest_path

    # ------------------------------------------------------------------
    # Cookie helpers
    # ------------------------------------------------------------------

    def set_cookie(self, cookie_string: str) -> None:
        """Apply a cookie string and update the authorization header."""
        self._set_cookies_from_string(cookie_string)
        self._update_authorization_header()

    def _update_authorization_header(self) -> None:
        """Update the Authorization header from the current cookies."""
        self._update_authorization_header_from_cookie()

    def refresh_token(self, force: bool = False) -> None:
        """Refresh the OAuth2 token."""
        r = self._get(
            "/anyshare/oauth2/login/refreshToken",
            params={"force": "true" if force else "false"},
        )
        self._update_authorization_header()
        self._logger.debug("Refreshed auth token (force=%s)", force)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_file(
        self,
        local_path: str | Path,
        remote_gns_dir: str,
        *,
        ondup: OnDup = OnDup.OVERWRITE,
    ) -> OsEndUploadResult:
        """Upload a file to a remote GNS directory.

        Parameters:
            local_path: Path to the local file to upload.
            remote_gns_dir: GNS path of the destination directory.
            ondup: Conflict resolution strategy.

        Returns:
            OsEndUploadResult with editor, modified timestamp, and name.
        """
        if not is_gns_path(remote_gns_dir):
            raise AnyShareInputError(f"Not a valid GNS path: {remote_gns_dir}")

        local_file = LocalFile.from_path(local_path)
        try:
            upload_auth, begin_result = self._begin_upload(local_file, remote_gns_dir, ondup=ondup)
            self._do_upload(upload_auth, local_file)
            return self._end_upload(begin_result.docid, begin_result.rev)
        finally:
            local_file.close()


# ------------------------------------------------------------------
# Internal parsing helpers
# ------------------------------------------------------------------


def _parse_entry_item(dto: dict) -> FileItem | FolderItem:
    """Parse a single entry-item DTO into a FileItem or FolderItem."""
    is_dir = dto.get("type") == "folder" or (dto.get("size") is not None and dto["size"] < 0)
    if is_dir:
        dto.setdefault("size", -1)
        return FolderItem.model_validate(dto)
    else:
        return FileItem.model_validate(dto)
