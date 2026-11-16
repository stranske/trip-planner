"""Request and response schemas for account authentication."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class SessionUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: str
    display_name: str


class SessionResponse(BaseModel):
    user: SessionUserResponse


class LogoutResponse(BaseModel):
    signed_out: bool = True
