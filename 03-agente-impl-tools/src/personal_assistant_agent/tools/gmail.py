"""Gmail tools for the personal assistant agent."""

import base64
import logging
from email.mime.text import MIMEText

from strands import tool

from .auth import AuthenticationError, get_gmail_service
from .errors import ToolExecutionError, google_api_call

logger = logging.getLogger(__name__)


@tool
def list_recent_emails(max_results: int = 10, query: str = "") -> str:
    """List recent Gmail messages, optionally filtered by a Gmail search query.

    Args:
        max_results: Maximum number of messages to return (default: 10).
        query: Optional Gmail search query (e.g. "is:unread", "from:someone@example.com").

    Returns:
        A formatted list of matching emails with sender, subject, and snippet.
    """
    logger.info("list_recent_emails called | max_results=%s query=%r", max_results, query)
    try:
        service = get_gmail_service()
        response = google_api_call(
            "list_recent_emails",
            lambda: service.users().messages().list(userId="me", maxResults=max_results, q=query).execute(),
        )
        messages = response.get("messages", [])
        if not messages:
            return "No emails found."

        lines = []
        for msg_ref in messages:
            msg = google_api_call(
                "list_recent_emails",
                lambda ref=msg_ref: service.users()
                .messages()
                .get(userId="me", id=ref["id"], format="metadata", metadataHeaders=["From", "Subject"])
                .execute(),
            )
            headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
            sender = headers.get("From", "(unknown sender)")
            subject = headers.get("Subject", "(no subject)")
            snippet = msg.get("snippet", "")
            lines.append(f"- From: {sender}\n  Subject: {subject}\n  Snippet: {snippet}\n  ID: {msg_ref['id']}")

        return "\n".join(lines)
    except (ToolExecutionError, AuthenticationError) as e:
        return str(e)


@tool
def get_email(message_id: str) -> str:
    """Get the full content of a specific email by its message ID.

    Args:
        message_id: The Gmail message ID (as returned by list_recent_emails).

    Returns:
        The email's sender, subject, and body text.
    """
    logger.info("get_email called | message_id=%s", message_id)
    try:
        service = get_gmail_service()
        msg = google_api_call(
            "get_email",
            lambda: service.users().messages().get(userId="me", id=message_id, format="full").execute(),
        )
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        sender = headers.get("From", "(unknown sender)")
        subject = headers.get("Subject", "(no subject)")
        body = _extract_body(msg["payload"])
        return f"From: {sender}\nSubject: {subject}\n\n{body}"
    except (ToolExecutionError, AuthenticationError) as e:
        return str(e)


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
    logger.info("send_email called | to=%s subject=%r", to, subject)
    try:
        service = get_gmail_service()
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        sent = google_api_call(
            "send_email",
            lambda: service.users().messages().send(userId="me", body={"raw": raw}).execute(),
        )
        logger.info("send_email succeeded | to=%s message_id=%s", to, sent["id"])
        return f"Email sent to {to}. Message ID: {sent['id']}"
    except (ToolExecutionError, AuthenticationError) as e:
        return str(e)
