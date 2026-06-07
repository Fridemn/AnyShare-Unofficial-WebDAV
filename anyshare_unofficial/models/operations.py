"""Operation-specific request/response models for file operations."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DownloadAuth(BaseModel):
    """Parsed download authorization from osdownload auth_list."""

    model_config = ConfigDict(populate_by_name=True)

    url: str
    method: str = "GET"

    @classmethod
    def parse_auth_list(cls, auth_list: list[str]) -> "DownloadAuth":
        """Parse the authrequest list from an osdownload response.

        Expected format: ["GET", "https://host/path?AWSAccessKeyId=...&Signature=..."]
        """
        if len(auth_list) != 2:
            raise ValueError(f"Unexpected download auth_list length: {len(auth_list)}")
        if auth_list[0] != "GET":
            raise ValueError(f"Unexpected download auth method: {auth_list[0]}")
        return cls(url=auth_list[1], method=auth_list[0])


class UploadAuth(BaseModel):
    """Parsed upload authorization from osbeginupload auth_list."""

    model_config = ConfigDict(populate_by_name=True)

    url: str
    method: str = "POST"
    aws_access_key_id: str
    content_type: str
    policy: str
    signature: str
    key: str

    @classmethod
    def parse_auth_list(cls, auth_list: list[str]) -> tuple[str, "UploadAuth"]:
        """Parse the authrequest list from an osbeginupload response.

        Expected format:
            ["POST", "https://host/path", "AWSAccessKeyId: xxx",
             "Content-Type: application/octet-stream", "Policy: eyJ...",
             "Signature: ...", "key: ..."]

        Returns (url, UploadAuth).
        """
        if len(auth_list) != 7:
            raise ValueError(f"Unexpected upload auth_list length: {len(auth_list)}")
        if auth_list[0] != "POST":
            raise ValueError(f"Unexpected upload auth method: {auth_list[0]}")

        field_names = (
            "AWSAccessKeyId",
            "Content-Type",
            "Policy",
            "Signature",
            "key",
        )
        fields: dict[str, str] = {}
        for i, field_name in enumerate(field_names, 2):
            raw: str = auth_list[i]
            parts = raw.split(": ", 1)
            if len(parts) != 2 or parts[0] != field_name:
                raise ValueError(f"Unexpected auth field format: {raw}")
            fields[field_name] = parts[1]
        return auth_list[1], cls(
            url=auth_list[1],
            aws_access_key_id=fields["AWSAccessKeyId"],
            content_type=fields["Content-Type"],
            policy=fields["Policy"],
            signature=fields["Signature"],
            key=fields["key"],
        )

    def as_form_data(self) -> dict[str, str]:
        """Return the auth fields as a dict suitable for multipart form upload."""
        return {
            "AWSAccessKeyId": self.aws_access_key_id,
            "Content-Type": self.content_type,
            "Policy": self.policy,
            "Signature": self.signature,
            "key": self.key,
        }


class OsDownloadResult(BaseModel):
    """Full response from POST /api/efast/v1/file/osdownload."""

    model_config = ConfigDict(populate_by_name=True)

    authrequest: list[str]
    client_mtime: int = 0
    editor: str = ""
    modified: int = 0
    name: str = ""
    need_watermark: bool = False
    rev: str = ""
    siteid: str = ""
    size: int = 0


class OsBeginUploadResult(BaseModel):
    """Success response from POST /api/efast/v1/file/osbeginupload."""

    model_config = ConfigDict(populate_by_name=True)

    authrequest: list[str]
    docid: str = ""
    name: str = ""
    rev: str = ""


class OsEndUploadResult(BaseModel):
    """Response from POST /api/efast/v1/file/osendupload."""

    model_config = ConfigDict(populate_by_name=True)

    editor: str = ""
    modified: int = 0
    name: str = ""


class PreduploadResult(BaseModel):
    """Response from POST /api/efast/v1/file/predupload."""

    model_config = ConfigDict(populate_by_name=True)

    match: bool = False


class DirCreateResult(BaseModel):
    """Response from POST /api/efast/v1/dir/create."""

    model_config = ConfigDict(populate_by_name=True)

    creator: str = ""
    docid: str = ""
    editor: str = ""
    modified: int = 0  # epoch microseconds
    rev: str = ""
    create_time: int = 0


class MoveResult(BaseModel):
    """Response from POST /api/efast/v1/file/move."""

    model_config = ConfigDict(populate_by_name=True)

    docid: str = ""


class SuggestNameResult(BaseModel):
    """Response from POST /api/efast/v1/file/getsuggestname or dir/getsuggestname."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = ""


class DirRenameResult(BaseModel):
    """Response from POST /api/efast/v1/dir/rename.

    On success the body is an empty JSON object. On 403, the body contains error details.
    """

    model_config = ConfigDict(populate_by_name=True)

    cause: str | None = Field(default=None)
    code: int | None = Field(default=None)
    message: str | None = Field(default=None)
