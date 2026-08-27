"""Tests for Gmail tools, including archive_email and delete_email's hard
Interrupt confirmation flow.
"""

import base64
from unittest.mock import Mock

from personal_assistant_agent.tools.auth import AuthenticationError
from personal_assistant_agent.tools.errors import ToolExecutionError
from personal_assistant_agent.tools.gmail import (
    archive_email,
    delete_email,
    get_email,
    list_recent_emails,
    send_email,
)


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
        assert "msg1" in result
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


class TestArchiveEmail:
    def test_archives_email_and_returns_confirmation(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=mock_service,
        )
        mock_service.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}

        result = archive_email("msg123")

        assert "msg123" in result
        assert "archived" in result.lower()
        mock_service.users.return_value.messages.return_value.modify.assert_called_once_with(
            userId="me", id="msg123", body={"removeLabelIds": ["INBOX"]}
        )

    def test_does_not_touch_trash_or_delete_apis(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=mock_service,
        )
        mock_service.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}

        archive_email("msg123")

        mock_service.users.return_value.messages.return_value.trash.assert_not_called()
        mock_service.users.return_value.messages.return_value.delete.assert_not_called()

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.gmail.google_api_call",
            side_effect=ToolExecutionError("archive_email failed: the requested item was not found (404)."),
        )

        result = archive_email("bad-id")

        assert result == "archive_email failed: the requested item was not found (404)."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = archive_email("msg123")

        assert result == "credentials.json is missing."


class TestDeleteEmail:
    """delete_email requires a synchronous human confirmation via
    tool_context.interrupt(...) before it touches the Gmail API at all."""

    def test_confirmed_deletion_trashes_the_email(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=mock_service,
        )
        mock_service.users.return_value.messages.return_value.trash.return_value.execute.return_value = {}

        tool_context = Mock()
        tool_context.interrupt.return_value = "y"

        result = delete_email(
            tool_context,
            message_id="msg123",
            subject="Some subject",
            sender="someone@example.com",
        )

        tool_context.interrupt.assert_called_once_with(
            "gmail-delete-approval",
            reason={
                "message_id": "msg123",
                "subject": "Some subject",
                "sender": "someone@example.com",
            },
        )
        mock_service.users.return_value.messages.return_value.trash.assert_called_once_with(
            userId="me", id="msg123"
        )
        assert "msg123" in result
        assert "Trash" in result

    def test_confirmed_deletion_accepts_yes_case_insensitively(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=mock_service,
        )
        mock_service.users.return_value.messages.return_value.trash.return_value.execute.return_value = {}

        tool_context = Mock()
        tool_context.interrupt.return_value = "YES"

        result = delete_email(tool_context, message_id="msg123")

        mock_service.users.return_value.messages.return_value.trash.assert_called_once()
        assert "Trash" in result

    def test_denied_deletion_does_not_call_gmail_api(self, mocker):
        get_service_mock = mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
        )

        tool_context = Mock()
        tool_context.interrupt.return_value = "n"

        result = delete_email(
            tool_context,
            message_id="msg123",
            subject="Some subject",
            sender="someone@example.com",
        )

        get_service_mock.assert_not_called()
        assert "msg123" in result
        assert "NOT performed" in result

    def test_denied_deletion_with_arbitrary_response_does_not_call_gmail_api(self, mocker):
        get_service_mock = mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
        )

        tool_context = Mock()
        tool_context.interrupt.return_value = "not really sure"

        result = delete_email(tool_context, message_id="msg123")

        get_service_mock.assert_not_called()
        assert "NOT performed" in result

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.gmail.google_api_call",
            side_effect=ToolExecutionError("delete_email failed: permission denied (403) - insufficient access."),
        )

        tool_context = Mock()
        tool_context.interrupt.return_value = "y"

        result = delete_email(tool_context, message_id="msg123")

        assert result == "delete_email failed: permission denied (403) - insufficient access."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.gmail.get_gmail_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        tool_context = Mock()
        tool_context.interrupt.return_value = "y"

        result = delete_email(tool_context, message_id="msg123")

        assert result == "credentials.json is missing."
