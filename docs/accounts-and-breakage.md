# Accounts and breakage reporting

## Sign in and manage access

Use the blank **Email or Username** and **Password** fields. There is no sign-up option. The Master account and two staff accounts already exist in the current database. Accounts and password hashes persist in `data/inventory.db`; startup does not recreate accounts or undo changes.

Master can add staff, edit usernames, reset passwords and grant/revoke actions and sections under **Team & access**. Full-access Admins can manage both admins and staff. Restricted admins can delegate only their own permitted actions and sections. All access checks are enforced by the API as well as the interface.

Use **Profile → Log out** in the top bar on desktop or mobile. The desktop sidebar and Account settings also offer Log out.

## Report breakage

1. Open **Breakage → Report breakage**.
2. Choose **Take photo** (rear-camera capture on supported mobile browsers) or **Choose photo**. Review the preview and select **Use photo & continue**.
3. Select the section, then its item. Only permitted sections are listed.
4. Enter the broken quantity and type the reason.
5. Select **Send report**.

The date is read-only. The server assigns today's date on submission and rejects past/future report dates, including tampered API requests. This restriction remains in force even if staff have stock-adjustment permission. The server uses its local date, so hosting must use the Asia/Kolkata time zone.

Images are compressed and validated. The stock deduction, audit event and Master notification share a database transaction. If notification insertion fails, the stock movement is rolled back. Retries using the same submission reference do not duplicate stock deductions or alerts. Historic DAMAGE records remain available but there is no separate Report damage action.

## Master notifications

The Master profile shows a **Notifications** button with an unread badge. Notifications persist while Master is logged out. An open visible app refreshes the badge every 30 seconds and when the window regains focus. Opening notifications also refreshes it.

Each alert includes the item, quantity, section/property, staff name, date, typed reason and report reference. **View report** marks it read and opens/highlights the matching report; the report includes the recorded photo. **Mark read** clears the unread badge without deleting the record. Other staff cannot read or mark the Master's notifications.

These are in-app notifications, not email, SMS or operating-system push messages. Physical camera capture still needs a real-phone test; automated browser validation uses image uploads through the capture input.
