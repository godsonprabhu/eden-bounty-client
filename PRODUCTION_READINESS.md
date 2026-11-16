# EDEN BOUNTY — Production Readiness Assessment

> [!IMPORTANT]
> **CURRENT STATUS: NOT PRODUCTION-READY AND NOT DEPLOYED**  
> The EDEN BOUNTY web platform is undergoing pre-release staging preparation. No production or staging server, managed database, domain DNS record, or live email service has been provisioned. This document provides a comprehensive readiness assessment, architectural summary, and operational checklist required before authorizing a production deployment.

---

## 1. Executive Summary & Readiness Disposition

The core application implementation is feature-complete across the public commercial catalogue, customer portal, investor portal, and administrative console. Pre-release verification has been conducted against isolated test environments.

However, the application **cannot be deployed to production immediately** because external cloud infrastructure, managed database services, DNS records, and production communication channels have not yet been provisioned or verified by the client.

### Readiness Status Overview

| Operational Component | Status | Required Action Prior to Production |
|---|:---:|---|
| **Application Source Code** | Complete | Review and tag the approved release version in the handover repository. |
| **Public Services Catalogue** | Complete | Verify commercial copy and business details with executive leadership. |
| **Customer & Investor Portals** | Complete | Review portal workflows and terms in an isolated staging environment. |
| **Administrative Console** | Complete | Provision initial super administrator credentials on staging. |
| **Hosting Infrastructure (VPS)** | **Not Provisioned** | Provision dedicated Ubuntu 24.04 LTS server (2 vCPU, 2–4 GB RAM, 25 GB+ disk, encrypted storage at rest). |
| **Managed Database (PostgreSQL 16)** | **Not Provisioned** | Provision managed PostgreSQL 16 instance with TLS and automated backups. |
| **Domain & DNS Configuration** | **Not Provisioned** | Configure DNS A/AAAA records for staging and production hostnames. |
| **Email Transport (SMTP)** | **Unconfigured** | Configure and test Hostinger business email credentials on staging. |
| **Single Sign-On (Google OAuth)** | **Unconfigured** | Create Google Cloud OAuth credentials (optional; fallback active). |
| **Edge Rate Limiting** | **Not Implemented** | Evaluate and configure reverse-proxy/edge rate limiting before deployment. |
| **Automated Session Cleanup** | **Not Configured** | Configure and verify host cron job for `cleanup` ops service. |
| **Malware Scanning (ClamAV)** | Optional | Evaluate server RAM capacity (requires ~1.5 GB additional memory). |
| **Offsite Backup Repository** | **Not Provisioned** | Set up secure offsite storage for encrypted `age` backup archives. |

---

## 2. System Architecture & Technology Stack

The EDEN BOUNTY platform uses an isolated multi-container architecture orchestrated via Docker Compose:

```text
Browser Client ── HTTPS (443) ──> Caddy (Reverse Proxy & Automatic TLS)
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
       Next.js 16 (Frontend)                       FastAPI (Backend API)
       Internal Port 3000                          Internal Port 8000
                                                             │
                                                             ▼
                                                Managed PostgreSQL 16
                                                (Direct TLS / Session Mode)
```

### Technology Components

- **Frontend Application:**
  - Next.js 16 (App Router, Server Components, standalone output build)
  - React 19, TypeScript, Tailwind CSS, Framer Motion
  - Lucide icons, Three.js visualization components
- **Backend API Service:**
  - FastAPI (Python 3.12+, asynchronous request handling)
  - SQLAlchemy 2.0 Async engine with `asyncpg` driver
  - Pydantic v2 data validation and schema enforcement
  - Alembic database migration management
  - Argon2id cryptographic password hashing (`argon2-cffi`)
- **Edge & Security Gateway:**
  - Caddy 2.10 reverse proxy
  - Automatic HTTPS certificate provisioning via Let's Encrypt / ACME
  - Enforced HTTP to HTTPS redirection and apex domain normalization
  - Content Security Policy (CSP), Strict-Transport-Security (HSTS), X-Content-Type-Options, X-Frame-Options
