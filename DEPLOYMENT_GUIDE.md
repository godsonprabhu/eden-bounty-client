# EDEN BOUNTY — Deployment Guide

This guide describes the existing Docker Compose deployment. **Nothing has been deployed.**
Use it first for an isolated staging environment. Production requires a separate approval and
separate infrastructure, credentials, database, DNS, and release procedure.

## Architecture

```text
Browser ── HTTPS ──> Caddy ── /api/* ──> FastAPI ── TLS ──> managed PostgreSQL 16
                           └─ other paths ──> Next.js 16
```

Caddy is the only service publishing ports 80/443. API and frontend containers communicate on
the private Compose network. The API uses SQLAlchemy 2 and Alembic. Customer, investor, and
administrator sessions are first-party secure cookies. Investor PDFs live in the persistent
`investor_documents` volume, outside the web root. The production Dockerfiles run non-root;
application filesystems are read-only. Compose applies `no-new-privileges` and rotated JSON logs.

The API must run one worker: sign-in and public-request limits are in memory and the startup
guard rejects `WORKERS` other than `1`. Scale-out requires shared rate-limit storage first.

## Staging recommendation

Use `staging.edenbounty.org` on one isolated Ubuntu 24.04 LTS VPS (2 vCPU, 2 GB RAM, at least
25 GB disk) with managed PostgreSQL 16 in Singapore. Use a dedicated staging database/project,
not the development or production database. Keep staging's Compose project name
`edenbounty-staging` so its named volumes are separate. Do not add Cloudflare proxying initially.

No domain, DNS record, server, database, or SMTP connection is confirmed as provisioned. Confirm
domain ownership and control of DNS before creating the record. Add only:

| Type | Name | Value | Notes |
|---|---|---|---|
| A | `staging` | `<staging VPS IPv4>` | Required for Caddy ACME validation. |
| AAAA | `staging` | `<staging VPS IPv6>` | Add only if the VPS has working public IPv6. |

Do not change apex/www, MX, SPF, DKIM, or DMARC records for this staging setup. Allow inbound
SSH from a trusted source and TCP 80/443; UDP 443 is optional for HTTP/3. Do not expose PostgreSQL.

Deployment must proceed only from the approved client-handover repository and release tag or
commit SHA once officially reviewed and published. Do not attempt deployment using unapproved
development branches or substitute a different remote commit.

## Server prerequisites

On a fresh server, create a non-root deploy user, install security updates, disable SSH password
authentication after confirming key access, enable a firewall, and install Docker Engine and the
Compose plugin from Docker's official instructions. Ensure the application deployment directory
(e.g. `/opt/eden-bounty`) is created and owned by the deploy user. Keep provider disk encryption enabled. The
VPS needs outbound HTTPS to fetch images/dependencies and outbound SMTP only if mail testing is
planned. Keep SSH accessible before enabling firewall rules.

Managed database requirements and the URL format are in [DATABASE_SETUP.md](DATABASE_SETUP.md).
Use PostgreSQL 16 with TLS and a direct connection or session-mode pooler; transaction-mode
pooling is unsupported. Create a new staging database and credentials. Never copy the development
database wholesale.

## Environment file

On the staging server, copy `.env.production.example` to `.env.staging`, fill in placeholders, and
set permissions to `600`. Store unique database and SMTP credentials in a password manager.
Never commit the completed file or print `docker compose config` output. Required values and
defaults are documented in [PRODUCTION_ENVIRONMENT_VARIABLES.md](PRODUCTION_ENVIRONMENT_VARIABLES.md).

The Compose project name and environment file are explicit in every command below. Verify the
rendered configuration without printing it:

```bash
DC='docker compose -p edenbounty-staging -f docker-compose.prod.yml --env-file .env.staging'
$DC config -q
```

The project name isolates Compose volumes, but **does not isolate a database URL**. Confirm the
database provider/project/database in the password manager and compare it to staging's inventory
before running any database command. Do not use `.env`, `backend/.env`, `.env.production`, or the
development database URL in these commands.

### Google OAuth configuration

Public customer and investor registration support optional Google OAuth 2.0 authentication alongside standard email and password authentication.

To enable Google sign-in:
1. Configure an OAuth 2.0 Client ID in the Google Cloud Console under APIs & Services → Credentials.
2. Add the staging redirect / callback URI to the authorized redirect URIs list:
   `https://staging.edenbounty.org/api/v1/auth/google/callback`
3. Provide the client credentials in `.env.staging`:
   - `GOOGLE_CLIENT_ID=<google-client-id>`
   - `GOOGLE_CLIENT_SECRET=<google-client-secret>`

