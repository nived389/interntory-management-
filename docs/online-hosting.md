# Online hosting preparation

Status: deployment files prepared locally. No cloud resources created and no company data uploaded.

## Recommended initial setup

Run this Flask app on a paid Render web service with a persistent disk, or an equivalent single-server Docker host. Keep SQLite, photos, saved reports and encryption keys together on that disk. Do not run multiple app instances or place the data directory on ephemeral storage. Start with one Gunicorn worker, as the current login-attempt counters are process-local.

- Build: the repository Dockerfile (Python 3.12).
- Persistent disk mount: `/var/lib/travelicious`.
- Environment: `INVENTORY_DATA=/var/lib/travelicious`, `HTTPS=1`, `TZ=Asia/Kolkata`, `PORT=10000`.
- HTTPS must terminate at the hosting service/reverse proxy. Never expose the development server.
- Repository/image includes application code only. `.dockerignore` excludes company data, private configuration and local keys.
- Before starting: restore the existing data folder into the persistent mount. The production entry point deliberately refuses to start without the existing database and session key.

## Migration order

1. Choose the provider and approve its actual plan/storage charges. Use a private source repository.
2. Provision persistent storage and an HTTPS web service. Keep initial access restricted while restoring.
3. Schedule a brief write pause on the local app. Stop the local app, then privately transfer the complete `data` directory to the mounted disk. Preserve `inventory.db`, `photos`, `reports`, `session.key`, and `password-vault.key` if present. Keep secrets out of Git and container images.
4. Start the production service. Verify master login, staff section access, existing photos and item counts, approval/correction cycles and PDF/Excel downloads. Test phone camera capture over HTTPS.
5. Make the cloud URL the single shared system. Do not keep entering data into a separate local database after cutover.
6. Configure regular SQLite-consistent backups plus photo/report backups to a separate private storage location. Keep the password-vault key backed up separately and test restoring it. A persistent disk alone is not an independent backup.

Existing downloadable application backups omit the password-vault key. They are not sufficient on their own to preserve password-reveal functionality when moving servers. A stopped, full-directory migration preserves it.

## Later scaling

A managed PostgreSQL database and private object storage can separate records and photos and support multiple app instances. This requires a deliberate SQLite-to-PostgreSQL code/data migration; changing a connection URL is not enough for the current app.

Provider references: https://render.com/docs/deploy-flask and https://render.com/docs/disks
