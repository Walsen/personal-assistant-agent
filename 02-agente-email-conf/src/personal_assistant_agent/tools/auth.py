"""Shared OAuth2 credential helper for Google Workspace APIs."""

import logging
import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
]


class AuthenticationError(Exception):
    """Raised when Google OAuth credentials cannot be obtained or refreshed."""


def get_credentials() -> Credentials:
    """Get or refresh OAuth2 credentials.

    On first run, opens a browser for user consent and saves the token.
    On subsequent runs, loads and refreshes the saved token.

    Raises:
        AuthenticationError: If credentials.json is missing, or if a stored
            token exists but can't be refreshed (e.g. it was revoked, or its
            granted scopes no longer match SCOPES).
    """
    creds = None
    if os.path.exists("token.json"):
        try:
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        except ValueError as e:
            logger.warning("token.json exists but could not be parsed: %s", e)
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Google OAuth token refreshed successfully")
            except RefreshError as e:
                logger.error("Failed to refresh Google OAuth token: %s", e)
                raise AuthenticationError(
                    "Google authentication has expired and could not be refreshed "
                    "(the token may have been revoked, or its scopes changed). "
                    "Delete token.json and re-run the OAuth flow to re-authenticate."
                ) from e
        else:
            if not os.path.exists("credentials.json"):
                raise AuthenticationError(
                    "credentials.json is missing. Download the OAuth client credentials "
                    "from Google Cloud Console and place them at credentials.json in the "
                    "project root before running the agent."
                )
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("Completed new Google OAuth consent flow")

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