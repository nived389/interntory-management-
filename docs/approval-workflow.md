# Staff submissions and admin review

Staff purchases (including starting stock on new items), breakage and adjustments enter Reports & approvals as Pending. They are saved as submissions, not ledger movements. An admin with Review/close/reopen months permission and access to the section can accept or return them. Acceptance inserts a ledger transaction once, retaining the staff actor and recording the reviewer in the submission/audit. Existing ledger entries are unchanged. Admin-entered stock transactions remain immediate.

Return requires feedback. Only the original submitter can correct and resubmit; quantity, item within the original section, reason, note, purchase rate and replacement camera photo can be corrected. The original incident date is retained, preventing backdating. Each correction increments the revision; stale acceptance attempts fail. Reports & approvals displays usernames, user IDs, status and feedback, with an action-count badge refreshed every 30 seconds.

Monthly counts show previous accepted actual stock + approved purchases - approved breakage + adjustments, expected stock, actual count and the difference. Both shortages and excesses are visible to users with stock visibility. Draft quantities do not replace the accepted opening baseline. A count belongs to its submitter. Admins flag individual submitted items with feedback; the original submitter corrects flagged lines and resubmits the count. Accept & close month creates immutable snapshots and reports. Pending/returned stock reports must be resolved first. Submitted counts can still have their queued stock transactions reviewed; finalized periods must be reopened before such changes.

Section moves and item archiving are blocked while item submissions are unresolved. Existing closed snapshots and ledger history are preserved. Legacy counts may have no submitter identity because it was not previously stored; new submissions always record it.

## Member security update

Only the MASTER account with username traveliciousrestaurant@gmail.com can list/manage members, reset passwords, change access or reveal saved passwords. Other full admins retain operational access but cannot manage accounts. Staff and other admins request password changes from the owner. New or reset passwords require five characters; existing passwords continue working until changed.

Authentication retains PBKDF2 hashes. Passwords set after this update additionally have a Fernet-encrypted copy for the requested owner-only reveal function. The separate data/password-vault.key file is created with mode 0600 and is not included in downloadable backups; preserve it separately when migrating the server. Existing hash-only passwords cannot be revealed until reset. Reveal is POST-only with CSRF protection, no-store responses, owner authorization and an audit event that never includes password text.

## Staff mobile workspace and private correction lists

Staff now have a phone-width workspace with three ordered home actions: Report breakage, Monthly count, and Add new items / purchases. Navigation contains Home, Corrections and Log out; Profile stays available. Catalogue access, stock/rate visibility, reports, approvals, exports and backups are excluded from staff permissions at runtime, including legacy grants. Non-master admins retain their permitted operational catalogue access; only the owner can review submissions or download reports/backups. Form-only item lookup provides identifiers and names for authorized purchase, breakage and count tasks.

A staff new-item request remains a NEW_ITEM submission, including photo and details, with no catalogue or ledger row until accepted. Existing records are preserved. Master reviews submissions grouped by submitter, section, date and type. Marking doubtful entries and returning a list sends the entire group back; unmarked entries are read-only context. The author corrects marked entries, then explicitly resubmits the whole list. Group acceptance is transactional: all entries succeed together or none are recorded. Every revision and review action retains the original submitter ID and audit details.

Monthly counts can return multiple marked items in one action. The complete count stays with its original submitter; other staff cannot read it or modify it. The master and original author can access the returned file. Staff can revise marked quantities and notes until resubmission; acceptance alone creates the finalized snapshot.
