"""Permission and access control models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PermissionCheckResult(BaseModel):
    """Response from POST /api/eacp/v1/perm1/check.

    result == 0 means the permission is granted.
    """

    model_config = ConfigDict(populate_by_name=True)

    result: int = -1  # 0 = allowed


class AutoLockInfo(BaseModel):
    """Response from POST /api/eacp/v1/autolock/getlockinfo."""

    model_config = ConfigDict(populate_by_name=True)

    islocked: bool = False


class ShareDocConfig(BaseModel):
    """Response from POST /api/eacp/v1/perm1/getsharedocconfig.

    Controls which types of sharing are enabled for the user.
    """

    model_config = ConfigDict(populate_by_name=True)

    enable_user_doc_out_link_share: bool = False
    enable_user_doc_property_share: bool = False
    enable_user_doc_inner_link_share: bool = False
