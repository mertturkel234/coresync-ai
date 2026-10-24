"""Auth and identity schemas."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    account_type: Literal["vendor", "developer"]
    organization_name: str | None = Field(default=None, max_length=200)

    @field_validator("full_name", "organization_name")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _vendor_needs_org(self) -> RegisterRequest:
        if self.account_type == "vendor" and not (self.organization_name or "").strip():
            raise ValueError("organization_name is required for vendor accounts")
        if not self.full_name:
            raise ValueError("full_name must not be blank")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str


class MembershipOut(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    role: str


class MeResponse(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int
    user: UserOut
    memberships: list[MembershipOut]


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: Literal["developer", "member"] = "developer"


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
