"""Shared OAuth2 credential helper for Google Workspace APIs.

Local CLI usage and AgentCore Runtime deployment need different token
storage: locally, token.json on disk is fine and lets the interactive
browser consent flow write it directly. In AgentCore Runtime, the container
filesystem is ephemeral (a fresh container can be started at any time) and
there is no browser to complete an interactive consent flow, so the token
must come from a durable, pre-provisioned secret instead.

Set GOOGLE_TOKEN_SECRET_ID (an AWS Secrets Manager secret ARN or name) to
switch to that mode. The secret must contain the OAuth token JSON produced
by a one-time local `get_credentials()` run (see the README for the
provisioning steps) - this module reads and refreshes it, but never runs
the interactive browser flow when a secret store is configured, since a
container has no way to complete that flow.
"""

import json
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
    "https://www.googleapis.com/auth/drive.readonly",
]

# When set, tokens are read from/written to this AWS Secrets Manager secret
# instead of the local token.json file. Set this in the AgentCore Runtime
# deployment; leave unset for local CLI development.
GOOGLE_TOKEN_SECRET_ID = os.environ.get("GOOGLE_TOKEN_SECRET_ID")


class AuthenticationError(Exception):
    """Raised when Google OAuth credentials cannot be obtained or refreshed."""


def _load_token_from_secrets_manager() -> str | None:
    import boto3

    client = boto3.client("secretsmanager")
    try:
        response = client.get_secret_value(SecretId=GOOGLE_TOKEN_SECRET_ID)
    except client.exceptions.ResourceNotFoundException:
        return None
    return response.get("SecretString")


def _save_token_to_secrets_manager(token_json: str) -> None:
    import boto3

    client = boto3.client("secretsmanager")
    try:
        client.put_secret_value(SecretId=GOOGLE_TOKEN_SECRET_ID, SecretString=token_json)
    except client.exceptions.ResourceNotFoundException as e:
        raise AuthenticationError(
            f"Secrets Manager secret {GOOGLE_TOKEN_SECRET_ID!r} does not exist. "
            "Provision it first with a valid Google OAuth token JSON (see README "
            "for the one-time local provisioning steps)."
        ) from e


def _load_stored_token() -> str | None:
    if GOOGLE_TOKEN_SECRET_ID:
        return _load_token_from_secrets_manager()
    if os.path.exists("token.json"):
        with open("token.json") as f:
            return f.read()
    return None


def _save_token(token_json: str) -> None:
    if GOOGLE_TOKEN_SECRET_ID:
        _save_token_to_secrets_manager(token_json)
    else:
        with open("token.json", "w") as f:
            f.write(token_json)


def get_credentials() -> Credentials:
    """Get or refresh OAuth2 credentials.

    Locally (GOOGLE_TOKEN_SECRET_ID unset): on first run, opens a browser
    for user consent and saves the token to token.json. On subsequent runs,
    loads and refreshes the saved token.

    Under AgentCore Runtime (GOOGLE_TOKEN_SECRET_ID set): loads the token
    from the configured Secrets Manager secret and refreshes it there. The
    interactive browser consent flow is never triggered in this mode - the
    secret must already contain a valid token (provisioned once locally
    before deployment; see README).

    Raises:
        AuthenticationError: If no credentials are available and the
            interactive flow can't run (Secrets Manager mode with no stored
            token, or credentials.json missing locally), or if a stored
            token exists but can't be refreshed (e.g. revoked, or its
            granted scopes no longer match SCOPES).
    """
    creds = None
    stored_token = _load_stored_token()
    if stored_token:
        try:
            creds = Credentials.from_authorized_user_info(json.loads(stored_token), SCOPES)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning("Stored token could not be parsed: %s", e)
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
                    "Re-provision a fresh token (locally, then upload to Secrets "
                    "Manager if deployed) to re-authenticate."
                ) from e
        elif GOOGLE_TOKEN_SECRET_ID:
            raise AuthenticationError(
                f"No valid Google OAuth token found in Secrets Manager secret "
                f"{GOOGLE_TOKEN_SECRET_ID!r}. This deployment cannot run the "
                "interactive browser consent flow - provision a valid token "
                "into the secret first (run the OAuth flow locally, then "
                "upload token.json's contents to the secret)."
            )
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

        _save_token(creds.to_json())

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


def get_drive_service():
    """Build and return the Google Drive API service client."""
    return build("drive", "v3", credentials=get_credentials())
