---
name: weekly-billing-summary
description: Use when the user asks for a weekly summary of billing/payment emails, how much they spent this week, or a list of recent charges. Searches Gmail for billing-related emails from the last 7 days and produces a spending summary.
allowed-tools:
  - list_recent_emails
  - get_email
---

# Weekly Billing Summary

## Goal

Produce a concise weekly report of billing/payment emails received in the
last 7 days, including a list of individual charges and a total spend
estimate.

## Steps

1. Call `list_recent_emails` with a Gmail search query that targets billing
   content from the last 7 days, for example:
   `newer_than:7d (invoice OR receipt OR payment OR "your bill" OR statement OR charged OR subscription OR renewal)`
   Use `max_results` of at least 25 to avoid missing emails.

2. From the returned list, identify which emails are actually billing-related
   (bank/card notifications, subscription renewals, payment receipts,
   invoices). Ignore anything that is clearly not billing (e.g. newsletters
   that happen to mention "payment" in passing).

3. For emails where the amount isn't clear from the subject/snippet alone,
   call `get_email` on that message ID to read the full body and extract the
   exact amount charged.

4. Build a table with columns: Date (if available), Merchant/Sender,
   Description, Amount.

5. Sum all amounts found. If amounts are in different currencies, list
   subtotals per currency rather than mixing them into a single sum.

6. Present the final summary as:
   - A markdown table of individual charges
   - A **Total spent this week** line (per currency if mixed)
   - A short note on any emails that looked billing-related but where the
     amount could not be determined, so the user can check manually

## Notes

- Only look at emails from the last 7 days. If the user asks for a different
  time range (e.g. "this month"), adjust the `newer_than:` value accordingly
  (e.g. `newer_than:30d`).
- Do not take any action (no replying, no deleting) as part of this skill —
  it is read-only reporting.
