"""Contact and department models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContactGroup(BaseModel):
    """A contact group from POST /api/eacp/v1/contactor/getgroups."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = ""
    groupname: str = ""
    count: int = 0


class ContactGroupListResponse(BaseModel):
    """Response wrapper for contact group list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    groups: list[ContactGroup] = Field(default_factory=list)


class ContactPersonListResponse(BaseModel):
    """Response wrapper for contact person list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    userinfos: list[dict[str, Any]] = Field(default_factory=list)


class DepartmentInfo(BaseModel):
    """A department entry from /api/eacp/v1/department/ endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    depid: str = ""
    name: str = ""
    isconfigable: bool = True


class DepartmentListResponse(BaseModel):
    """Response wrapper for department list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    depinfos: list[DepartmentInfo] = Field(default_factory=list)


class DepartmentUserInfo(BaseModel):
    """A user entry from POST /api/eacp/v1/department/getsubusers."""

    model_config = ConfigDict(populate_by_name=True)

    account: str = ""
    csflevel: int = 0
    mail: str = ""
    name: str = ""
    userid: str = ""


class DepartmentUserListResponse(BaseModel):
    """Response wrapper for department user list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    userinfos: list[DepartmentUserInfo] = Field(default_factory=list)
