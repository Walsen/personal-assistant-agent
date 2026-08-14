# Module 5: Testing & Iterating

**Duration:** 20 minutes

---

## 5.1 Debugging Tool Errors (10 min)

### Common Issues and Solutions

| Error | Cause | Fix |
|-------|-------|-----|
| `HttpError 403: insufficient permissions` | Missing scope | Delete `token.json`, re-authenticate |
| `HttpError 401: invalid credentials` | Token expired | Delete `token.json`, re-authenticate |
| `FileNotFoundError: credentials.json` | Missing OAuth client file | Re-download from Google Cloud Console |
| `HttpError 429: rate limit exceeded` | Too many API calls | Add delays, reduce `max_results` |
| `RefreshError: token has been revoked` | User revoked access | Delete `token.json`, re-authenticate |

### Refreshing Tokens After Scope Changes

If you add new scopes to `SCOPES` in `auth.py`:

```bash
# Delete the old token
rm token.json

# Next run will re-trigger browser auth with new scopes
python agent.py
```

### Reading Google API Error Messages

```python
from googleapiclient.errors import HttpError

try:
    result = service.users().messages().list(userId="me").execute()
except HttpError as error:
    print(f"API Error {error.resp.status}: {error._get_reason()}")
```

### Debugging the Agent's Tool Selection

If the agent calls the wrong tool or passes bad parameters:
1. **Check the docstring** — Is the tool's purpose clear?
2. **Check parameter descriptions** — Are they specific enough?
3. **Check the system prompt** — Does it guide the agent properly?
4. **Add examples** — Put usage examples in the docstring

---

## 5.2 Improving the Agent (10 min)

### Adding Error Handling to Tools

Before (crashes on error):
```python
@tool
def read_emails(query: str = "is:unread", max_results: int = 5) -> str:
    service = get_gmail_service()
    results = service.users().messages().list(...).execute()
```

After (graceful error messages):
```python
@tool
def read_emails(query: str = "is:unread", max_results: int = 5) -> str:
    try:
        service = get_gmail_service()
        results = service.users().messages().list(...).execute()
    except HttpError as e:
        return f"Error reading emails: {e._get_reason()}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
```

The model can read error messages and adjust its approach!

### Improving Tool Descriptions

Weak description:
```python
@tool
def read_emails(query: str = "is:unread") -> str:
    """Read emails."""
```

Strong description:
```python
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
```

### Adding Confirmation Patterns

For tools with side effects (send email, create event), the system prompt should tell the agent to confirm first. But you can also enforce it in code:

```python
@tool
def send_email(to: str, subject: str, body: str, confirmed: bool = False) -> str:
    """Send an email via Gmail.
    
    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body text.
        confirmed: Must be True to actually send. Set False to preview.
    """
    if not confirmed:
        return f"Preview - To: {to}, Subject: {subject}\nBody: {body}\n\nCall again with confirmed=True to send."
    # ... actually send
```

---

## Discussion: What Else Could This Agent Do?

Ideas for additional tools:
- 📎 **Attach files** to emails (Gmail attachments API)
- 🔍 **Search Docs** across all your documents (Drive API)
- 📊 **Read Sheets** for data analysis
- 🗑️ **Delete/archive** emails (with extra confirmation)
- 🔔 **Set reminders** via Calendar
- 👥 **Manage contacts** (People API)
- 📝 **Create templates** for common emails/docs

---

## Resources

- [Gmail API Error Handling](https://developers.google.com/workspace/gmail/api/guides/handle-errors)
- [Strands: Responsible AI](https://strandsagents.com/docs/user-guide/safety-security/responsible-ai/)
- [Strands: Guardrails](https://strandsagents.com/docs/user-guide/safety-security/guardrails/)
