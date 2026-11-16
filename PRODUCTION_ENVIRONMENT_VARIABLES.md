# EDEN BOUNTY — Deployment Environment Variables

This reference covers the existing Compose deployment for staging or production. Keep separate
protected env files, credentials, databases, hostnames, and Compose project names for each
environment. The repository's `.env.production.example` is the baseline template for configuring
environment files (copy to `.env.staging` for staging, or `.env.production` for production). Completed
env files are ignored by Git and must be mode `600` on the server.

Compose reads the env file only for interpolation; it does not pass every value to every
container. Service-specific allow-lists are in `docker-compose.prod.yml`. Never display rendered
Compose config or env-file contents in shared logs.

## Variables

| Variable | Required | Default / guidance |
|---|---:|---|
| `SITE_DOMAIN` | Yes | Hostname served by Caddy and baked into frontend metadata. Staging: `staging.edenbounty.org`; production: apex domain. Changing it requires a frontend rebuild. |
| `ACME_EMAIL` | Yes | Address for Let's Encrypt notices. |
| `CORS_ORIGINS` | Yes | JSON list of exact HTTPS browser origins. For staging: `["https://staging.edenbounty.org"]`. No wildcard, HTTP, localhost, or production origins in staging. Also checked for sensitive request origins. |
| `DATABASE_URL` | Yes | PostgreSQL 16 SQLAlchemy URL using `postgresql+asyncpg://`; managed DB must use TLS and direct or session-pooler mode. Use a dedicated staging database. URL-encode reserved password characters. |
| `RELEASE_TAG` | Recommended | Immutable unique image tag for release tracking and rollback. Avoid `latest`. |
| `CADDY_GLOBAL_OPTIONS` | No | Empty on real servers; `local_certs` only for local rehearsal. |
| `HTTP_BIND` / `HTTP_PORT` / `HTTPS_PORT` | No | Defaults `0.0.0.0`, `80`, `443`. Change only for isolated local rehearsal. |
| `EDGE_SUBNET` | No | Defaults `172.30.0.0/24`; must not overlap host/VPC networks. API trusts forwarded headers from this Compose network. |
| `TRUSTED_CLOUDFLARE_PROXIES` | No | Defaults `[]`. Only set published Cloudflare IP ranges if Cloudflare proxying is intentionally enabled. |
| `CSP_MODE` / `CSP_REPORT_URI` | No | Defaults `enforce` / empty. `report-only` is for diagnosis; `off` is emergency-only. |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT` | No | Defaults `5`, `5`, `30`; API connections total at most 10, plus a migration connection. |
| `SMTP_ENABLED` | No | Defaults `false`. Enable only after controlled-mailbox testing and protected credentials are configured. |
| `SMTP_HOST` | No | Hostinger Email default `smtp.hostinger.com`; confirm in hPanel for the actual mailbox. |
| `SMTP_PORT` / `SMTP_USE_SSL` | No | `465` / `true` for implicit SSL. Hostinger also documents `587` with STARTTLS; use `SMTP_PORT=587` and `SMTP_USE_SSL=false` for that mode. |
| `SMTP_USER` / `SMTP_PASSWORD` | If SMTP enabled | Full mailbox address and mailbox password. Secrets; store in server-side env file only. |
| `OPERATIONS_NOTIFY_EMAIL` | No | Compose passes this legacy setting, but current application code has no consumer for it. It does not configure invitation/reset delivery. |
| `DOCUMENT_SCAN_MODE` | No | Defaults `off`; values `off` or `clamav`. ClamAV is optional and fails closed if unavailable. |
| `CLAMAV_HOST` / `CLAMAV_PORT` | No | Defaults `clamav` / `3310`; used with Compose `scan` profile. |
| `PG_DB` / `PG_USER` / `PG_PASSWORD` | Self-hosted DB only | For Compose `selfhosted-db`; use a unique strong password and encrypted host disk. Not used for managed PostgreSQL. |

Compose fixes `APP_ENV=production`, `DEBUG=false`, `WORKERS=1`, `PUBLIC_SITE_URL=https://${SITE_DOMAIN}`,
`TRUSTED_PROXIES` to the edge subnet, and `PRIVATE_STORAGE_DIR=/var/lib/edenbounty/private`.
`PUBLIC_SITE_URL` is therefore HTTPS and must match the environment hostname. `NEXT_PUBLIC_SITE_URL`
and `INTERNAL_BACKEND_URL` are build arguments; the browser API base remains same-origin.

`WORKERS=1` is required because rate limits are in memory. `APP_SECRET_KEY` is not currently used
by the production code paths. Session cookie security, SameSite policy, password and throttling
limits, token lifetimes, and document size have safe application defaults; see
`backend/app/core/config.py`. Do not override secure-cookie defaults.

## SMTP behavior and Hostinger

The SMTP sender uses Python's standard SMTP client with certificate-validated TLS. Port 465 uses
implicit TLS; port 587 uses STARTTLS. The From address is `SMTP_USER`. Confirm the current server,
port, encryption, and full mailbox username in Hostinger hPanel → Emails → Manage → Connect Apps &
Devices; these settings can be account-specific. Hostinger's published defaults are
`smtp.hostinger.com:465` with SSL, or port 587 with STARTTLS. See [Hostinger's configuration
guide](https://www.hostinger.com/support/1575756-how-to-get-email-account-configuration-details-for-hostinger-email/).

SMTP is used for customer/investor invitations and administrator-issued reset links synchronously
before the response. A send failure is surfaced as `FAILED`, audited, and the token is revoked.
Forgot-password sends asynchronously after returning a generic response; the outcome is audited
and shown to administrators. A failed send revokes that reset token. `SENT` means accepted by
Hostinger's SMTP server, not delivered to the recipient's inbox. The live Hostinger account has
not yet been tested; verify with a controlled mailbox before relying on delivery. When SMTP is
disabled or credentials are absent, admin-issued links are returned once for secure manual
delivery, while forgot-password requests are recorded for staff follow-up.

## Validation and safety

The production startup guard rejects unsafe CORS, disabled secure cookies, `SameSite=None`,
development database passwords, multiple workers, non-HTTPS public origins, and invalid scanning
modes. Compose's ops `migrate`, `seed`, `create-admin`, and `cleanup` services receive database
credentials. Before running any of them, confirm the selected env file and database identity.

Validate without revealing interpolated values:

```bash
docker compose -p edenbounty-staging -f docker-compose.prod.yml --env-file .env.staging config -q
```

Never reuse staging credentials in production or development. `docker compose config` without
`-q` prints resolved configuration, including secrets, and must not be used in shared output.
