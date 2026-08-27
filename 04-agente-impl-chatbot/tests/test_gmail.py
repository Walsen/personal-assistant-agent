"""Tests for Gmail tools."""

import base64
from unittest.mock import Mock

from personal_assistant_agent.tools.auth import AuthenticationError
from personal_assistant_agent.tools.errors import ToolExecutionError
from personal_assistant_agent.tools.gmail import get_email, list_recent_emails, send_email


class TestListRecentEmails:
    def test_returns_formatted_list_of_emails(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=mock_service,
        )
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}]
        }
        mock_service.users.return_value.messages.return_value.get.return_value.execute.side_effect = [
            {
                "payload": {"headers": [{"name": "From", "value": "a@example.com"}, {"name": "Subject", "value": "Hi"}]},
                "snippet": "Hello there",
            },
            {
                "payload": {"headers": [{"name": "From", "value": "b@example.com"}, {"name": "Subject", "value": "Yo"}]},
                "snippet": "What's up",
            },
        ]

        result = list_recent_emails(max_results=2, query="is:unread")

        assert "a@example.com" in result
        assert "Hi" in result
        assert "Hello there" in result
        assert "msg1" in result
        assert "b@example.com" in result
        assert "msg2" in result
        mock_service.users.return_value.messages.return_value.list.assert_called_once_with(
            userId="me", maxResults=2, q="is:unread"
        )

    def test_returns_message_when_no_emails(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=mock_service,
        )
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }

        result = list_recent_emails()

        assert result == "No emails found."

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.gmail.google_api_call",
            side_effect=ToolExecutionError("list_recent_emails failed: Google API server error (500)."),
        )

        result = list_recent_emails()

        assert result == "list_recent_emails failed: Google API server error (500)."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = list_recent_emails()

        assert result == "credentials.json is missing."


class TestGetEmail:
    def test_returns_sender_subject_and_body(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=mock_service,
        )
        body_text = base64.urlsafe_b64encode(b"Body content here").decode("utf-8")
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Test subject"},
                ],
                "mimeType": "text/plain",
                "body": {"data": body_text},
            }
        }

        result = get_email("msg1")

        assert "sender@example.com" in result
        assert "Test subject" in result
        assert "Body content here" in result

    def test_extracts_body_from_multipart_message(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=mock_service,
        )
        body_text = base64.urlsafe_b64encode(b"Plain part body").decode("utf-8")
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "payload": {
                "headers": [{"name": "From", "value": "x@example.com"}, {"name": "Subject", "value": "S"}],
                "mimeType": "multipart/alternative",
                # _extract_body returns the first part that yields any
                # non-empty text (including its own "no readable text body"
                # fallback), so the text/plain part must come first here to
                # be picked up.
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": body_text}},
                    {"mimeType": "text/html", "body": {"data": "aHRtbA=="}},
                ],
            }
        }

        result = get_email("msg2")

        assert "Plain part body" in result

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.gmail.google_api_call",
            side_effect=ToolExecutionError("get_email failed: the requested item was not found (404)."),
        )

        result = get_email("bad-id")

        assert result == "get_email failed: the requested item was not found (404)."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            side_effect=AuthenticationError("Google authentication has expired and could not be refreshed."),
        )

        result = get_email("msg1")

        assert result == "Google authentication has expired and could not be refreshed."


class TestSendEmail:
    def test_sends_email_and_returns_confirmation(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=mock_service,
        )
        mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {
            "id": "sent123"
        }

        result = send_email(to="dest@example.com", subject="Subject line", body="Body text")

        assert "dest@example.com" in result
        assert "sent123" in result
        mock_service.users.return_value.messages.return_value.send.assert_called_once()
        _, kwargs = mock_service.users.return_value.messages.return_value.send.call_args
        assert kwargs["userId"] == "me"
        assert "raw" in kwargs["body"]

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.gmail.google_api_call",
            side_effect=ToolExecutionError("send_email failed: permission denied (403) - insufficient access."),
        )

        result = send_email(to="dest@example.com", subject="S", body="B")

        assert result == "send_email failed: permission denied (403) - insufficient access."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = send_email(to="dest@example.com", subject="S", body="B")

        assert result == "credentials.json is missing."
