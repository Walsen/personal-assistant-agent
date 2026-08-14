"""Gmail tools for the personal assistant agent."""

import base64
from email.mime.text import MIMEText
from strands import tool
from tools.auth import get_gmail_service


@tool
def read_emails(query: str = "is:unread", max_results: int = 5) -> str:
    """Read emails from Gmail inbox.

    Args:
        query: Gmail search query (e.g., 'is:unread', 'from:boss@company.com',
               'subject:meeting'). Uses same syntax as Gmail search bar.
        max_results: Maximum number of emails to return (1-20).

    Returns:
        Formatted list of emails with subject, sender, date, and snippet.
    """
    service = get_gmail_service()
    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        return "No emails found matching the query."

    output = []
    for msg_ref in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_ref["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"]
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        output.append(
            f"- **{headers.get('Subject', 'No Subject')}**\n"
            f"  From: {headers.get('From', 'Unknown')}\n"
            f"  Date: {headers.get('Date', 'Unknown')}\n"
            f"  Snippet: {msg.get('snippet', '')[:100]}"
        )
    return "\n\n".join(output)


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body text (plain text).

    Returns:
        Confirmation message with the sent message ID.
    """
    service = get_gmail_service()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    sent = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    return f"Email sent successfully. Message ID: {sent['id']}"