Google OAuth is currently unconfigured. When `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are omitted or blank, the API safely reports OAuth as unconfigured (`{"configured": false}` at `/api/v1/auth/google/url`), and standard password-based registration and login remain fully functional.

## Staging deployment procedure

These are future commands for the staging host only. Replace `<...>` placeholders; do not execute
until the host, DNS, and staging database have been provisioned and independently checked.

```bash
git clone <client-handover-repository-url> /opt/eden-bounty
cd /opt/eden-bounty
git checkout <approved-release-tag-or-commit-sha>
```

Replace `<client-handover-repository-url>` with the URL of the approved client-handover repository, and replace `<approved-release-tag-or-commit-sha>` with the reviewed and approved release tag or commit SHA. Only reviewed and approved releases should be deployed; do not deploy unapproved or arbitrary commits.

Prepare the staging environment configuration from the template and build the container images:

```bash
cp .env.production.example .env.staging
chmod 600 .env.staging
# Edit .env.staging using the secured procedure; do not put secrets on a command line.
DC='docker compose -p edenbounty-staging -f docker-compose.prod.yml --env-file .env.staging'
$DC config -q
$DC build
```

Verify that the codebase and container runtime contain the complete migration graph up to revision 0012:
- On a fresh server, the host does not have Python virtual environment dependencies installed; verify Alembic directly through the built container runtime:
  ```bash
  $DC run --rm backend alembic heads
  ```
  *(Or alternatively using Docker directly: `docker run --rm edenbounty/api:${RELEASE_TAG:-latest} alembic heads`)*
- Confirm that `alembic heads` displays `0012_deactivate_shisha_and_axe_oil (head)` before proceeding.
- You can also inspect the repository's `backend/alembic/versions/` directory to confirm that `0012_deactivate_shisha_and_axe_oil.py` is present.

Before the migration, verify the database target one last time using the provider dashboard and
the secured staging inventory. Take and verify a database backup and an encrypted document-volume
backup (for a fresh staging install, the document volume may be empty). The development database
is expected to remain at revision 0008. **Never point these commands at it.** Staging starts at
an empty database and must migrate through the complete active chain to 0012:

```bash
$DC --profile ops run --rm migrate
$DC --profile ops run --rm seed
$DC --profile ops run --rm create-admin
$DC up -d
$DC ps
```

The `migrate` task runs `alembic upgrade head`; `head` is `0012_deactivate_shisha_and_axe_oil`.

The active migration chain includes:
- **0009 (`0009_account_security`)**: Checks existing account emails before making schema changes and aborts without changes on conflicts. A new staging database should have no account conflicts. Do not fix conflicts or retry against development or production.
- **0010 (`0010_registration_verification`)**: Adds public customer/investor self-registration, single-use email verification tokens, and Google OAuth support.
- **0011 (`0011_consolidate_building_promotions`)**: Consolidates duplicate Building Promotion services and legacy records into canonical Construction (`EB-DIV-03`).
- **0012 (`0012_deactivate_shisha_and_axe_oil`)**: Deactivates Shisha Tobacco Trading and Axe Oil from active commercial listings while preserving historical records and referential integrity.

Seed creates/updates reference divisions and roles only; create one staging `SUPER_ADMIN` through the interactive CLI prompt (hidden password input).

## HTTPS and smoke checks

After `staging.edenbounty.org` resolves to the VPS and ports 80/443 are reachable, Caddy obtains a
certificate automatically. It redirects HTTP and `www` to HTTPS/apex, adds HSTS and security
headers, and routes `/api/*` to FastAPI. Keep `CSP_MODE=enforce` unless a specific staging issue
requires a time-limited report-only investigation.

```bash
SITE='https://staging.edenbounty.org'
curl -sS -o /dev/null -w '%{http_code}\n' "$SITE/"
curl -sS -o /dev/null -w '%{http_code}\n' "$SITE/api/v1/health"
curl -sSI "$SITE/" | grep -iE 'strict-transport|content-security-policy|x-content-type'
curl -sS -o /dev/null -w '%{http_code}\n' "$SITE/api/v1/docs"  # expect 404
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' "$SITE/admin" # expect login redirect
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' 'http://staging.edenbounty.org/' # expect HTTPS redirect
```

Then verify public pages, admin login, role authorization, customer/investor portal routing,
invitation, password reset, audit events, CSP nonce/no violations, and private document access.
Use synthetic staging records only. The health endpoint reports database connectivity, not an
overall security or backup check.

## SMTP testing and email verification

SMTP is implemented for customer/investor invitation, administrator-issued password-reset links,
account-holder forgot-password links, and public self-registration email verification. For Hostinger Email, the documented default is
`smtp.hostinger.com`, port `465`, implicit SSL; use the complete mailbox address as `SMTP_USER`
and the mailbox password as `SMTP_PASSWORD`. Hostinger documents port `587` with STARTTLS as an
alternative. Verify the exact settings in hPanel → Emails → Manage → Connect Apps & Devices for
the actual mailbox before use. See [PRODUCTION_ENVIRONMENT_VARIABLES.md](PRODUCTION_ENVIRONMENT_VARIABLES.md).

SMTP is disabled by default (`SMTP_ENABLED=false`). To test it on staging, enable it only after placing the credentials
in the protected staging env file, and use an account/mailbox controlled by the organization.
Admin-issued messages are sent before the response: status `SENT` means the SMTP server accepted
the message, not that it reached the inbox; on failure status is `FAILED` and the token is revoked.
Forgot-password returns the same generic response and sends asynchronously; failure is audited
and visible to administrators, and its token is revoked. Confirm arrival, spam placement, and
retry behavior manually. No real Hostinger delivery has yet been tested. Do not test using an
unapproved external recipient.

### Public self-registration email verification behavior

When prospective customers or investors register through `/register`:

- **When `SMTP_ENABLED=true` (email delivery mode):** The verification link is sent to the registrant's registered email address. The public registration response does not contain the verification link.
- **When `SMTP_ENABLED=false` (manual delivery mode):** No verification email is sent. The public registration response reports that an authorized administrator must retrieve the activation link. The response does not expose the verification token or link.
- **Manual verification:** An authorized administrator with the required portal-user permissions can issue a verification link through the admin portal. The link is returned only to the authenticated administrator and must be communicated to the account holder through a trusted channel. Treat it as a sensitive, single-use credential.
- **Email verification:** The account holder submits the verification token through `/auth/verify-email`.
- **Resending verification:** The public resend-verification endpoint does not disclose verification links or tokens, regardless of delivery mode.

Do not expose verification links in public API responses, browser interfaces, application logs, screenshots, or support tickets. Configure and test SMTP before enabling production email delivery.

With SMTP disabled, invitations and administrator-issued password-reset links also require controlled manual delivery. Administrators must communicate those links securely to the verified account holder.
## Backups and restore rehearsal

Back up the PostgreSQL database and `investor_documents` volume at the same point in time. Encrypt
both with `age` public-key recipients on the staging server, copy encrypted artifacts off the VPS, and keep private identity keys
strictly off the staging server.

Both database decryption / `pg_restore --list` verification and investor document archive verification must happen on a trusted machine holding the matching private key, never on the staging server:
- Verify the database dump: `age -d -i "$PRIVATE_KEY_FILE" "$DATABASE_DUMP" | pg_restore --list - >/dev/null`
- Verify the document archive: `age -d -i "$PRIVATE_KEY_FILE" "$DOCUMENT_ARCHIVE" | tar tzf - >/dev/null`

Encrypt DB dump streams directly; the document script (`deploy/backup-documents.sh`) streams the volume directly to `age` and installs an EXIT trap that automatically removes any incomplete temporary file if interrupted, leaving no failed partial archives. Periodically rehearse restores into a separate disposable staging-restore database and a separate temporary volume. Do not restore into the source database or overwrite an existing backup. Full commands, ordering, and verification steps are in [DATABASE_SETUP.md](DATABASE_SETUP.md) and [ROLLBACK_GUIDE.md](ROLLBACK_GUIDE.md).

## Operations

- Daily: run the `cleanup` ops service to remove expired sessions and old used/revoked tokens.
- Monitor `https://staging.edenbounty.org/api/v1/health`; inspect service logs without sharing
  secrets or one-time links.
- Schedule cleanup daily after verifying the checkout and log paths:

  ```cron
  17 3 * * * cd /opt/eden-bounty && docker compose -p edenbounty-staging -f docker-compose.prod.yml --env-file .env.staging --profile ops run --rm cleanup >> /var/log/edenbounty-staging-cleanup.log 2>&1
  ```

- If enabling document scanning, start the `scan` profile, wait for ClamAV health, then set
  `DOCUMENT_SCAN_MODE=clamav` and recreate the backend. Scanning fails closed when ClamAV is
  unavailable. ClamAV needs about 1.5 GB RAM, so this small staging server may need additional RAM.
- Never run `docker compose ... down -v` as a routine action; it deletes named volumes.

## Staging checklist

- [ ] Confirm control of `edenbounty.org` DNS and create only the `staging` record.
- [ ] Provision isolated Ubuntu VPS and managed PostgreSQL 16 staging database.
- [ ] Confirm staging DB identity, TLS, unique credentials, encryption at rest, and backup policy.
- [ ] Create protected `.env.staging`; confirm hostname, exact HTTPS CORS origin, and unique DB.
- [ ] Validate with `config -q`; build the target release commit; review image tags.
- [ ] Take and verify encrypted pre-migration database and document-volume backups.
- [ ] Run migrations through 0012, seed reference data, create staging admin, start the stack.
- [ ] Verify HTTPS, health, CSP, authentication/authorization, portals, audit, SMTP, and documents.
- [ ] Restore backups into isolated targets and document the result.
- [ ] Schedule cleanup and backups; record staging release commit, migration, and image tags.

Staging is not technically ready until the manual infrastructure items above exist and are verified.