- **Database Engine:**
  - PostgreSQL 16 (relational database with ACID transaction semantics)
- **Container Environment:**
  - Production Dockerfiles with multi-stage builds
  - Unprivileged non-root runtime user (`appuser`, UID 1001)
  - Read-only container root filesystems (`read_only: true`)
  - No new privileges security option (`no-new-privileges:true`)
  - Log rotation controls (JSON log files capped at 10 MB × 5 files)

---

## 3. Implemented Business Functionality

### A. Public Website & Commercial Catalogue
- **Approved Divisions:** Exactly six active commercial divisions are exposed across navigation, catalogue pages, and RFQ forms:
  1. Mineral Water (`mineral-water`)
  2. Scrap Trading (`scrap-trading`)
  3. Construction / Building Promotion (`construction`)
  4. Petroleum Products (`petroleum-products`)
  5. Furnace Oil (`furnace-oil`)
  6. Drone Solutions (`agricultural-drones`)
- **Service Presentations:** Interactive image sliders displaying three verified commercial photographs per division.
- **Request for Quotation (RFQ):** Multi-step commercial enquiry submission form with client-side validation, server-side sanitization, and duplicate submission idempotency protection.

### B. Customer Portal (`/account`)
- **Public Self-Registration:** Prospective customers register via `/register` with policy-enforced password requirements.
- **Email Verification Flow:** Accounts require verification prior to initial sign-in.
- **Order & Shipment Tracking:** Authenticated customers view assigned purchase orders, shipping statuses, dispatch dates, carrier information, and tracking event histories.
- **Commercial Enquiries:** Customers monitor submitted RFQs and status updates.
- **Tenant Isolation:** Rigorous ownership controls ensure customers can only query their own orders and enquiries; cross-account queries return HTTP 404 (preventing account enumeration).

### C. Investor Portal (`/investors/portal`)
- **Investor Self-Registration:** Dedicated investor registration flow with verification requirement.
- **Portfolio Overview:** Visibility into recorded capital allocations, investment dates, active investment totals, and investment status classifications.
- **Allocation Tracking:** Breakdown of investment amounts and percentage shares across commercial business divisions. The platform displays recorded principal amounts only. It does not calculate or project financial returns, profits, yields, valuations, or distributions.
- **Corporate Updates:** Direct access to verified executive announcements and investor bulletins.
- **Confidential Document Room:** Streaming PDF retrieval for investment agreements, financial statements, and compliance certificates. Investor documents are stored in a private persistent Docker volume outside the web root, with restricted filesystem permissions. Backup archives are encrypted using age public-key encryption. Runtime disk encryption depends on the hosting infrastructure.

### D. Administrative Console (`/admin`)
- **Role-Based Access Control (RBAC):** Gated access for `SUPER_ADMIN` and `OPERATIONS_ADMIN` personnel.
- **Enquiry Management:** Full enquiry lifecycle handling: division filtering, priority assignment, status updates, and CSV export.
- **Order Administration:** Order creation, milestone updating, and shipment tracking event management.
- **User Account Administration:** Account activation, deactivation, password reset link generation, and administrative email verification.
- **Audit Logging:** Immutable, tamper-evident security audit trail recording all administrative actions, sign-in events, status transitions, and authorization failures.

---

## 4. Authentication, Authorization & Security Architecture

### Session Management
- **First-Party Secure Cookies:** HTTP-only, secure, `SameSite=Lax` cookies partitioned by portal role:
  - `eb_customer_session` (Customer Portal)
  - `eb_investor_session` (Investor Portal)
  - `eb_admin_session` (Administrative Dashboard)
- **Token Protection:** Raw session tokens are never stored in plaintext; database records store cryptographic hashes.
- **CSRF Defense:** State-changing administrative operations require an `X-CSRF-Token` header matching the authenticated session.
- **Origin Validation:** Strict validation against configured `CORS_ORIGINS` on all sensitive authentication and mutation requests.

