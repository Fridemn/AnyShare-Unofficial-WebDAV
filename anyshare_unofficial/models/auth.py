"""Authentication and user information models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from anyshare_unofficial.models.common import DepInfo


class ThirdAuthConfig(BaseModel):
    """Third-party authentication provider configuration."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    config: dict[str, Any] = Field(default_factory=dict)


class AuthConfig(BaseModel):
    """Response from GET /api/eacp/v1/auth1/configs."""

    model_config = ConfigDict(populate_by_name=True)

    csf_level_enum: dict[str, int] = Field(default_factory=dict)
    internal_link_prefix: str = ""
    only_share_to_user: bool = True
    smtp_server_exists: bool = False
    tag_max_num: int = 0
    oemconfig: dict[str, Any] = Field(default_factory=dict)


class LoginConfig(BaseModel):
    """Response from GET /api/eacp/v1/auth1/login-configs."""

    model_config = ConfigDict(populate_by_name=True)

    dualfactor_auth_server_status: dict[str, bool] = Field(default_factory=dict)
    enable_secret_mode: bool = False
    enable_strong_pwd: bool = False
    strong_pwd_length: int = 8
    thirdauth: ThirdAuthConfig | None = None
    vcode_login_config: dict[str, Any] = Field(default_factory=dict)
    vcode_server_status: dict[str, bool] = Field(default_factory=dict)
    windows_ad_sso: dict[str, bool] = Field(default_factory=dict)
    oemconfig: dict[str, Any] = Field(default_factory=dict)


class UserInfo(BaseModel):
    """Response from POST /api/eacp/v1/user/get — current user information."""

    model_config = ConfigDict(populate_by_name=True)

    account: str
    agreedtotermsofuse: bool = False
    csflevel: int = 0
    directdepinfos: list[DepInfo] = Field(default_factory=list)
    freezestatus: bool = False
    ismanager: bool = False
    leakproofvalue: int = 0
    mail: str = ""
    name: str = ""
    needrealnameauth: bool = False
    needsecondauth: bool = False
    pwdcontrol: int = 0
    roleinfos: list[Any] = Field(default_factory=list)
    roletypes: list[Any] = Field(default_factory=list)
    telnumber: str = ""
    type: str = "user"
    userid: str = ""
    usertype: int = 0


class UserBasicDepInfo(BaseModel):
    """Department fragment returned by POST /api/eacp/v1/user/getbasicinfo."""

    model_config = ConfigDict(populate_by_name=True)

    depid: str | None = None
    name: str | None = None
    deppath: str | None = None


class UserBasicInfo(BaseModel):
    """Response from POST /api/eacp/v1/user/getbasicinfo."""

    model_config = ConfigDict(populate_by_name=True)

    directdepinfos: list[UserBasicDepInfo] = Field(default_factory=list)
