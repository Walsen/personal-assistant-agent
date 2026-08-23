"""Gmail tools for the personal assistant agent."""

import base64
from email.mime.text import MIMEText

from strands import tool

from .auth import get_gmail_service


@tool
def list_recent_emails(max_results: int = 10, query: str = "") -> str:
    """List recent Gmail messages, optionally filtered by a Gmail search query.

    Args:
        max_results: Maximum number of messages to return (default: 10).
        query: Optional Gmail search query (e.g. "is:unread", "from:someone@example.com").

    Returns:
        A formatted list of matching emails with sender, subject, and snippet.
    """
    service = get_gmail_service()
    response = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, q=query)
        .execute()
    )
    messages = response.get("messages", [])
    if not messages:
        return "No emails found."

    lines = []
    for msg_ref in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_ref["id"], format="metadata",
                 metadataHeaders=["From", "Subject"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        sender = headers.get("From", "(unknown sender)")
        subject = headers.get("Subject", "(no subject)")
        snippet = msg.get("snippet", "")
        lines.append(f"- From: {sender}\n  Subject: {subject}\n  Snippet: {snippet}\n  ID: {msg_ref['id']}")

    return "\n".join(lines)


@tool
def get_email(message_id: str) -> str:
    """Get the full content of a specific email by its message ID.

    Args:
        message_id: The Gmail message ID (as returned by list_recent_emails).

    Returns:
        The email's sender, subject, and body text.
    """
    service = get_gmail_service()
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    sender = headers.get("From", "(unknown sender)")
    subject = headers.get("Subject", "(no subject)")
    body = _extract_body(msg["payload"])
    return f"From: {sender}\nSubject: {subject}\n\n{body}"


def _extract_body(payload: dict) -> str:
    """Recursively extract plain text body from a Gmail message payload."""
    if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text

    return "(no readable text body)"


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain text body of the email.

    Returns:
        Confirmation message with the sent message ID.
    """
    service = get_gmail_service()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Email sent to {to}. Message ID: {sent['id']}"
