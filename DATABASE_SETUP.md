# EDEN BOUNTY — Database Setup and Recovery

## Database isolation

There is no production database provisioned. The development database is expected to remain at
Alembic revision `0008_portal_accounts_orders_investments`. Staging must use a separately provisioned
PostgreSQL 16 database with unique credentials. Never run the staging `migrate`, `seed`,
`create-admin`, test-suite, restore, or cleanup commands against development or production.
Do not copy development records into staging wholesale.

For managed PostgreSQL use TLS and a direct connection or a session-mode pooler. SQLAlchemy uses
`asyncpg` prepared statements, so transaction-mode poolers are unsupported. Use a least-privilege
role that can create/own the application schema objects for Alembic. The app needs no superuser,
CREATEDB, CREATEROLE, replication, or access to other schemas. Use encrypted storage at rest.

### Permission model

Use two dedicated staging roles:

- **Migration role:** Used by Alembic to create and alter application database objects. It needs CONNECT on the staging database, USAGE and CREATE on the application schema, and ownership of the application objects it must alter.
- **Runtime role:** Used by the application. It needs CONNECT on the staging database, USAGE on the application schema, and the required data-access permissions. It must not have schema ownership or migration privileges.

Use the same migration role consistently for all staging migrations so that it owns the objects created by Alembic. Existing objects must be owned by that role or have the required owner-level authority before migrations run. Ordinary GRANT statements do not transfer object ownership.

Example grants, executed by the database owner:

```sql
GRANT CONNECT ON DATABASE <staging_database> TO <migration_role>;
GRANT USAGE, CREATE ON SCHEMA public TO <migration_role>;

GRANT CONNECT ON DATABASE <staging_database> TO <runtime_role>;
GRANT USAGE ON SCHEMA public TO <runtime_role>;

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA public TO <runtime_role>;

GRANT USAGE, SELECT
ON ALL SEQUENCES IN SCHEMA public TO <runtime_role>;

ALTER DEFAULT PRIVILEGES FOR ROLE <migration_role>
IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO <runtime_role>;

ALTER DEFAULT PRIVILEGES FOR ROLE <migration_role>
IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES TO <runtime_role>;
```

The default privileges apply to future objects created by the specified migration role in the `public` schema. If another role creates application objects, configure corresponding default privileges for that role as well.

Do not grant the runtime role SUPERUSER, CREATEDB, CREATEROLE, replication privileges, or ownership of application schema objects.

Connection URL:

```text
postgresql+asyncpg://<staging-user>:<url-encoded-password>@<host>:<port>/<staging-database>?ssl=require
```

Use URL-encoding for reserved password characters. The app and Alembic both support percent-encoded
passwords. `DATABASE_URL` in `.env.staging` must point to the staging database only.

## Authoritative Alembic chain

The active graph has one head:

```text
0001_initial_schema
  → 0002_add_enquiry_idempotency
  → 0005_optional_contact_nullable
  → 0007_align_index_names_with_models
  → 0008_portal_accounts_orders_investments
  → 0009_account_security
  → 0010_registration_verification
  → 0011_consolidate_building_promotions
  → 0012_deactivate_shisha_and_axe_oil (current head)
```
### Deferred migration revisions

Revisions 0003, 0004 and 0006 are stored under backend/alembic/deferred/ and are excluded from the active migration graph.

They were deferred because their migration logic is incompatible with the current application models and migration execution path. Revision 0003 introduces a separate notification-worker security model and requires additional database roles that are not part of the current application setup. Revision 0004 duplicates an earlier contact-number migration, while 0006 merges the deferred branches.

Do not apply these revisions as part of the active migration sequence. The active migration chain is listed above.

The migration environment in backend/alembic/env.py rejects databases stamped with deferred revision identifiers. Deferred migration files can be inspected separately using the configuration in backend/alembic/deferred/.

## Provisioning staging PostgreSQL

Create a new managed PostgreSQL 16 project/instance in Singapore (or a dedicated database with
separate credentials and backup boundary) and label it as staging. Do not select the development
or future production project. Enable provider storage encryption and database backups. Prefer a
direct endpoint or session pooler with TLS; set the staging role and database name in the team's
secured inventory. Do not place credentials in this document, shell history, or ticket output.



## Pre-migration backup

Before any staging migration, dump the staging database and back up the investor documents volume, and verify that both backups are readable. Backups must be encrypted on the staging server, copied off-server, and never overwritten.

Keep age **public recipients** in a protected file on the staging server. Never require or store private age identity keys on the staging server. The database backup must be encrypted on the staging server directly as it is streamed from `pg_dump`, ensuring no unencrypted dump touches disk. `SYNC_URL` must point to the same staging database as `DATABASE_URL`, using the libpq prefix (`postgresql://`) and `sslmode=require`.

### Database backup

Run this on the staging server in a restricted shell. Set `SYNC_URL` and `AGE_RECIPIENTS_FILE` securely without echoing their values. The staging server must have access only to the age public recipients file (`AGE_RECIPIENTS_FILE`), never the private identity keys. The database backup is encrypted directly on the staging server before writing to disk.

```bash
set -euo pipefail
umask 077

: "${SYNC_URL:?SYNC_URL is not set}"
: "${AGE_RECIPIENTS_FILE:?AGE_RECIPIENTS_FILE is not set}"

mkdir -p backups

stamp="$(date +%Y%m%d-%H%M%S)"
tmp="$(mktemp "backups/.staging-db-${stamp}.XXXXXX.partial")"
final="backups/staging-db-${stamp}.dump.age"

trap 'rm -f "$tmp"' EXIT

test ! -e "$final"

pg_dump --format=custom --no-owner --no-privileges "$SYNC_URL" \
  | age -R "$AGE_RECIPIENTS_FILE" > "$tmp"

test -s "$tmp"

ln "$tmp" "$final"
rm "$tmp"
trap - EXIT

sha256sum "$final"
```

