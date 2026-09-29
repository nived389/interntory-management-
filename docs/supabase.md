# Supabase deployment

Status: optional PostgreSQL/private Storage integration prepared. Live migration and PostgreSQL integration testing require a Supabase project and credentials. Local SQLite remains active until DATABASE_URL is configured. Do not cut over until cloud checks pass.

## Layout

- Existing Flask server keeps login, master/staff permission checks and approval transactions.
- PostgreSQL uses a separate `inventory` schema. Migration revokes public/anon/authenticated access and enables RLS with no browser policies. Do not add this schema to exposed Data API schemas. Database credentials remain on the server.
- Photos and saved reports use the private `inventory-private` Storage bucket. Flask authorizes reads before fetching a file; no public photo URLs are created.
- Local files in cloud mode are a cache. Sessions and password encryption use stable environment secrets copied from the existing keys.
- Four years is the requested history retention. Automatic deletion is disabled. An archival job must first preserve opening balances and needed current-item photos, exclude unresolved submissions, export a verified backup, and remove dependent records in order. Never delete old ledger rows directly: stock balances depend on them. Pending implementation: reviewed retention cleanup and restore tooling for cloud JSON backups.

## Setup and migration

1. Create a free Supabase project. Save its database password privately. Copy the Session pooler connection from Connect, not a guessed hostname.
2. Install `requirements-supabase.txt` in the Flask environment. Set the server variables shown in `deploy/supabase.env.example`. Use the existing session.key and password-vault.key values so existing accounts and encrypted credentials continue to work. Do not share keys in chat or expose them in JavaScript.
3. Dry-run `python scripts/migrate_supabase.py --data /path/to/data` to inspect counts without changing anything.
4. Pause local writes and keep a complete local backup. Run the same command with `--apply` against an empty target. This creates the private schema and bucket, preserves IDs, copies every row and photo/report, checks row counts, then commits. An existing schema causes refusal rather than overwrite. Failed uploads roll back database migration, but private orphan uploads may remain and will be reused on retry.
5. Start the app using `gunicorn --workers 1 --threads 1 --timeout 180 production:app` on an HTTPS Flask host. Supabase does not host this Python app. PythonAnywhere's free outbound restrictions make it unsuitable for this configuration; choose a host allowing PostgreSQL and HTTPS connections. Hosting selection remains pending.
6. Verify master/staff login, permissions, photos, count submission/return/approval, reports and restart persistence before switching staff to the new URL. Use one live database after cutover.

Master backup downloads in cloud mode contain `inventory-postgres.json` and all cloud photos/reports. They do not contain encryption keys. Keep keys backed up separately; the existing SQLite restore script does not restore this JSON format. Retain the pre-migration SQLite backup until a cloud restore test passes.

Free-plan limits: 500 MB database, 1 GB file storage, 5 GB egress plus cached allowance; inactivity can pause the project. Four-year retention reduces growth but cannot guarantee staying within quotas. Monitor storage usage, especially photos and exported reports.

References:
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/storage/uploads/standard-uploads
- https://supabase.com/pricing
