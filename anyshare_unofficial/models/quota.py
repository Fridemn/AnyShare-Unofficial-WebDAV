"""Quota information model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class QuotaInfo(BaseModel):
    """Response from GET /api/efast/v1/quota/user.

    Storage quota in bytes.
    """

    model_config = ConfigDict(populate_by_name=True)

    allocated: int = 0  # Total allocated storage in bytes
    used: int = 0  # Currently used storage in bytes
