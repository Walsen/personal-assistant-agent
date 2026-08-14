"""Shared OAuth2 credential helper for Google Workspace APIs."""

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


def get_credentials() -> Credentials:
    """Get or refresh OAuth2 credentials.

    On first run, opens a browser for user consent and saves the token.
    On subsequent runs, loads and refreshes the saved token.
    """
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


def get_gmail_service():
    """Build and return the Gmail API service client."""
    return build("gmail", "v1", credentials=get_credentials())


def get_calendar_service():
    """Build and return the Google Calendar API service client."""
    return build("calendar", "v3", credentials=get_credentials())


def get_docs_service():
    """Build and return the Google Docs API service client."""
    return build("docs", "v1", credentials=get_credentials())
