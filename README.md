# Cavern & Co. Inventory

A working inventory management application for **Travelicious** and **Travellers Cavern**, built with Flask, SQLite, and a mobile-responsive interface.

### 🌐 Live Public Demo Link
Access the live running instance from any device:
* **Public URL**: [https://trials-yarn-comment-commitments.trycloudflare.com](https://trials-yarn-comment-commitments.trycloudflare.com)
* **Master Login**: `traveliciousrestaurant@gmail.com` | Password: `Travelicious@2026!`
* **Staff Login**: `riya` | Password: `riya@123`

---

## Start Locally

Double-click **start.command**, or run with Python 3.11+ / OpenSSL:

```sh
python3 -m venv .venv-modern
.venv-modern/bin/pip install -r requirements.txt
.venv-modern/bin/python app.py
```

Open http://127.0.0.1:5055. Use the existing Master email/password or a staff username/password. The login screen has no public account creation and displays no account examples. The Master is **traveliciousrestaurant@gmail.com**; its password is the one supplied by the owner. Existing staff accounts are **riya** and **staff2**. The generated Staff 2 credentials are in the private, Git-ignored `data/staff2-login.txt` file.

Under **Team & access**, the Master can create Staff/Admin accounts, edit usernames, reset passwords, and select allowed modules and sections. Full-access Admins can manage admins, staff and all company sections/files. Startup never resets passwords, roles or permissions. Use Profile → Log out on desktop or mobile. See [Accounts and reporting](docs/accounts-and-breakage.md).

## Included

- Both properties and all six initial sections. Master can add, rename, order and archive sections.
- 61 Cafe and 123 Service names extracted from the PDF appendices, preserving labels. **No quantities, rates or source photos were invented.** Imported items show a photo-needed badge.
- Item catalogue, photos, specifications, units, categories, default INR rates, edits and archival.
- Purchases, one photo-first Report breakage flow, and reasoned Master adjustments. Existing damage records remain in history. Breakage requires a validated photo, item, quantity and typed reason; the date is locked to the server’s current day. Master receives a persistent in-app notification. Stock writes are serialized and atomic; duplicate breakage references do not deduct twice.
- Immutable ledger and event-time rates; money stored in integer paise.
- Master/Admin/Staff authorization on the server, with editable action permissions and section scope. Staff payloads omit balances, previous stock, expected stock, variance and rates unless explicitly granted financial visibility.
- Autosaved blind counts, local unsent drafts, submission, Master review, closing and reasoned reopening. Submitted periods block stock changes. Later finalized periods must be reopened before older periods.
- Versioned immutable snapshots. Closing actual becomes the following period's previous stock; intervening unclosed movements are carried forward.
- Monthly inventory, breakage/damage, purchases and yearly closed-snapshot reports. Property, combined and section filters. Photo-bearing Excel and PDF export. Core Excel columns preserve SI.NO / ITEM / PICTURE / PREV MONTH STOCK / NEW STOCK / DAMAGE / ACTUAL.
- Section inventory and breakage Excel/PDF files archived on every close, preserving previous revisions and checksums.
- Staff creation, disabling, password reset, immutable audit history, full database/photo/report backup download.
- Excel import preview for `Cafe report` and `SERVICE PRINT`, including conventional drawings and Excel rich-value image resolution. Explicit editable quantity/rate preview. Existing exact names match seeded items. No overwrite of existing stock history.
- Installable manifest, responsive layout, mobile camera file capture, 1600px WebP compression, 320px thumbnails, private authenticated photo access.

## Important operational behavior

- The live user database is `data/inventory.db`. Keep the entire `data` directory together. The session signing key is generated locally; it is not in source control.
- Public account setup is disabled. All accounts use email/username and password; authorized administrators create team accounts. Google OAuth is no longer required or registered.
- Entries use the server's local date. Set the server time zone to Asia/Kolkata when hosting.
- Unit quantities are whole numbers. Blank rates are unknown, distinct from zero. Reports exclude unknown values from financial totals and flag missing rates in incident rows and dashboard.
- Month-end closing must be deliberate: it establishes physical actual stock even when the variance is non-zero. Adjustments remain explicit ledger entries.
- Editing names and rates does not rewrite movement snapshots or closed count snapshots.
- Moving an item with ledger history is blocked to preserve attribution. Unused seeded items may be reassigned by editing their section. Historical transfers and bulk transfer tools are not implemented.
- Count drafts survive a temporary connection loss on the same device and account. Reopen the count online first; the app does not cache private count responses for fully offline browsing. Draft conflicts with a submitted/closed period remain pending and must be resolved by the Master.
- Photos use authenticated local file storage. They are retained without automatic deletion, as are ledger, snapshots and audit records. This is a retention mechanism, not a six-year availability guarantee.

## Backup and restore

Download a complete ZIP under Settings, or run:

```sh
.venv-modern/bin/python scripts/backup.py --data data --destination /absolute/path/to/backups
```

Schedule this command nightly on the production host; keep at least 30 daily copies and monthly copies in an independent backup location. To restore, stop the server, preserve the current data directory, then extract a trusted backup into a new data directory and start with `INVENTORY_DATA=/absolute/path/to/restored-data`. A new signing key will log everyone out. Test a restored copy periodically. Backups contain company records and password hashes and should remain private.

## Validation

```sh
.venv-modern/bin/python -m pytest -q
node --check static/app.js
```

Tests use a temporary database, not live data. They cover role restrictions, blind API payloads, photo requirement, over-deduction rejection, idempotency, rate snapshots, immutable ledger, count completeness, close/reopen, rollover, archived files, exports, account disable, backups and workbook preview/commit. The current report/notification/mobile-logout browser test is `scripts/browser-breakage.cjs` and use the locally bundled Playwright runtime with a separate QA server/database.

## Remaining before production launch

This is a functional local build, **not yet a public production deployment**. The PDF's proposed Next.js/Supabase stack was replaced with a self-contained Flask/SQLite implementation for immediate use; no Supabase/Postgres RLS deployment is included. Server authorization enforces Staff privacy.

- Obtain the original workbook to validate its actual rich-image mapping and import real quantities/rates/photos. Only synthetic workbook import has been tested.
- Choose hosting, HTTPS/domain and a production WSGI server. Set `HTTPS=1` behind HTTPS to enable secure cookies. Do not expose Flask's development server publicly.
- Configure independent scheduled backups, monitoring, disaster recovery and storage capacity for six years.
- Test camera capture and installation on real iPhone/Android devices over HTTPS, plus real staff UAT. Desktop browser viewport testing does not establish physical camera support.
- Optional Master TOTP/2FA, email-based password recovery, custom reason/unit settings, paginated large inventory/event lists, and property-wide archived files generated automatically on closing the last section are not implemented. Property/combined exports are available on demand.
- Rate limiting is per process; use a shared rate limiter and managed auth if deploying multiple workers or moving to a distributed environment.

The detailed extracted PDF requirements are in `docs/requirements.txt` for traceability.
