# Turso storage

Status: libSQL integration prepared locally. No Turso account/database is connected and no company data has been uploaded. Use a Turso **libSQL** database (libsql:// URL), not the newer Turso engine (turso://).

Existing SQLite SQL, IDs, permissions and immutable history triggers remain intact. The Flask backend uses the official libsql Python driver against the remote primary. Photos, thumbnails and report files are kept in private database BLOB chunks with size/SHA-256 checks, in the same transaction as their associated database changes. No Supabase account is needed. Database tokens never go to browser code.

## Account and migration

1. Sign in to https://app.turso.tech/ and select the free plan. Website hosting is separate; Turso hosts the data.
2. Install/authenticate the official Turso CLI when ready to migrate. Create a database from the prepared SQLite file using the libSQL engine.
3. Before final migration, pause local writes and retain a complete local backup, including session.key and password-vault.key. Build a fresh private snapshot:

   ```sh
   .venv-modern/bin/python scripts/prepare_turso.py --data data --output tmp/turso-final.db
   turso db create travelicious-inventory --from-file tmp/turso-final.db
   turso db show --url travelicious-inventory
   ```

   The snapshot includes all records, compressed photos and reports. It excludes plaintext credential notes and secret key files. Never commit or publicly share this file. The script refuses to overwrite an existing output.

4. Generate a database auth token privately using the dashboard or CLI. Configure the server using `deploy/turso.env.example`; preserve existing session and password-vault keys. Remove Supabase DATABASE_URL. Install `requirements-turso.txt` and start via `production:app` on an HTTPS Flask host.
5. Verify login, permissions, photos, report exports, staff submissions, correction loops, approval, backups and persistence after restart. Then make the cloud site the only live system. Keep the local backup until restore is verified.

## Backups and retention

The master backup endpoint produces a SQLite database and extracted photos/reports in a ZIP. Backup reads use one transaction, fail without returning a partial archive, and can hit remote transaction/time/size limits as data grows; verify on the actual cloud instance and use provider exports for larger databases. Keys need a separate private backup.

Requested maximum history: four years. Retention configuration is included but deletion remains disabled. Cleanup still needs opening-balance preservation and restore verification before it can be enabled. Current catalogue items/photos and unresolved corrections must remain available. No older records are deleted by migration.

Compressed file storage counts toward database usage. Monitor quota and read/write limits. The account's current plan is authoritative; four-year retention does not guarantee a fixed storage size.

References: https://docs.turso.tech/sdk/python/quickstart and https://docs.turso.tech/cli/db/create
