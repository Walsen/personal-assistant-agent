"""Tests for tools/calendar.py."""

from unittest.mock import Mock

from googleapiclient.errors import HttpError

from personal_assistant_agent.tools.auth import AuthenticationError
from personal_assistant_agent.tools.calendar import create_event, list_upcoming_events


def _make_http_error(status: int, reason: str = "error") -> HttpError:
    class _FakeResp:
        def __init__(self, status: int, reason: str) -> None:
            self.status = status
            self.reason = reason

    return HttpError(resp=_FakeResp(status, reason), content=b"{}", uri="https://example.invalid/api")


class TestListUpcomingEvents:
    def test_returns_formatted_list_of_events(self, mocker):
        mock_service = Mock()
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "evt1",
                    "summary": "Team sync",
                    "start": {"dateTime": "2026-08-24T15:00:00-05:00"},
                },
                {
                    "id": "evt2",
                    "summary": "All-day offsite",
                    "start": {"date": "2026-08-25"},
                },
            ]
        }
        mocker.patch("personal_assistant_agent.tools.calendar.get_calendar_service", return_value=mock_service)

        result = list_upcoming_events(max_results=2)

        assert "Team sync" in result
        assert "2026-08-24T15:00:00-05:00" in result
        assert "evt1" in result
        assert "All-day offsite" in result
        assert "2026-08-25" in result
        assert "evt2" in result

    def test_returns_no_events_message_when_empty(self, mocker):
        mock_service = Mock()
        mock_service.events.return_value.list.return_value.execute.return_value = {"items": []}
        mocker.patch("personal_assistant_agent.tools.calendar.get_calendar_service", return_value=mock_service)

        result = list_upcoming_events()

        assert result == "No upcoming events found."

    def test_returns_error_message_on_authentication_error(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.calendar.get_calendar_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = list_upcoming_events()

        assert result == "credentials.json is missing."

    def test_returns_error_message_on_http_error(self, mocker):
        mock_service = Mock()
        mock_service.events.return_value.list.return_value.execute.side_effect = _make_http_error(
            401, "Invalid Credentials"
        )
        mocker.patch("personal_assistant_agent.tools.calendar.get_calendar_service", return_value=mock_service)

        result = list_upcoming_events()

        assert "list_upcoming_events" in result
        assert "authentication expired" in result.lower()


class TestCreateEvent:
    def test_returns_confirmation_with_event_id_and_link(self, mocker):
        mock_service = Mock()
        mock_service.events.return_value.insert.return_value.execute.return_value = {
            "id": "evt-new",
            "summary": "Planning session",
            "htmlLink": "https://calendar.google.com/event?eid=evt-new",
        }
        mocker.patch("personal_assistant_agent.tools.calendar.get_calendar_service", return_value=mock_service)

        result = create_event(
            summary="Planning session",
            start_time="2026-08-24T15:00:00-05:00",
            end_time="2026-08-24T16:00:00-05:00",
        )

        assert "Planning session" in result
        assert "evt-new" in result
        assert "https://calendar.google.com/event?eid=evt-new" in result

    def test_returns_error_message_on_authentication_error(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.calendar.get_calendar_service",
            side_effect=AuthenticationError("auth failed"),
        )

        result = create_event(
            summary="Planning session",
            start_time="2026-08-24T15:00:00-05:00",
            end_time="2026-08-24T16:00:00-05:00",
        )

        assert result == "auth failed"

    def test_returns_error_message_on_http_error(self, mocker):
        mock_service = Mock()
        mock_service.events.return_value.insert.return_value.execute.side_effect = _make_http_error(
            403, "Insufficient Permission"
        )
        mocker.patch("personal_assistant_agent.tools.calendar.get_calendar_service", return_value=mock_service)

        result = create_event(
            summary="Planning session",
            start_time="2026-08-24T15:00:00-05:00",
            end_time="2026-08-24T16:00:00-05:00",
        )

        assert "create_event" in result
        assert "permission denied" in result.lower()
