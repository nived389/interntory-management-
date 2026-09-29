# Free online hosting: PythonAnywhere

Status: configuration prepared locally. No account provisioned, company data uploaded, or live deployment verified.

## Fit and limits

The existing Flask application can use SQLite and photos in private persistent files on PythonAnywhere. The free plan provides one web app with one worker and 512 MiB total disk space. The web app has a one-month expiry: renew it from the hosting dashboard before expiry. Current business data is approximately 24 MB; Python dependencies, uploaded source, future photos, reports and backups also consume the quota. Check actual usage after installation. This is a small initial deployment, not unlimited storage or guaranteed availability.

Use the included PythonAnywhere subdomain and enable Force HTTPS. Keep database files and photos outside public static mappings. Free outbound networking is restricted; the current username/password login does not need an external identity service.

## Setup

1. Create a free account at https://www.pythonanywhere.com/ and sign in. Choose a username suitable for the public website address.
2. Upload application source to `/home/YOUR_USERNAME/travelicious`. Exclude `data`, `.git`, `.venv*`, `tmp`, caches, `.env*` and `google-auth.local.json`. Do not upload local virtual environments.
3. In a Bash console, create a Python 3.12 virtual environment (or a supported matching version), then install dependencies:

   ```sh
   mkvirtualenv --python=/usr/bin/python3.12 travelicious
   cd ~/travelicious
   pip install --no-cache-dir -r requirements.txt
   ```

4. Add a web app using Manual Configuration with the same Python version. Set its virtualenv to `/home/YOUR_USERNAME/.virtualenvs/travelicious`.
5. Replace the generated WSGI configuration contents with `deploy/pythonanywhere_wsgi.py`. It sets the private storage directory, secure cookies and India timezone before importing the app. Do not run `app.run()` or Gunicorn on this provider.
6. Enable Force HTTPS on the Web tab. Do not map the data directory as a static URL.
7. Migrate existing data as below, then reload the web app. `production.py` deliberately refuses to start without the existing database and session key.
8. Check disk quota after installing dependencies. Remove upload archives after successful verification, retaining an independent private local backup.

## Data migration and cutover

1. Arrange a brief write pause. Stop the local application before copying its database and files so the snapshot is consistent.
2. Keep a complete private local backup. Transfer `inventory.db`, `photos/`, `reports/`, `session.key`, and `password-vault.key` into `/home/YOUR_USERNAME/travelicious-data`. Preserve any required historical backups separately; never upload plaintext credential notes such as `staff2-login.txt`.
3. Restrict the private directory to the account user and key files to owner read/write. Keep secrets out of Git, source archives and public static paths.
4. Reload the web app. Verify existing master/staff login, item/photo totals, assigned sections, blind counts, approval/correction cycles, report downloads and mobile camera capture over HTTPS.
5. Use the online site as the single shared system after acceptance. Do not enter new records into a separate local copy.
6. Download regular application backups to private off-host storage. Back up the password-vault key separately: normal application backup downloads omit it. Test recovery. New free accounts do not include scheduled tasks, so do not assume automatic daily backups exist.

## Other hosting files

The Dockerfile and requirements-production.txt remain available for a future host supporting Docker and persistent disks. They are not used by PythonAnywhere. Render free storage is ephemeral and is unsuitable for this app's local database/photos. PostgreSQL plus object storage would require a separate code and data migration.

## Official references

- https://help.pythonanywhere.com/pages/FreeAccountsFeatures/
- https://help.pythonanywhere.com/pages/Flask/
- https://help.pythonanywhere.com/pages/DiskQuota/
- https://help.pythonanywhere.com/pages/HTTPSSetup/