### Password & Account Security
- **Hashing Standard:** Argon2id with memory-hard parameters.
- **Password Policy:** Minimum 10 characters, requiring uppercase, lowercase, numeric, and special characters.
- **Unified Account Registry:** Centralized email registry (`account_email_registry`) enforcing unique normalized emails across all user categories (preventing cross-role credential collisions).
- **Brute-Force & Lockout Controls:**
  - Progressive IP-level request throttling for failed authentication attempts.
  - Per-account lockouts after repeated consecutive failed attempts.

---

## 5. Database Architecture & Migration Status

### PostgreSQL & Alembic Migration State
The active database schema is fully defined through 9 sequential, linear Alembic migrations:

```text
0001_initial_schema
  → 0002_add_enquiry_idempotency
  → 0005_optional_contact_nullable
  → 0007_align_index_names_with_models
  → 0008_portal_accounts_orders_investments
  → 0009_account_security
  → 0010_public_registration_and_verification
  → 0011_consolidate_building_promotions
  → 0012_deactivate_shisha_and_axe_oil (CURRENT ACTIVE HEAD)
```

- **Active Head Revision:** `0012_deactivate_shisha_and_axe_oil`.
- **Deferred Revisions:** Revisions `0003`, `0004`, and `0006` are stored in `backend/alembic/deferred/` and excluded from the active migration graph. The runtime migration environment rejects databases carrying deferred revisions.
- **Pre-Migration Safety Checks:** Migration `0009` includes pre-flight conflict detection that halts execution if non-normalized or duplicate account emails exist, preventing accidental data corruption.
- **Migration Execution Status:** Verified and passed on disposable testing databases. **Staging and production databases have not yet been migrated.**

### Database Permission Model
Production deployments must use two distinct database roles:
1. **Migration Role:** Possesses `CREATE`, `USAGE`, and schema ownership privileges required to execute Alembic DDL migrations.
2. **Runtime Role:** Restricted least-privilege role used by the FastAPI application during normal operations (`SELECT`, `INSERT`, `UPDATE`, `DELETE`). It must **never** hold superuser, `CREATEDB`, `CREATEROLE`, or DDL permissions.

---

## 6. Integration & External Service Status

### A. SMTP Email Transport
- **Default Provider:** Hostinger Email (`smtp.hostinger.com`, port `465` with implicit SSL/TLS; alternative port `587` with STARTTLS).
- **Current Status:** `SMTP_ENABLED=false` by default. No live emails have been dispatched from the production domain.
- **Manual Verification Fallback:** When SMTP is disabled (`manual delivery mode`), single-use verification links are never exposed in public HTTP responses. Instead, authorized administrators must retrieve the activation link through the administrative console or via local CLI (`python -m app.cli.verify_account`) and communicate it securely to the account holder.

### B. Google OAuth 2.0 Single Sign-On
- **Current Status:** **Unconfigured** (graceful fallback active).
- **Behavior:** When `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are blank, `/api/v1/auth/google/url` safely reports `{"configured": false}`. Standard email and password authentication remains fully functional.
- **Activation Requirements:** Requires creating an OAuth 2.0 Web Application credential in the Google Cloud Console with the authorized redirect URI `https://<SITE_DOMAIN>/api/v1/auth/google/callback`.

### C. File & Document Storage
- **Current Status:** **Local volume storage** (Cloud object storage like AWS S3 or Google Cloud Storage is not implemented).
- **Implementation:** Investor documents are stored in a private persistent Docker volume outside the web root, with restricted filesystem permissions. Backup archives are encrypted using age public-key encryption. Runtime disk encryption depends on the hosting infrastructure.
- **Malware Scanning:** An optional ClamAV antivirus integration (`DOCUMENT_SCAN_MODE=clamav`) can scan uploads before saving. If enabled, it requires the Compose `scan` profile and approximately 1.5 GB of dedicated host RAM.

