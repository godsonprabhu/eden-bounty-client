# Deferred migrations (not part of the active Alembic graph)

These three revisions were moved here, **unchanged**, on 2026-11-12 during production-readiness review.
Alembic only loads `alembic/versions/`, so they are not applied by `alembic upgrade head`.

| File | Revision | What it does |
|---|---|---|
| `0003_v43_0_0_notification_claiming_and_payload.py` | `0003_v43_0_0` | "V43" notification-worker architecture: 22-column `notification_logs`, `platform_circuit_breakers`, `legacy_notification_provenance`, `smtp_evidence_store`, `eb_security` schema with 7 SECURITY DEFINER functions and 5 triggers, 7-role RBAC, KMS-signed provenance backfill |
| `0004_optional_enquiry_contact_number.py` | `0004_optional_enquiry_contact_number` | Makes `enquiries.contact_number` nullable **on top of 0003** (same change as active revision 0005) |
| `0006_merge_optional_contact_branches.py` | `0006_merge_contact_branches` | Merge point of the 0003/0004 line and 0005 |

## Why they were deferred (evidence)

1. **Not part of the active graph.** These revisions are stored outside `alembic/versions/`
   and the migration environment rejects databases stamped with their IDs. Do not infer a
   database's revision from this historical review; inspect only an explicitly approved,
   isolated target.
2. **Not used by the application.** No code in `app/` references any object 0003 creates; the `NotificationLog` model has the original 10 columns. Applying 0003 would make the database *diverge* from the models.
3. **Cannot run online.** It executes multi-statement SQL blocks through `op.execute()`. With the project's asyncpg driver this fails: `cannot insert multiple commands into a prepared statement` (reproduced on PostgreSQL 16).
4. **Needs infrastructure that does not exist.** Seven database roles pre-provisioned by a DBA (`eb_app_user`, `eb_worker_user`, `eb_migration_runner`, `eb_migration_role`, `eb_schema_owner`, `eb_sec_admin`, `eb_archival_role`) and an external KMS/Vault for HMAC provenance (deliberately fails closed without one).
5. **0004/0006 only existed to reconcile that branch.** 0005 provides the identical `contact_number` change directly from 0002.

## Authoritative path

The active Alembic graph is:

`0001_initial_schema → 0002_add_enquiry_idempotency → 0005_optional_contact_nullable → 0007_align_index_names_with_models → 0008_portal_accounts_orders_investments → 0009_account_security → 0010_registration_verification → 0011_consolidate_building_promotions → 0012_deactivate_shisha_and_axe_oil`

The current active head is `0012_deactivate_shisha_and_axe_oil`.

The migration chain from revision 0008 through 0012 has been
successfully executed and verified against a separate disposable
PostgreSQL 16 database.

The existing development database is expected to remain at
`0008_portal_accounts_orders_investments`. Staging and production
must use separately provisioned databases. Do not use this document
to run migrations against development or production.

`alembic/env.py` refuses to run against a database stamped with any
deferred revision, so a database cannot silently diverge.

## Reinstating the notification architecture later

If the deferred database-backed notification worker is built later (the existing transactional
invitation/reset email sender is separate):

1. Update `app/models/notification.py` to the intended schema (and the worker code that uses it).
2. Rewrite 0003's DDL as one statement per `op.execute()` (or run it through a sync driver), and decide the role model for the chosen provider (Supabase's `postgres` role is not a superuser).
3. Choose and integrate a KMS, or drop the legacy-provenance backfill (no legacy notification rows exist in production).
4. Add it as a **new revision on top of the current head** (new revision id, `down_revision` = current head). Do not re-insert these files with their old ids.
5. Remove the corresponding ids from `DEFERRED_REVISIONS` in `alembic/env.py` only if no database could carry them.
