"""Base HTTP client providing shared infrastructure for all AnyShare clients.

Manages httpx.Client lifecycle, request helpers with error mapping,
logging, and cookie/header management hooks.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Self

import httpx

from anyshare_unofficial.exceptions import AnyShareAPIError, AnyShareAuthError, AnyShareInputError, AnyShareNetworkError
from anyshare_unofficial.models.common import DocLibBrief
from anyshare_unofficial.models.fileobj import FileItem, FolderContent, FolderItem
from anyshare_unofficial.models.operations import OsBeginUploadResult, OsEndUploadResult, UploadAuth
from anyshare_unofficial.types.enums import ObjectMode, OnDup
from anyshare_unofficial.utils.cookie import parse_cookie_string
from anyshare_unofficial.utils.file import LocalFile


class BaseClient:
    """Shared foundation for all AnyShare API clients.

    Provides:
    - httpx.Client lifecycle (sync, supports context manager)
    - Request helpers (_get, _post) with unified error mapping
    - Base URL management
    - Structured logging
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = 30.0,
        verify: bool = True,
        headers: dict[str, str] | None = None,
    ) -> None:
        if not base_url:
            raise AnyShareInputError("base_url is required")
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout),
            verify=verify,
            headers=headers or {},
            follow_redirects=False,
        )
        self._logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Send a GET request and raise on error."""
        self._logger.debug("GET %s params=%s", path, params)
        try:
            response = self._client.get(path, params=params)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise AnyShareNetworkError(f"Network error during GET {path}: {exc}", original=exc) from exc
        self._raise_for_error(response)
        return response

    def _post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Send a POST request and raise on error."""
        self._logger.debug("POST %s json=%s data=%s params=%s", path, json, data, params)
        try:
            response = self._client.post(path, json=json, data=data, files=files, params=params)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise AnyShareNetworkError(f"Network error during POST {path}: {exc}", original=exc) from exc
        self._raise_for_error(response)
        return response

    def _raise_for_error(self, response: httpx.Response) -> None:
        """Map httpx / API responses to custom exceptions.

        Hierarchy:
        - 2xx: return silently
        - 401: AnyShareAuthError
        - 4xx/5xx with JSON error body: AnyShareAPIError
        - Other non-2xx: httpx.HTTPStatusError
        """
        if response.is_success:
            return

        status_code = response.status_code

        # Try to parse JSON error body
        error_body: dict[str, Any] | None = None
        try:
            error_body = response.json()
        except Exception:
            pass

        if status_code in (401, 403):
            msg = f"Authentication failed (HTTP {status_code})"
            if error_body and "message" in error_body:
                msg = str(error_body.get("message", msg))
            raise AnyShareAuthError(msg, status_code=status_code)

        if error_body is not None:
            code = error_body.get("code")
            cause = error_body.get("cause")
            message = error_body.get("message", str(error_body))
            raise AnyShareAPIError(
                str(message),
                status_code=status_code,
                code=int(code) if code is not None else None,
                cause_detail=str(cause) if cause else None,
                response_body=error_body,
            )

        response.raise_for_status()

    # ------------------------------------------------------------------
    # Shared client helpers
    # ------------------------------------------------------------------

    def _build_folder_content(self, data: dict, *, mode: ObjectMode) -> FolderContent:
        """Build a FolderContent from the sub_objects API response."""
        dirs: list[FolderItem] = []
        files: list[FileItem] = []

        raw_dirs: list[dict] = data.get("dirs", [])
        raw_files: list[dict] = data.get("files", [])

        if mode in (ObjectMode.ALL, ObjectMode.DIRS):
            dirs = [FolderItem.model_validate(d) for d in raw_dirs]

        if mode in (ObjectMode.ALL, ObjectMode.FILES):
            files = [FileItem.model_validate(f) for f in raw_files]

        doc_lib_raw = data.get("doc_lib")
        doc_lib = DocLibBrief.model_validate(doc_lib_raw) if doc_lib_raw is not None else None

        return FolderContent(
            next_marker=data.get("next_marker", ""),
            dirs=dirs,
            files=files,
            doc_lib=doc_lib,
        )

    def _set_cookies_from_string(self, cookie_string: str) -> None:
        """Parse and apply cookies to the underlying HTTP client."""
        cookies = parse_cookie_string(cookie_string)
        for name, value in cookies.items():
            self._client.cookies.set(name, value)

    def _update_authorization_header_from_cookie(
        self,
        *,
        missing_message: str = "Authorization cookie is missing",
    ) -> None:
        """Update the Authorization header from the current cookies."""
        auth_value = self._client.cookies.get("Authorization")
        if not auth_value:
            raise AnyShareAuthError(missing_message)
        self._client.headers["Authorization"] = auth_value
        self._logger.debug("Updated authorization header from cookies")

    def _stream_download(
        self,
        url: str,
        dest_path: str | Path,
        *,
        chunk_size: int = 8192,
    ) -> Path:
        """Download a pre-signed URL to a local path."""
        dest_path = Path(dest_path)
        with httpx.stream("GET", url, timeout=60.0) as response:
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size):
                    f.write(chunk)
        return dest_path

    def _begin_upload(
        self,
        local_file: LocalFile,
        remote_gns_dir: str,
        *,
        ondup: OnDup,
    ) -> tuple[UploadAuth, OsBeginUploadResult]:
        """Initiate an S3 upload session."""
        self._logger.debug(
            "Initiating upload: %s -> %s (ondup=%s)",
            local_file.name,
            remote_gns_dir,
            ondup.name,
        )
        response = self._post(
            "/api/efast/v1/file/osbeginupload",
            json={
                "use_https": True,
                "reqmethod": "POST",
                "name": local_file.name,
                "docid": remote_gns_dir,
                "ondup": ondup.value,
                "length": local_file.size,
                "client_mtime": int(time.time() * 1_000_000),
                "gns_dir_path": remote_gns_dir,
            },
        )
        result = OsBeginUploadResult.model_validate(response.json())
        _url, upload_auth = UploadAuth.parse_auth_list(result.authrequest)
        return upload_auth, result

    def _post_upload_data(self, upload_auth: UploadAuth, local_file: LocalFile) -> None:
        """Send file data to a pre-signed S3 upload URL."""
        self._logger.debug("Uploading file data to S3: %s", upload_auth.url)
        response = self._client.post(
            upload_auth.url,
            data=upload_auth.as_form_data(),
            files={
                "file": (
                    local_file.name,
                    local_file.handle,
                    "application/octet-stream",
                )
            },
        )
        response.raise_for_status()  # Expect 204
        self._logger.debug("File data uploaded successfully")

    def _do_upload(self, upload_auth: UploadAuth, local_file: LocalFile) -> None:
        """Upload file data to the pre-signed S3 URL."""
        self._post_upload_data(upload_auth, local_file)

    def _end_upload(self, docid: str, rev: str, *, csflevel: int = 0) -> OsEndUploadResult:
        """Finalize an S3 upload session."""
        self._logger.debug("Finalizing upload: docid=%s", docid)
        response = self._post(
            "/api/efast/v1/file/osendupload",
            json={"docid": docid, "rev": rev, "csflevel": csflevel},
        )
        return OsEndUploadResult.model_validate(response.json())

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
