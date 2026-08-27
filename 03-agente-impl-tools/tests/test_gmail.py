"""Tests for tools/gmail.py."""

import base64
from unittest.mock import Mock

from googleapiclient.errors import HttpError

from personal_assistant_agent.tools.auth import AuthenticationError
from personal_assistant_agent.tools.gmail import get_email, list_recent_emails, send_email


def _make_http_error(status: int, reason: str = "error") -> HttpError:
    class _FakeResp:
        def __init__(self, status: int, reason: str) -> None:
            self.status = status
            self.reason = reason

    return HttpError(resp=_FakeResp(status, reason), content=b"{}", uri="https://example.invalid/api")


class TestListRecentEmails:
    def test_returns_formatted_list_of_emails(self, mocker):
        mock_service = Mock()
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}]
        }

        def fake_get(userId, id, format, metadataHeaders):  # noqa: A002
            headers = {
                "msg1": [{"name": "From", "value": "alice@example.com"}, {"name": "Subject", "value": "Hello"}],
                "msg2": [{"name": "From", "value": "bob@example.com"}, {"name": "Subject", "value": "Meeting"}],
            }[id]
            snippet = {"msg1": "Hi there", "msg2": "Let's meet"}[id]
            return Mock(execute=Mock(return_value={"payload": {"headers": headers}, "snippet": snippet}))

        mock_service.users.return_value.messages.return_value.get.side_effect = fake_get
        mocker.patch("personal_assistant_agent.tools.gmail.get_gmail_service", return_value=mock_service)

        result = list_recent_emails(max_results=2, query="is:unread")

        assert "alice@example.com" in result
        assert "Hello" in result
        assert "Hi there" in result
        assert "bob@example.com" in result
        assert "Meeting" in result
        assert "msg1" in result
        assert "msg2" in result

    def test_returns_no_emails_message_when_empty(self, mocker):
        mock_service = Mock()
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }
        mocker.patch("personal_assistant_agent.tools.gmail.get_gmail_service", return_value=mock_service)

        result = list_recent_emails()

        assert result == "No emails found."

    def test_returns_error_message_on_authentication_error(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = list_recent_emails()

        assert result == "credentials.json is missing."

    def test_returns_error_message_on_http_error(self, mocker):
        mock_service = Mock()
        mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = (
            _make_http_error(429, "Too Many Requests")
        )
        mocker.patch("personal_assistant_agent.tools.gmail.get_gmail_service", return_value=mock_service)

        result = list_recent_emails()

        assert "list_recent_emails" in result
        assert "rate limited" in result.lower()


class TestGetEmail:
    def test_returns_formatted_email_with_plain_text_body(self, mocker):
        mock_service = Mock()
        body_text = "Hello, this is the body."
        encoded = base64.urlsafe_b64encode(body_text.encode("utf-8")).decode("utf-8")
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@example.com"},
                    {"name": "Subject", "value": "Hello"},
                ],
                "mimeType": "text/plain",
                "body": {"data": encoded},
            }
        }
        mocker.patch("personal_assistant_agent.tools.gmail.get_gmail_service", return_value=mock_service)

        result = get_email("msg1")

        assert "From: alice@example.com" in result
        assert "Subject: Hello" in result
        assert body_text in result

    def test_returns_error_message_on_authentication_error(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            side_effect=AuthenticationError("token expired"),
        )

        result = get_email("msg1")

        assert result == "token expired"

    def test_returns_error_message_on_http_error(self, mocker):
        mock_service = Mock()
        mock_service.users.return_value.messages.return_value.get.return_value.execute.side_effect = (
            _make_http_error(404, "Not Found")
        )
        mocker.patch("personal_assistant_agent.tools.gmail.get_gmail_service", return_value=mock_service)

        result = get_email("does-not-exist")

        assert "get_email" in result
        assert "not found" in result.lower()


class TestSendEmail:
    def test_returns_confirmation_with_message_id(self, mocker):
        mock_service = Mock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "sent-123"
        }
        mocker.patch("personal_assistant_agent.tools.gmail.get_gmail_service", return_value=mock_service)

        result = send_email(to="bob@example.com", subject="Hi", body="Just saying hello.")

        assert "bob@example.com" in result
        assert "sent-123" in result

    def test_returns_error_message_on_authentication_error(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            side_effect=AuthenticationError("auth failed"),
        )

        result = send_email(to="bob@example.com", subject="Hi", body="body")

        assert result == "auth failed"

    def test_returns_error_message_on_http_error(self, mocker):
        mock_service = Mock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.side_effect = (
            _make_http_error(403, "Insufficient Permission")
        )
        mocker.patch("personal_assistant_agent.tools.gmail.get_gmail_service", return_value=mock_service)

        result = send_email(to="bob@example.com", subject="Hi", body="body")

        assert "send_email" in result
        assert "permission denied" in result.lower()