### D. Rate Limiting & Scalability Constraints
- **Single Worker Requirement:** The backend container is strictly pinned to a single worker process (`WORKERS=1`). The API startup sequence enforces this guard and will fail to boot if `WORKERS > 1`.
- **Constraint Cause:** Request throttling, public submission windows, and account lockout tracking are currently managed in-memory within the Uvicorn worker process.
- **Edge Rate Limiting Gap:** Caddy currently does not implement edge rate limiting. Evaluate and configure suitable reverse-proxy or edge protection for public endpoints before production deployment. Do not claim this protection is already implemented.
- **Horizontal Scaling Path:** Before scaling out to multiple containers or multi-worker processes behind a load balancer, rate limiting must be migrated to a centralized shared memory store (such as Redis).

---

## 7. Backup and Recovery Requirements

Staging and production deployments require matched, point-in-time backup sets before any migration or release:

1. **Database Dump:** Generated using `pg_dump --format=custom` and streamed directly into `age` public-key encryption. Unencrypted database dumps must never touch the host disk.
2. **Document Volume Backup:** The `investor_documents` volume must be archived and encrypted using `deploy/backup-documents.sh` concurrently with the database dump.
3. **Key Separation:** The application server must hold only the public `age` encryption recipient key (`AGE_RECIPIENTS_FILE`). Private decryption identity keys must **never** reside on or be transferred to the staging or production server.
4. **Verification Testing:** Backup readability must be verified on a separate trusted workstation using `pg_restore --list` (database) and `tar tzf` (documents).
5. **Restore Safety:** Rehearsals must be conducted strictly into newly created, isolated disposable databases and temporary test volumes. Restorations must never overwrite a running database.

---

## 8. Production Infrastructure Prerequisites

Before scheduling a production deployment, the client must provision and verify the following infrastructure:

```text
[ ] Dedicated Virtual Private Server (VPS)
    - OS: Ubuntu 24.04 LTS (Clean installation, SSH key-only access, non-root deploy user)
    - Hardware: Minimum 2 vCPU, 2 GB RAM (4 GB RAM recommended if ClamAV scanning is enabled), 25 GB+ SSD
    - Host Disk Encryption: The VPS must use encrypted storage at rest, either through cloud-provider encrypted volumes or an appropriately configured disk-encryption solution
    - Software: Docker Engine and Docker Compose plugin (official Docker packages)
    - Network: Inbound TCP 80, 443; outbound HTTPS; strict UFW firewall

[ ] Managed PostgreSQL 16 Database
    - Location: Singapore cloud region (recommended for regional proximity)
    - Configuration: Dedicated instance with TLS/SSL enforced (`sslmode=require`)
    - Connectivity: Direct connection or session-mode pooler (transaction poolers unsupported)
    - Storage: Cloud provider disk encryption at rest and automated point-in-time recovery

[ ] Domain Name & DNS Control
    - DNS A Record: Target VPS IPv4 address configured for apex and subdomains
    - DNS AAAA Record: Target VPS IPv6 address (if IPv6 is enabled on the VPS)
    - Low TTL (300 seconds) during the initial cutover window

[ ] Hostinger Email Account
    - Dedicated business mailbox provisioned (e.g., info@edenbounty.org)
    - Outbound SMTP access verified in hPanel
    - Sender credentials stored securely in password management

[ ] Google Cloud Project (Optional)
    - OAuth 2.0 Web Client ID and Client Secret generated
    - Authorized redirect URI configured for the production domain

[ ] Edge Rate Limiting & Proxy Protection
    - Caddy currently does not implement edge rate limiting. Evaluate and configure suitable reverse-proxy or edge protection for public endpoints before production deployment (do not claim this protection is already implemented)

[ ] Automated Session & Token Cleanup
    - The operations cleanup service requires scheduled execution. Configure and verify the documented host cron job for expired sessions and revoked-token cleanup (do not claim the schedule is active until configured and tested)

[ ] Offsite Encrypted Backup Storage
    - Secure offsite S3-compatible or cold storage bucket for encrypted `.age` archives
    - `age` key pair generated: public recipient key on VPS, private key on secure offline vault
```

