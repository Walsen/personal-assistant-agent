"""Tests for the Google OAuth credential helper in tools/auth.py.

All tests run against tmp_path (via monkeypatch.chdir) so no real
credentials.json/token.json in the project root are ever read or written,
and all Google API calls (Credentials, Request, InstalledAppFlow, build)
are mocked so no real network/browser interaction happens.
"""

from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import RefreshError

from personal_assistant_agent.tools.auth import (
    AuthenticationError,
    get_calendar_service,
    get_credentials,
    get_docs_service,
    get_gmail_service,
)


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    """Run every test with cwd set to an empty tmp_path.

    get_credentials() reads/writes "token.json" and "credentials.json"
    relative to the current working directory, so this fixture guarantees
    tests never touch the real project root.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestGetCredentialsMissingFiles:
    def test_raises_authentication_error_when_credentials_json_missing(self):
        """No token.json and no credentials.json -> AuthenticationError."""
        with pytest.raises(AuthenticationError, match="credentials.json is missing"):
            get_credentials()


class TestGetCredentialsFromValidToken:
    def test_loads_and_returns_existing_valid_token(self, tmp_path, mocker):
        """A valid token.json is loaded and returned without refresh or flow."""
        (tmp_path / "token.json").write_text("{}")

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_from_file = mocker.patch(
            "personal_assistant_agent.tools.auth.Credentials.from_authorized_user_file",
            return_value=mock_creds,
        )
        mock_flow = mocker.patch("personal_assistant_agent.tools.auth.InstalledAppFlow")

        result = get_credentials()

        assert result is mock_creds
        mock_from_file.assert_called_once()
        mock_flow.from_client_secrets_file.assert_not_called()


class TestGetCredentialsRefresh:
    def test_refreshes_expired_token_successfully(self, tmp_path, mocker):
        """An expired token with a refresh_token is refreshed in place."""
        (tmp_path / "token.json").write_text("{}")

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "some-refresh-token"
        mock_creds.to_json.return_value = "{\"refreshed\": true}"
        mocker.patch(
            "personal_assistant_agent.tools.auth.Credentials.from_authorized_user_file",
            return_value=mock_creds,
        )
        mock_request = mocker.patch("personal_assistant_agent.tools.auth.Request")

        result = get_credentials()

        assert result is mock_creds
        mock_creds.refresh.assert_called_once_with(mock_request.return_value)
        assert (tmp_path / "token.json").read_text() == "{\"refreshed\": true}"

    def test_raises_authentication_error_when_refresh_fails(self, tmp_path, mocker):
        """A RefreshError during refresh is wrapped in AuthenticationError."""
        (tmp_path / "token.json").write_text("{}")

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "some-refresh-token"
        mock_creds.refresh.side_effect = RefreshError("token revoked")
        mocker.patch(
            "personal_assistant_agent.tools.auth.Credentials.from_authorized_user_file",
            return_value=mock_creds,
        )
        mocker.patch("personal_assistant_agent.tools.auth.Request")

        with pytest.raises(AuthenticationError) as exc_info:
            get_credentials()

        assert isinstance(exc_info.value.__cause__, RefreshError)
        # token.json must not be overwritten with anything on failure.
        assert (tmp_path / "token.json").read_text() == "{}"


class TestGetCredentialsNewFlow:
    def test_runs_new_oauth_flow_when_no_token_and_credentials_present(self, tmp_path, mocker):
        """No token.json but credentials.json exists -> runs the consent flow."""
        (tmp_path / "credentials.json").write_text("{}")

        mock_creds = MagicMock()
        mock_creds.to_json.return_value = "{\"new\": true}"
        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server.return_value = mock_creds
        mock_flow = mocker.patch("personal_assistant_agent.tools.auth.InstalledAppFlow")
        mock_flow.from_client_secrets_file.return_value = mock_flow_instance

        result = get_credentials()

        assert result is mock_creds
        mock_flow.from_client_secrets_file.assert_called_once_with(
            "credentials.json", mocker.ANY
        )
        mock_flow_instance.run_local_server.assert_called_once_with(port=0)
        assert (tmp_path / "token.json").read_text() == "{\"new\": true}"


class TestServiceBuilders:
    def test_get_gmail_service_calls_build_with_gmail_v1(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.auth.get_credentials",
            return_value="fake-creds",
        )
        mock_build = mocker.patch("personal_assistant_agent.tools.auth.build")

        result = get_gmail_service()

        mock_build.assert_called_once_with("gmail", "v1", credentials="fake-creds")
        assert result is mock_build.return_value

    def test_get_calendar_service_calls_build_with_calendar_v3(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.auth.get_credentials",
            return_value="fake-creds",
        )
        mock_build = mocker.patch("personal_assistant_agent.tools.auth.build")

        result = get_calendar_service()

        mock_build.assert_called_once_with("calendar", "v3", credentials="fake-creds")
        assert result is mock_build.return_value

    def test_get_docs_service_calls_build_with_docs_v1(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.auth.get_credentials",
            return_value="fake-creds",
        )
        mock_build = mocker.patch("personal_assistant_agent.tools.auth.build")

        result = get_docs_service()

        mock_build.assert_called_once_with("docs", "v1", credentials="fake-creds")
        assert result is mock_build.return_value
