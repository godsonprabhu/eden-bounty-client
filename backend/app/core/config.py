"""Application configuration using Pydantic Settings v2.

Aligns with Phase C13 architecture specifications for EDEN BOUNTY Sdn. Bhd.
"""


import ipaddress

from pydantic import (
    AliasChoices,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def validate_proxy_entry(entry: str, setting_name: str = "TRUSTED_PROXIES") -> str:
    """Validates that a single proxy configuration entry is a valid IPv4/IPv6 address or CIDR network.

    Raises TypeError if entry is not a string, or ValueError if entry is empty or malformed.
    """
    if not isinstance(entry, str):
        raise TypeError(
            f"Configuration error for '{setting_name}': entry must be a string, got {type(entry).__name__}."
        )
    cleaned = entry.strip()
    if not cleaned:
        raise ValueError(
            f"Configuration error for '{setting_name}': entry must be a non-empty string."
        )
    try:
        if "/" in cleaned:
            ipaddress.ip_network(cleaned, strict=False)
        else:
            ipaddress.ip_address(cleaned)
    except ValueError as e:
        raise ValueError(
            f"Configuration error for '{setting_name}': '{cleaned}' is not a valid IPv4/IPv6 address or CIDR network."
        ) from e
    return cleaned


def validate_proxy_configuration(entries: list[str], setting_name: str = "TRUSTED_PROXIES") -> list[str]:
    """Validates a list of proxy entries, rejecting malformed entries with a clear configuration error."""
    if not isinstance(entries, list):
        raise TypeError(
            f"Configuration error for '{setting_name}': expected a list of IP addresses or CIDR blocks, got {type(entries).__name__}."
        )
    return [validate_proxy_entry(entry, setting_name) for entry in entries]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Operational Environment
    APP_ENV: str = Field(default="development", description="Environment: development, staging, production")
    DEBUG: bool = Field(default=False, description="Debug mode flag")
    APP_NAME: str = Field(default="EDEN BOUNTY Sdn. Bhd. API", description="API Service Name")
    APP_VERSION: str = Field(default="2.1.0", description="API Version")
    APP_SECRET_KEY: str = Field(
        default="development_secret_key_change_in_production_32bytes",
        description="Application secret key for cryptographic operations",
    )

    # Server Settings
    HOST: str = Field(default="0.0.0.0", description="Bind host")
    PORT: int = Field(default=8000, description="Bind port")

    # Database Configuration (PostgreSQL 16)
    DB_HOST: str = Field(default="localhost", description="PostgreSQL Host")
    DB_PORT: int = Field(default=5433, description="PostgreSQL Port")
    DB_USER: str = Field(default="eb_db_user", description="PostgreSQL User")
    DB_PASSWORD: str = Field(default="development_db_password_only", description="PostgreSQL Password")
    DB_NAME: str = Field(default="eden_bounty_db", description="PostgreSQL Database Name")
    DATABASE_URL: str | None = Field(
        default=None,
        description="Full SQLAlchemy database connection string (takes precedence if provided)",
    )

    # Connection Pool Settings
    DB_POOL_SIZE: int = Field(default=10, description="SQLAlchemy connection pool size")
    DB_MAX_OVERFLOW: int = Field(default=5, description="SQLAlchemy connection pool max overflow")
    DB_POOL_TIMEOUT: int = Field(default=30, description="SQLAlchemy connection pool timeout (seconds)")
    DB_ECHO: bool = Field(default=False, description="Log raw SQL statements")

    # CORS Origins
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001", "https://edenbounty.org"],
        description="Allowed CORS origins",
    )
    PREVIEW_ORIGIN: str | None = Field(
        default=None,
        description="Explicit authorized preview origin (e.g. https://client-review.trycloudflare.com). Wildcards are disallowed.",
    )

    @field_validator("PREVIEW_ORIGIN", mode="after")
    @classmethod
    def validate_preview_origin(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip().rstrip("/")
        if not cleaned:
            return None
        if "*" in cleaned:
            raise ValueError(f"PREVIEW_ORIGIN must not contain wildcards: {cleaned!r}. Specify the exact authorized preview origin.")
        if not cleaned.startswith(("https://", "http://")):
            raise ValueError(f"PREVIEW_ORIGIN must start with https:// or http://: {cleaned!r}")
        return cleaned

    @property
    def all_allowed_origins(self) -> list[str]:
        """All permitted request origins, combining base CORS origins and the authorized preview origin."""
        origins = [o.rstrip("/") for o in self.CORS_ORIGINS]
        if self.PREVIEW_ORIGIN:
            clean_preview = self.PREVIEW_ORIGIN.rstrip("/")
            if clean_preview not in origins:
                origins.append(clean_preview)
        return origins

    # Session & Authentication Settings (Phase C13.2)
    SESSION_COOKIE_NAME: str = Field(
        default="eb_admin_session",
        description="Name of the HTTP-only admin session cookie",
    )
    CUSTOMER_SESSION_COOKIE_NAME: str = Field(
        default="eb_customer_session",
        description="Name of the HTTP-only customer portal session cookie",
    )
    INVESTOR_SESSION_COOKIE_NAME: str = Field(
        default="eb_investor_session",
        description="Name of the HTTP-only investor portal session cookie",
    )
    LOGIN_FAILURE_LIMIT_PER_IP: int = Field(
        default=30,
        description=(
            "Failed sign-in attempts (any account) allowed per client IP within the window before HTTP 429. "
            "Sized for an office of users behind one address; per-account guessing is limited separately."
        ),
    )
    LOGIN_FAILURE_WINDOW_SECONDS: int = Field(
        default=900,
        description="Sliding window (seconds) for the in-memory failed sign-in limits",
    )
    ACCOUNT_LOCKOUT_MAX_ATTEMPTS: int = Field(
        default=20,
        description=(
            "Consecutive failed attempts against one account, from any address, before the account itself is "
            "locked for LOCKOUT_DURATION_MINUTES. Deliberately higher than LOCKOUT_MAX_ATTEMPTS (which applies "
            "per account and client address) so one attacker cannot lock a real user out from their own network."
        ),
    )

    # Invitation and password-reset links (security remediation, finding 1)
    PUBLIC_SITE_URL: str = Field(
        default="http://localhost:3000",
        description="Public origin used to build invitation and reset links, e.g. https://edenbounty.org",
    )
    INVITATION_TOKEN_TTL_HOURS: int = Field(default=72, ge=1, le=168, description="Invitation link lifetime (hours)")
    RESET_TOKEN_TTL_MINUTES: int = Field(default=30, ge=5, le=120, description="Password reset link lifetime (minutes)")
    EMAIL_VERIFICATION_TOKEN_TTL_HOURS: int = Field(default=24, ge=1, le=168, description="Email verification link lifetime (hours)")
    GOOGLE_CLIENT_ID: str = Field(default="", description="Google OAuth 2.0 Client ID")
    GOOGLE_CLIENT_SECRET: str = Field(default="", description="Google OAuth 2.0 Client Secret")
    PASSWORD_RESET_REQUESTS_PER_HOUR: int = Field(
        default=3,
        description="Forgot-password requests accepted per email address per hour (generic response either way)",
    )
    PASSWORD_RESET_REQUESTS_PER_IP_HOUR: int = Field(
        default=20,
        description="Forgot-password requests accepted per client IP per hour before HTTP 429",
    )
    AUTH_TOKEN_RETENTION_DAYS: int = Field(
        default=7,
        ge=0,
        description="Days a used, revoked or expired invitation/reset token row is kept before cleanup removes it",
    )

    # Investor document malware scanning (security remediation, finding 7)
    DOCUMENT_SCAN_MODE: str = Field(
        default="off",
        description="'off' (structural PDF checks only) or 'clamav' (also scan with clamd; uploads fail closed if it is unreachable)",
    )
    CLAMAV_HOST: str = Field(default="clamav", description="clamd host when DOCUMENT_SCAN_MODE=clamav")
    CLAMAV_PORT: int = Field(default=3310, ge=1, le=65535, description="clamd TCP port")
    CLAMAV_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, description="clamd connect/scan timeout")
    PRIVATE_STORAGE_DIR: str = Field(
        default="private_storage",
        description=(
            "Directory for confidential investor documents. Must be outside any web-served path; "
            "files are only released through authenticated download endpoints."
        ),
    )
    MAX_DOCUMENT_BYTES: int = Field(
        default=15 * 1024 * 1024,
        description="Maximum size of an uploaded investor document (bytes)",
    )
    SESSION_MAX_AGE_SECONDS: int = Field(
        default=28800,  # 8 hours
        description="Admin session lifetime in seconds (8 hours)",
    )
    SESSION_COOKIE_PATH: str = Field(
        default="/",
        description="Path scope for the session cookie",
    )
    SESSION_COOKIE_SAMESITE: str = Field(
        default="lax",
        description="SameSite policy for session cookie: lax, strict, or none",
    )
    SESSION_COOKIE_HTTPONLY: bool = Field(
        default=True,
        description="Enforce HttpOnly flag on session cookie",
    )
    SESSION_COOKIE_SECURE_OVERRIDE: bool | None = Field(
        default=None,
        description="Override for secure cookie flag (None = auto-detect based on APP_ENV)",
    )
    LOCKOUT_MAX_ATTEMPTS: int = Field(
        default=5,
        description="Maximum consecutive failed login attempts before account lockout",
    )
    LOCKOUT_DURATION_MINUTES: int = Field(
        default=15,
        description="Account lockout duration in minutes",
    )
    PASSWORD_MIN_LENGTH: int = Field(
        default=12,
        description="Minimum password length required by policy",
    )

    # Public RFQ Ingestion & Anti-Abuse Settings (Phase C13.3)
    TRUSTED_PROXIES: list[str] = Field(
        default=["127.0.0.1", "::1"],
        description="List of trusted immediate upstream proxy IPs or CIDR blocks whose forwarding headers (X-Forwarded-For) are evaluated.",
    )
    TRUSTED_CLOUDFLARE_PROXIES: list[str] = Field(
        default=[],
        validation_alias=AliasChoices("TRUSTED_CLOUDFLARE_PROXIES", "CLOUDFLARE_PROXIES"),
        description="Explicit list of trusted Cloudflare edge proxy IPs or CIDR blocks. CF-Connecting-IP is trusted ONLY when the immediate peer matches this list.",
    )

    @field_validator("TRUSTED_PROXIES", "TRUSTED_CLOUDFLARE_PROXIES", mode="after")
    @classmethod
    def validate_proxies(cls, v: list[str], info: ValidationInfo) -> list[str]:
        field_name = info.field_name or "TRUSTED_PROXIES"
        return validate_proxy_configuration(v, field_name)
    WORKERS: int = Field(
        default=1,
        description="Number of Uvicorn worker processes. Must be 1 when using in-memory rate limiting without Redis.",
    )
    PUBLIC_RATE_LIMIT_PER_MINUTE: int = Field(
        default=10,
        description="Maximum public requests per minute per IP",
    )
    PUBLIC_SUBMISSION_LIMIT_10MIN: int = Field(
        default=5,
        description="Maximum successful submissions per IP per 10-minute window",
    )
    DUPLICATE_SUBMISSION_WINDOW_SECONDS: int = Field(
        default=60,
        description="Sliding window in seconds to detect and safely de-duplicate identical submissions",
    )
    MAX_PAYLOAD_BYTES: int = Field(
        default=65536,  # 64 KB
        description="Maximum request payload size in bytes for public endpoints",
    )

    # SMTP Transport Configuration (Phase C13.5 — Notification System)
    SMTP_HOST: str = Field(
        default="smtp.hostinger.com",
        description="Hostinger SMTP relay hostname",
    )
    SMTP_PORT: int = Field(
        default=465,
        ge=1,
        le=65535,
        description="SMTP port (465 for implicit SSL/TLS)",
    )
    SMTP_USER: str = Field(
        default="",
        description="Authenticated SMTP username / sender account",
    )
    SMTP_PASSWORD: str = Field(
        default="",
        description="Authenticated SMTP account password / secret",
    )
    SMTP_USE_SSL: bool = Field(
        default=True,
        description="Enforce implicit SSL/TLS for SMTP connection (Port 465)",
    )
    SMTP_ENABLED: bool = Field(
        default=False,
        description="Master switch for live SMTP dispatches. Strictly False in local development.",
    )
    OPERATIONS_NOTIFY_EMAIL: str = Field(
        default="info@edenbounty.org",
        description="Recipient address for operational notifications and security alerts",
    )

    @property
    def is_production(self) -> bool:
        """Determines if the application environment is reliably identified as production."""
        return (self.APP_ENV or "").strip().lower() in {"production", "prod"}

    @model_validator(mode="after")
    def guard_smtp_configuration(self) -> "Settings":
        """Enforces that live SMTP dispatch cannot be enabled outside verified production.

        In local development, automated test environments, or any unrecognized/unidentifiable
        environment, SMTP_ENABLED is strictly and unconditionally forced to False even if
        SMTP_ENABLED=true is supplied via an environment variable or configuration parameter.
        In verified production environments, enabling SMTP requires non-empty credentials
        (SMTP_USER, SMTP_PASSWORD).
        """
        # Fail safely: if live SMTP is requested outside verified production, force it to False
        if self.SMTP_ENABLED and not self.is_production:
            self.SMTP_ENABLED = False

        # In verified production with SMTP explicitly enabled, validate required credentials
        if self.SMTP_ENABLED and self.is_production:
            user_clean = (self.SMTP_USER or "").strip()
            password_clean = (self.SMTP_PASSWORD or "").strip()
            if not user_clean or not password_clean:
                raise ValueError(
                    "SMTP credentials (SMTP_USER, SMTP_PASSWORD) must be configured when SMTP_ENABLED is True in production."
                )

        return self

    @model_validator(mode="after")
    def guard_production_configuration(self) -> "Settings":
        """Fails closed at startup when a production deployment carries development settings.

        Applies only when APP_ENV identifies production; development and test are unaffected.
        """
        if not self.is_production:
            return self

        problems: list[str] = []
        if self.DEBUG:
            problems.append("DEBUG must be false (it exposes /docs and /openapi.json).")
        if not self.CORS_ORIGINS:
            problems.append("CORS_ORIGINS must list the public site origin(s), e.g. [\"https://edenbounty.org\"].")
        for origin in self.CORS_ORIGINS:
            o = origin.strip().lower()
            if o == "*" or "*" in o:
                problems.append(f"CORS_ORIGINS must not contain wildcards ({origin!r}).")
            elif not o.startswith("https://"):
                problems.append(f"CORS_ORIGINS must use https:// in production ({origin!r}).")
            elif any(h in o for h in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")):
                problems.append(f"CORS_ORIGINS must not include local addresses in production ({origin!r}).")
        if self.SESSION_COOKIE_SECURE_OVERRIDE is False:
            problems.append("SESSION_COOKIE_SECURE_OVERRIDE must not disable the Secure cookie flag in production.")
        if (self.SESSION_COOKIE_SAMESITE or "").lower() == "none":
            problems.append("SESSION_COOKIE_SAMESITE=none is not permitted; the site is served same-origin.")
        dev_password = "development_db_password_only"
        if not self.DATABASE_URL and self.DB_PASSWORD in (dev_password, "CHANGE_ME_LOCAL_DEVELOPMENT_PASSWORD"):
            problems.append("Database credentials are still the development defaults; set DATABASE_URL.")
        if self.DATABASE_URL and (dev_password in self.DATABASE_URL or "CHANGE_ME" in self.DATABASE_URL):
            problems.append("DATABASE_URL contains a development placeholder password.")
        if self.WORKERS != 1:
            problems.append("WORKERS must be 1 while rate limiting is in-memory (no Redis).")
        site = (self.PUBLIC_SITE_URL or "").strip().lower()
        if not site.startswith("https://") or any(h in site for h in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")):
            problems.append("PUBLIC_SITE_URL must be the public https:// origin (it is used in invitation and reset links).")
        if (self.DOCUMENT_SCAN_MODE or "").strip().lower() not in {"off", "clamav"}:
            problems.append("DOCUMENT_SCAN_MODE must be 'off' or 'clamav'.")

        if problems:
            raise ValueError("Unsafe production configuration:\n- " + "\n- ".join(problems))
        return self

    @property
    def session_cookie_secure(self) -> bool:
        """Determines if the session cookie must have the Secure flag set."""
        if self.SESSION_COOKIE_SECURE_OVERRIDE is not None:
            return self.SESSION_COOKIE_SECURE_OVERRIDE
        if self.PREVIEW_ORIGIN and self.PREVIEW_ORIGIN.startswith("https://"):
            return True
        return self.is_production

    @property
    def async_database_url(self) -> str:
        """Returns the asyncpg database connection URL."""
        if self.DATABASE_URL:
            # Ensure URL uses asyncpg driver if specified as postgresql://
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def sync_database_url(self) -> str:
        """Returns the sync connection URL (e.g. for offline Alembic inspection)."""
        async_url = self.async_database_url
        if "postgresql+asyncpg://" in async_url:
            return async_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return async_url


settings = Settings()
