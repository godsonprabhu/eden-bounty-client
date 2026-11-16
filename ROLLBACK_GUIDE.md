# EDEN BOUNTY — Staging Rollback Guide

This runbook is for the isolated `edenbounty-staging` Compose project only. No rollback or restore
command in this file is approved for development or production. Confirm `.env.staging`, the Compose
project name, hostname, and database identity before each operation. Preserve existing backups and
keep prior image tags available.

```bash
DC='docker compose -p edenbounty-staging -f docker-compose.prod.yml --env-file .env.staging'
```

## Before a staging release

- Record the checked-out commit and immutable `RELEASE_TAG`.
- Keep the previous web and API images; do not run broad image pruning.
- Take an encrypted database dump and encrypted `investor_documents` volume backup as a matched
  set before any migration. Verify both artifacts and copy them off the server.
- Verify the Compose file and env file identify staging only with `$DC config -q`.

## Application-only rollback

If the schema is compatible and the fault is in application code, restore the previous staging
commit/image tag in the staging checkout and `.env.staging`, then:

```bash
$DC config -q
$DC up -d --no-build
$DC ps
curl -fsS https://staging.edenbounty.org/api/v1/health
```

Do not change `DATABASE_URL` to development or production during a rollback. Do not remove named
volumes; `down -v` deletes staging documents and Caddy certificates.

## Database recovery

Prefer a forward fix. Alembic downgrade may drop tables/columns or discard invitation-token state;
do not improvise downgrade targets. Migration 0009 is an intermediate revision that adds
`portal_auth_tokens`, `account_email_registry`, triggers, and email constraints over 0008. The current active Alembic head is `0012_deactivate_shisha_and_axe_oil`, following revisions 0010, 0011, and 0012. The
development database is expected to remain at 0008. No rollback step here authorizes changing it.

If staging data must be restored, use the verified pre-migration database backup and matching
document backup, but restore into a **new, empty, separately named staging recovery database and
new empty volume**. Confirm target identity and availability first. Do not use `--clean`, do not
restore over the source database, and do not extract into an existing document volume. After
validation, an operator may explicitly point only the staging env file to those recovery targets.
Record data loss relative to the backup timestamp. See `DATABASE_SETUP.md` for encrypted restore
commands.

## Configuration rollback

Before changing `.env.staging`, make a mode-600 copy whose destination is confirmed not to exist;
do not overwrite a prior copy. Restore the chosen copy only after verifying its staging database,
hostname, and image tag. Then validate with `$DC config -q` and recreate affected services with
`$DC up -d`. Never share file contents or rendered Compose output.

## DNS and stop procedure

For a staging outage, first stop `frontend` and `backend` or stop the Compose project; preserve
volumes. Change only the staging DNS record if needed. Do not alter apex/www or mail records.
Keep TCP 80/443 available if Caddy should continue certificate renewal. Avoid `docker compose down
-v` unless authorized deletion of all staging volumes is explicitly intended.

## Recovery checklist

- [ ] Confirmed `edenbounty-staging`, `.env.staging`, staging hostname, and staging database.
- [ ] Previous image tag and source commit recorded.
- [ ] Encrypted database and document backups readable and stored off-host.
- [ ] Any restore targets are new, empty, and isolated; existing backups/volumes preserved.
- [ ] Health, login, portal access, and document retrieval checked after recovery.
- [ ] Migration revision and incident notes recorded.
