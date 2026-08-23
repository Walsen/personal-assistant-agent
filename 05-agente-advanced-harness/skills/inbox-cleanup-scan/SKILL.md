---
name: inbox-cleanup-scan
description: Use when the user wants to find promotional, marketing, or advertising emails cluttering their inbox that could be archived, deleted, or unsubscribed from. Produces a review list, and only archives/deletes emails after the user explicitly confirms.
allowed-tools:
  - list_recent_emails
  - get_email
  - archive_email
  - delete_email
---

# Inbox Cleanup Scan (Promotional / Advertising Emails)

## Goal

Find promotional/marketing emails in the inbox and present them to the user
as candidates for cleanup. Discovery is read-only; taking action (archiving
or deleting) always requires the user to explicitly approve which emails to
act on.

## Steps

1. Call `list_recent_emails` with a Gmail search query aimed at promotional
   content, for example:
   `category:promotions OR unsubscribe OR newsletter OR "% off" OR sale OR deal`
   Use a generous `max_results` (25-50) since the goal is a cleanup candidate
   list, not just the most recent handful.

2. From the results, classify each email as likely-promotional based on
   sender domain, subject line, and snippet (e.g. marketing/no-reply
   addresses, sale/discount language, newsletter senders). Exclude anything
   that looks like a real transactional or personal email even if it
   contains words like "% off" incidentally.

3. Group the candidates by sender when there are multiple emails from the
   same sender, so the user can see which senders are the biggest clutter
   sources.

4. Present a list with: Sender, Subject, Date/received time (if available),
   and Message ID. Order by sender (grouped), most frequent senders first.
   Do not archive or delete anything yet at this point.

5. Ask the user what they'd like to do with the candidates: leave them,
   archive them (reversible — removes from inbox, keeps the email), delete
   them (moves to Trash, permanently erased after ~30 days), or unsubscribe
   manually (this assistant cannot click unsubscribe links itself — point
   the user to the link in the email).

6. Only after the user identifies which specific emails/senders to act on:
   - Use `archive_email` for routine cleanup. It is reversible and needs no
     further confirmation beyond the user's selection in step 5.
   - Use `delete_email` only if the user specifically asked to delete rather
     than archive. It will independently prompt the user for a final
     yes/no confirmation before anything is removed — do not skip calling it
     even if the user already said "delete" once in step 5.
   - Never guess which emails to remove; only act on the ones the user
     explicitly selected from the presented list.

## Notes

- Never archive or delete an email that wasn't shown to and approved by the
  user in this conversation.
- Treat the classification as advisory — always show the list and let the
  user decide, since misclassifying a real email as promotional and removing
  it would be a mistake that (for delete) can't be undone after ~30 days.