The procedure stops if a command or pipeline fails. Any incomplete temporary file is removed automatically by the EXIT trap. Never overwrite an existing backup.

Copy the encrypted final artifact off-server. Database decryption and `pg_restore --list` verification must happen on a trusted machine holding the matching private key, never on the staging server:

```bash
age -d -i "$PRIVATE_KEY_FILE" "$DATABASE_DUMP" \
  | pg_restore --list - >/dev/null
```

Do not consider the database backup verified until this decryption and archive-inspection test succeeds on the trusted machine. Verify its SHA-256 hash after transfer.

### Investor document backup

Back up `investor_documents` at the same time using `deploy/backup-documents.sh`, with:

- `COMPOSE_PROJECT_NAME=edenbounty-staging`
- `AGE_RECIPIENTS_FILE` set to the protected public-recipient file on the staging server.

Verify that the script identifies the staging volume, not the default production-named volume. The backup is streamed directly into `age` and encrypted on the staging server before touching disk.

The script installs an EXIT trap (`trap 'rm -f "$TMP"' EXIT`) that automatically removes any incomplete temporary file if the process fails or is interrupted. Failed partial archives do not remain on disk. Once successfully encrypted and verified non-empty, the file is atomically published to its final timestamped archive path.

Keep the database and investor-document backups together as a matched backup set.

### Backup verification

Both database decryption / `pg_restore --list` verification and investor document archive verification must happen on a trusted machine holding the matching private key. The private key must never be copied to or stored on the staging server.

Before migration, verify the investor document archive on the trusted machine:

```bash
age -d -i "$PRIVATE_KEY_FILE" "$DOCUMENT_ARCHIVE" | tar tzf - >/dev/null
```

Both `$PRIVATE_KEY_FILE` and `$DOCUMENT_ARCHIVE` must point to actual local file paths on the trusted verification machine. The private key must never be copied to the staging server.

Similarly, verify the database backup on the trusted machine following the main verification instructions under Database backup.

Before migration, confirm:

1. The database backup exists and its encrypted file can be decrypted and inspected on the trusted machine using `pg_restore --list`.
2. The investor-document archive exists and can be decrypted and verified on the trusted machine using `tar tzf`.
3. Both backup artifacts have been copied off-server.
4. Their SHA-256 hashes have been recorded and verified.
5. The backup pair belongs to the intended staging environment.

## Migration procedure — staging only

Only after verifying the staging project/database identity and the backup pair, use:

```bash
DC='docker compose -p edenbounty-staging -f docker-compose.prod.yml --env-file .env.staging'
$DC config -q
$DC build
$DC --profile ops run --rm migrate
$DC --profile ops run --rm seed
$DC --profile ops run --rm create-admin
```

The migration command is `alembic upgrade head` and should finish at `0012_deactivate_shisha_and_axe_oil`.
Seed affects reference divisions and roles only. The admin CLI prompts for the initial staging
SUPER_ADMIN password without echoing it. Do not run these commands with `.env`, `.env.production`,
or any database URL other than the specifically provisioned staging URL.

## Revision 0009 — existing account email conflicts

Migration `0009_account_security` checks that account email addresses in
`admin_users` and `portal_users` are normalized and unique across both tables.
It stops before applying schema changes if it finds conflicts.

If the migration reports an existing-data conflict, run these read-only
diagnostic queries against the specifically provisioned staging database.

Find emails that are not lowercase and trimmed:

```sql
SELECT 'admin_users' AS table_name, id, email
FROM admin_users
WHERE email <> lower(btrim(email))
UNION ALL
SELECT 'portal_users', id, email
FROM portal_users
WHERE email <> lower(btrim(email));
```
```sql
SELECT lower(btrim(email)) AS normalized_email,
       array_agg(account_type || ':' || id) AS accounts
FROM (
    SELECT 'admin_users' AS account_type, id, email FROM admin_users
    UNION ALL
    SELECT 'portal_users' AS account_type, id, email FROM portal_users
) AS all_accounts
GROUP BY lower(btrim(email))
HAVING count(*) > 1;
```

## Restore rehearsal — isolated targets only

Do not automatically normalize, delete, or deactivate conflicting accounts.

Take and verify a backup first. Have the business owner review the affected accounts and approve remediation for each record before changing data.

After the approved remediation is complete, rerun the migration against staging.

Restore only into a newly created, empty, separately named restore-test database and a newly
created empty Docker volume. Confirm both targets in advance. Never use `--clean` against a source
or shared database and never extract a document archive into an existing volume. For a disposable
database:

```bash
age -d -i <private-key-file> <encrypted-dump> | pg_restore --no-owner --no-privileges --dbname "$RESTORE_TEST_SYNC_URL"
```

For documents, decrypt to the fresh empty volume (example volume names must be checked first):

```bash
age -d -i <private-key-file> <encrypted-document-archive> \
  | docker run --rm -i -v <new-empty-restore-volume>:/data alpine:3.20 tar xzf - -C /data
```

Verify restored table/revision state and document checksums on those isolated targets. Record the
restore result. Do not use a production or development URL or volume for restore verification.

## Test suite database

The backend suite contains destructive fixtures. It requires an explicit `TEST_DATABASE_URL`
whose database name has a standalone `test` marker and differs from the app database. Run it only
against a disposable test database, never the development, staging, or production database. The
guard in `backend/tests/conftest.py` checks the target name and connection before destructive
fixtures run.