---

## 9. Step-by-Step Production Deployment Checklist

### Phase 1: Pre-Deployment Verification
- [ ] Review and approve the final release tag or commit SHA from the client-handover repository.
- [ ] Verify that the target server meets all hardware, OS, and firewall prerequisites.
- [ ] Confirm DNS records resolve correctly to the server's public IP address.
- [ ] Verify that managed PostgreSQL 16 is accessible over TLS using dedicated migration and runtime roles.

### Phase 2: Server Provisioning & Configuration
- [ ] Clone the approved release tag to `/opt/eden-bounty`:
  ```bash
  git clone <client-handover-repository-url> /opt/eden-bounty
  cd /opt/eden-bounty
  git checkout <approved-release-tag-or-commit-sha>
  ```
- [ ] Copy `.env.production.example` to `.env.production` (permissions `600`).
- [ ] Populate all required production environment variables (see [PRODUCTION_ENVIRONMENT_VARIABLES.md](PRODUCTION_ENVIRONMENT_VARIABLES.md)).
- [ ] Validate configuration syntax without disclosing secrets:
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.production config -q
  ```
- [ ] Build production container images:
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.production build
  ```

### Phase 3: Database Migration & Administrative Bootstrap
- [ ] Verify migration head inside the built API container image:
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.production run --rm backend alembic heads
  ```
  *(Expected output: `0012_deactivate_shisha_and_axe_oil (head)`)*
- [ ] Take an initial baseline database backup before schema execution.
- [ ] Apply database migrations:
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.production --profile ops run --rm migrate
  ```
- [ ] Seed reference divisions and system roles:
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.production --profile ops run --rm seed
  ```
- [ ] Create the primary super administrator account via interactive secure prompt:
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.production --profile ops run --rm create-admin
  ```

### Phase 4: Service Startup & Verification
- [ ] Start production services:
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.production up -d
  ```
- [ ] Verify container health:
  ```bash
  docker compose -f docker-compose.prod.yml --env-file .env.production ps
  ```
- [ ] Execute smoke tests against the public origin:
  ```bash
  curl -fsS https://<SITE_DOMAIN>/api/v1/health
  curl -sI https://<SITE_DOMAIN>/ | grep -iE 'strict-transport|content-security-policy'
  ```
- [ ] Verify administrative login and audit event logging.
- [ ] Verify public commercial catalogue rendering and RFQ submission flow.
- [ ] Verify customer and investor portal authentication and tenant isolation boundaries.
- [ ] Test transactional email dispatch using a controlled test mailbox.

### Phase 5: Post-Launch Operational Handover
- [ ] Configure and verify host cron job for daily token and session cleanup (the operations cleanup service requires scheduled execution; do not claim the schedule is active until configured and tested):
  ```cron
  17 3 * * * cd /opt/eden-bounty && docker compose -f docker-compose.prod.yml --env-file .env.production --profile ops run --rm cleanup >> /var/log/edenbounty-cleanup.log 2>&1
  ```
- [ ] Schedule automated daily encrypted database and document backups.
- [ ] Rehearse backup restoration into an isolated disposable test database.
- [ ] Transfer administrative credentials and private encryption keys to authorized company custodians.

---

## 10. Operational Runbook Cross-References

For detailed operational procedures, refer to the accompanying runbooks:
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md):** Complete Docker Compose deployment commands and staging rehearsal steps.
- **[DATABASE_SETUP.md](DATABASE_SETUP.md):** PostgreSQL role definitions, migration mechanics, encrypted backups, and restore rehearsals.
- **[PRODUCTION_ENVIRONMENT_VARIABLES.md](PRODUCTION_ENVIRONMENT_VARIABLES.md):** Exhaustive environment variable specification and validation rules.
- **[ROLLBACK_GUIDE.md](ROLLBACK_GUIDE.md):** Rapid rollback procedures for application, configuration, and database recovery.
