"""Pydantic schemas for Administrator Authentication and Session Management.

Phase C13.2 — Aligned with C13-api-specification.md v2.1.0.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.portal import PortalUserPublic


class LoginRequest(BaseModel):
    """Administrator login credentials."""

    email: EmailStr = Field(..., description="Corporate administrator email address")
    password: str = Field(..., min_length=1, description="Account password")


class AdminUserPublic(BaseModel):
    """Public administrator identity representation (no sensitive fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique administrator identifier")
    email: EmailStr = Field(..., description="Administrator email address")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    job_title: str | None = Field(default=None, description="Job title or commercial designation")
    roles: list[str] = Field(default_factory=list, description="Assigned administrative roles")


class AdminUserMeResponse(AdminUserPublic):
    """Extended administrator identity for /auth/me endpoint."""

    last_login_at: datetime | None = Field(default=None, description="Timestamp of last successful login")
    csrf_token: str = Field(..., description="Active session anti-CSRF token")


class LoginResponseData(BaseModel):
    """Login response payload containing authenticated user and session CSRF token.

    ``account_type`` and ``redirect_to`` are decided by the server from the account that was
    authenticated. The client only follows them; it never tells the server which role to use.
    """

    user: AdminUserPublic | PortalUserPublic
    csrf_token: str = Field(..., description="Per-session CSRF token required in X-CSRF-Token header")
    account_type: str = Field(default="ADMIN", description="ADMIN or CUSTOMER")
    redirect_to: str = Field(default="/admin", description="Dashboard path for the authenticated account")


class LoginResponseEnvelope(BaseModel):
    """Standard response envelope for successful authentication."""

    success: bool = True
    data: LoginResponseData


class AuthMeResponseEnvelope(BaseModel):
    """Standard response envelope for current identity endpoint."""

    success: bool = True
    data: AdminUserMeResponse


class LogoutResponseEnvelope(BaseModel):
    """Standard response envelope for session termination."""

    success: bool = True
    message: str = "Logged out successfully"


class RegisterRequest(BaseModel):
    """Public customer or investor registration payload."""

    role: Literal["CUSTOMER", "INVESTOR"] = Field(..., description="Target portal account role (CUSTOMER or INVESTOR only)")
    email: EmailStr = Field(..., description="Business or investor email address")
    password: str = Field(..., min_length=12, max_length=128, description="Account password (min 12 characters)")
    full_name: str = Field(..., min_length=1, max_length=150, description="Full name of representative")
    company_name: str | None = Field(default=None, max_length=200, description="Corporate entity name (optional for investor)")
    contact_number: str | None = Field(default=None, max_length=50, description="Contact phone number")
    country: str | None = Field(default=None, max_length=100, description="Country of operation or incorporation")


class RegisterResponseData(BaseModel):
    """Registration response payload."""

    user: PortalUserPublic
    delivery: str = Field(..., description="EMAIL or MANUAL delivery mode")
    verification_link: str | None = Field(default=None, description="Direct verification link (strictly omitted in public responses)")
    message: str = Field(..., description="Confirmation message")


class RegisterResponseEnvelope(BaseModel):
    """Standard envelope for registration response."""

    success: bool = True
    data: RegisterResponseData


class VerifyEmailRequest(BaseModel):
    """Email verification payload."""

    token: str = Field(..., min_length=1, max_length=128, description="Single-use verification token")


class VerifyEmailResponseEnvelope(BaseModel):
    """Standard envelope for email verification."""

    success: bool = True
    message: str
    redirect_to: str


class ResendVerificationRequest(BaseModel):
    """Request to resend email verification."""

    email: EmailStr = Field(..., description="Registered account email address")


class GoogleAuthUrlResponse(BaseModel):
    """Google OAuth initiation response."""

    configured: bool
    url: str | None = None
    state: str | None = None
    message: str | None = None


class GoogleCallbackRequest(BaseModel):
    """Google OAuth callback payload."""

    code: str = Field(..., min_length=1, description="OAuth authorization code")
    state: str = Field(..., min_length=1, description="Signed OAuth state token")
    role: Literal["CUSTOMER", "INVESTOR"] = Field(..., description="Target portal role")
