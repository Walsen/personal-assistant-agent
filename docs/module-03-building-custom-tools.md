# Module 3: Building Custom Tools

**Duration:** 60 minutes

---

## 3.1 Shared Auth Module (10 min)

Our tools share a common authentication layer in `tools/auth.py`:

```python
from tools.auth import get_gmail_service, get_calendar_service, get_docs_service
```

### Why centralize auth?
- **DRY** — One place to manage credentials
- **Single token** — All scopes in one `token.json`
- **Easy to swap** — Replace with service account for production

### The pattern

```python
def get_gmail_service():
    return build("gmail", "v1", credentials=get_credentials())
```

Each tool calls the appropriate service builder. The credentials are cached after first load.

---

## 3.2 Gmail Tools (20 min)

### `read_emails` — Search and read messages

**Google API methods used:**
- `users().messages().list()` — Get message IDs matching a query
- `users().messages().get()` — Get message metadata/content

**Key concepts:**
- Gmail query syntax (same as the search bar): `is:unread`, `from:someone@email.com`, `subject:keyword`
- Messages are returned as IDs first, then fetched individually
- `format="metadata"` + `metadataHeaders` avoids downloading full message bodies

```python
@tool
def read_emails(query: str = "is:unread", max_results: int = 5) -> str:
    """Read emails from Gmail inbox.
    
    Args:
        query: Gmail search query (same syntax as Gmail search bar).
        max_results: Maximum number of emails to return (1-20).
    """
    service = get_gmail_service()
    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    # ... fetch each message's metadata
```

### `send_email` — Send messages via Gmail

**Google API method:** `users().messages().send()`

**Key concepts:**
- Build a MIME message with Python's `email.mime.text.MIMEText`
- Base64url-encode the message bytes
- Send via the API

```python
@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via Gmail."""
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    sent = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
```

### 🔨 Hands-On

```bash
python -c "
from tools.gmail_tools import read_emails
print(read_emails._fn(query='is:unread', max_results=3))
"
```

Try different queries:
- `"from:notifications@github.com"`
- `"subject:meeting after:2026/08/01"`
- `"is:starred"`

---

## 3.3 Calendar Tools (15 min)

### `list_events` — View upcoming events

**Google API method:** `events().list()`

**Key concepts:**
- `timeMin` / `timeMax` for date range filtering
- `singleEvents=True` expands recurring events
- `orderBy="startTime"` for chronological order

```python
@tool
def list_events(days_ahead: int = 7, max_results: int = 10) -> str:
    """List upcoming calendar events."""
    now = datetime.utcnow().isoformat() + "Z"
    time_max = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"
    
    results = service.events().list(
        calendarId="primary", timeMin=now, timeMax=time_max,
        maxResults=max_results, singleEvents=True, orderBy="startTime"
    ).execute()
```

### `create_event` — Create new events

**Google API method:** `events().insert()`

**Key concepts:**
- ISO 8601 datetime format with timezone: `2026-08-20T10:00:00-04:00`
- Optional fields: description, location, attendees
- Attendees receive email invitations automatically

```python
@tool
def create_event(summary: str, start_time: str, end_time: str, ...) -> str:
    """Create a new Google Calendar event."""
    event_body = {
        "summary": summary,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
    }
    event = service.events().insert(calendarId="primary", body=event_body).execute()
```

### 🔨 Hands-On

```bash
python -c "
from tools.calendar_tools import list_events
print(list_events._fn(days_ahead=7, max_results=5))
"
```

---

## 3.4 Google Docs Tools (15 min)

### `create_document` — Create new docs

**Google API methods:**
- `documents().create()` — Create an empty doc with a title
- `documents().batchUpdate()` — Insert text content

```python
@tool
def create_document(title: str, body_text: str = "") -> str:
    """Create a new Google Doc."""
    doc = service.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]
    
    if body_text:
        service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": body_text}}]}
        ).execute()
```

### `get_document` — Read document content

**Google API method:** `documents().get()`

**Key concept:** The document body is a tree of structural elements (paragraphs → elements → textRuns). We walk the tree to extract plain text.

### `update_document` — Append to existing docs

**Google API method:** `documents().batchUpdate()` with `insertText`

**Key concept:** You must specify the character index where text is inserted. We find the end of the document by reading the last element's `endIndex`.

### 🔨 Hands-On

```bash
python -c "
from tools.docs_tools import create_document, get_document
result = create_document._fn(title='Workshop Test', body_text='Hello from the workshop!')
print(result)
"
```

---

## Tool Design Best Practices

1. **Clear docstrings** — The model uses them to decide WHEN to call your tool
2. **Type hints** — They become the parameter schema (str, int, bool, etc.)
3. **Return strings** — The model reads the return value; make it human-readable
4. **Handle errors gracefully** — Return error messages, don't crash
5. **Limit scope** — Each tool does ONE thing well

---

## Resources

- [Gmail API: List Messages](https://developers.google.com/workspace/gmail/api/guides/list-messages)
- [Calendar API: Create Events](https://developers.google.com/workspace/calendar/api/guides/create-events)
- [Docs API: batchUpdate](https://developers.google.com/docs/api/reference/rest/v1/documents/batchUpdate)
- [Strands: Creating Custom Tools](https://strandsagents.com/docs/user-guide/concepts/tools/custom-tools/)
