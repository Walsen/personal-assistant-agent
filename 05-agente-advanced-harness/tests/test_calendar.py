"""Tests for Google Calendar tools."""

from unittest.mock import Mock

from personal_assistant_agent.tools.auth import AuthenticationError
from personal_assistant_agent.tools.calendar import create_event, list_upcoming_events
from personal_assistant_agent.tools.errors import ToolExecutionError


class TestListUpcomingEvents:
    def test_returns_formatted_list_of_events(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.calendar.get_calendar_service",
            return_value=mock_service,
        )
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "evt1",
                    "summary": "Team sync",
                    "start": {"dateTime": "2026-01-01T10:00:00Z"},
                },
                {
                    "id": "evt2",
                    "summary": "(no title)",
                    "start": {"date": "2026-01-02"},
                },
            ]
        }

        result = list_upcoming_events(max_results=5)

        assert "Team sync" in result
        assert "evt1" in result
        assert "2026-01-01T10:00:00Z" in result
        assert "evt2" in result
        assert "2026-01-02" in result
        mock_service.events.return_value.list.assert_called_once_with(
            calendarId="primary",
            timeMin=mocker.ANY,
            maxResults=5,
            singleEvents=True,
            orderBy="startTime",
        )

    def test_returns_message_when_no_events(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.calendar.get_calendar_service",
            return_value=mock_service,
        )
        mock_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        result = list_upcoming_events()

        assert result == "No upcoming events found."

    def test_handles_missing_summary_with_default(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.calendar.get_calendar_service",
            return_value=mock_service,
        )
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "evt3", "start": {"dateTime": "2026-01-03T09:00:00Z"}}]
        }

        result = list_upcoming_events()

        assert "(no title)" in result
        assert "evt3" in result

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.calendar.get_calendar_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.calendar.google_api_call",
            side_effect=ToolExecutionError("list_upcoming_events failed: rate limited by the Google API (429)."),
        )

        result = list_upcoming_events()

        assert result == "list_upcoming_events failed: rate limited by the Google API (429)."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.calendar.get_calendar_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = list_upcoming_events()

        assert result == "credentials.json is missing."


class TestCreateEvent:
    def test_creates_event_and_returns_confirmation(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.calendar.get_calendar_service",
            return_value=mock_service,
        )
        mock_service.events.return_value.insert.return_value.execute.return_value = {
            "id": "evt123",
            "summary": "Planning",
            "htmlLink": "https://calendar.google.com/event?eid=evt123",
        }

        result = create_event(
            summary="Planning",
            start_time="2026-08-24T15:00:00-05:00",
            end_time="2026-08-24T16:00:00-05:00",
            description="Quarterly planning",
        )

        assert "Planning" in result
        assert "evt123" in result
        assert "https://calendar.google.com/event?eid=evt123" in result
        mock_service.events.return_value.insert.assert_called_once_with(
            calendarId="primary",
            body={
                "summary": "Planning",
                "description": "Quarterly planning",
                "start": {"dateTime": "2026-08-24T15:00:00-05:00"},
                "end": {"dateTime": "2026-08-24T16:00:00-05:00"},
            },
        )

    def test_defaults_description_to_empty_string(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.calendar.get_calendar_service",
            return_value=mock_service,
        )
        mock_service.events.return_value.insert.return_value.execute.return_value = {
            "id": "evt456",
            "summary": "Quick call",
            "htmlLink": "https://calendar.google.com/event?eid=evt456",
        }

        create_event(
            summary="Quick call",
            start_time="2026-08-24T15:00:00-05:00",
            end_time="2026-08-24T15:30:00-05:00",
        )

        _, kwargs = mock_service.events.return_value.insert.call_args
        assert kwargs["body"]["description"] == ""

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.calendar.get_calendar_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.calendar.google_api_call",
            side_effect=ToolExecutionError("create_event failed: invalid request (400) - bad start time."),
        )

        result = create_event(
            summary="Broken event",
            start_time="not-a-date",
            end_time="also-not-a-date",
        )

        assert result == "create_event failed: invalid request (400) - bad start time."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.calendar.get_calendar_service",
            side_effect=AuthenticationError("Google authentication has expired and could not be refreshed."),
        )

        result = create_event(
            summary="Doesn't matter",
            start_time="2026-08-24T15:00:00-05:00",
            end_time="2026-08-24T16:00:00-05:00",
        )

        assert result == "Google authentication has expired and could not be refreshed."
