# Module 2: Google Cloud & OAuth2 Setup

**Duration:** 30 minutes

---

## 2.1 Google Cloud Console Setup (15 min)

### Step 1: Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Click **Select Project** → **New Project**
3. Name: `personal-assistant-workshop`
4. Click **Create**

### Step 2: Enable APIs

Enable these three APIs in the [API Library](https://console.cloud.google.com/apis/library):

1. **Gmail API** — [Enable](https://console.cloud.google.com/apis/enableflow;apiid=gmail.googleapis.com)
2. **Google Calendar API** — [Enable](https://console.cloud.google.com/apis/enableflow;apiid=calendar-json.googleapis.com)
3. **Google Docs API** — [Enable](https://console.cloud.google.com/apis/enableflow;apiid=docs.googleapis.com)

### Step 3: Configure OAuth Consent Screen

1. Go to **Google Auth Platform** → **Branding**
2. App name: `Personal Assistant Workshop`
3. User support email: your email
4. Click **Save**
5. Go to **Audience** → Select **External**
6. Add your email as a test user

### Step 4: Create OAuth 2.0 Client ID

1. Go to **Google Auth Platform** → **Clients**
2. Click **Create Client**
3. Application type: **Desktop app**
4. Name: `Workshop Desktop Client`
5. Click **Create**
6. **Download the JSON** → save as `credentials.json` in your project root

---

## 2.2 Understanding the Auth Flow (15 min)

### How OAuth2 Desktop Flow Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Your Script │────→│ Google Auth  │────→│ User's Browser  │
│             │     │ Server       │     │ (consent screen)│
└─────────────┘     └──────────────┘     └─────────────────┘
       │                                          │
       │              ┌──────────────┐            │
       │←─────────────│ Access Token │←───────────┘
       │              └──────────────┘      (user clicks Allow)
       │
       ▼
 Saves token.json
 (for future runs)
```

### Scopes We Request

| Scope | What it allows |
|-------|----------------|
| `gmail.modify` | Read and modify emails (not delete) |
| `gmail.send` | Send emails on behalf of the user |
| `calendar` | Full read/write access to all calendars |
| `documents` | Full read/write access to Google Docs |

### Token Lifecycle

1. **First run:** Opens browser → user consents → saves `token.json`
2. **Subsequent runs:** Loads `token.json`, refreshes if expired
3. **Scope change:** Delete `token.json`, re-authenticate

### Required Packages

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### The Auth Code Pattern

```python
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
]

def get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds
```

### Building Service Objects

```python
creds = get_credentials()
gmail_service = build("gmail", "v1", credentials=creds)
calendar_service = build("calendar", "v3", credentials=creds)
docs_service = build("docs", "v1", credentials=creds)
```

---

## 🔨 Hands-On Exercise

1. Place your `credentials.json` in the project root
2. Run the auth helper:
   ```bash
   python -c "from tools.auth import get_credentials; get_credentials()"
   ```
3. Complete the browser consent flow
4. Verify `token.json` was created

---

## ⚠️ Security Notes

- **NEVER commit** `credentials.json` or `token.json` to git
- Both are in `.gitignore` already
- For production: use Google Cloud service accounts or Secrets Manager
- The OAuth consent screen in "Testing" mode limits to 100 test users

---

## API Scopes Reference

| API | Scope | Access Level |
|-----|-------|--------------|
| Gmail | `gmail.readonly` | Read messages/labels |
| Gmail | `gmail.modify` | Read + write (no delete) |
| Gmail | `gmail.send` | Send only |
| Gmail | `gmail.compose` | Create/modify drafts + send |
| Calendar | `calendar` | Full CRUD on all calendars |
| Calendar | `calendar.events` | CRUD events only |
| Calendar | `calendar.readonly` | Read-only |
| Docs | `documents` | Full CRUD |
| Docs | `documents.readonly` | Read-only |

---

## Resources

- [Gmail API Python Quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
- [Calendar API Python Quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python)
- [OAuth 2.0 Scopes for Google APIs](https://developers.google.com/identity/protocols/oauth2/scopes)
- [google-api-python-client docs](https://github.com/googleapis/google-api-python-client/blob/main/docs/auth.md)
