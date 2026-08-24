"""Google Calendar tools for the personal assistant agent."""

import logging
from datetime import datetime, timezone

from strands import tool

from .auth import AuthenticationError, get_calendar_service
from .errors import ToolExecutionError, google_api_call

logger = logging.getLogger(__name__)


@tool
def list_upcoming_events(max_results: int = 10) -> str:
    """List the user's upcoming Google Calendar events, starting from now.

    Args:
        max_results: Maximum number of events to return (default: 10).

    Returns:
        A formatted list of upcoming events with title, start time, and event ID.
    """
    logger.info("list_upcoming_events called | max_results=%s", max_results)
    try:
        service = get_calendar_service()
        now = datetime.now(timezone.utc).isoformat()
        response = google_api_call(
            "list_upcoming_events",
            lambda: service.events()
            .list(calendarId="primary", timeMin=now, maxResults=max_results, singleEvents=True, orderBy="startTime")
            .execute(),
        )
        events = response.get("items", [])
        if not events:
            return "No upcoming events found."

        lines = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            summary = event.get("summary", "(no title)")
            lines.append(f"- {summary} at {start} (ID: {event['id']})")

        return "\n".join(lines)
    except (ToolExecutionError, AuthenticationError) as e:
        return str(e)


@tool
def create_event(summary: str, start_time: str, end_time: str, description: str = "") -> str:
    """Create a new Google Calendar event.

    Args:
        summary: Title of the event.
        start_time: Start time in ISO 8601 format (e.g. "2026-08-24T15:00:00-05:00").
        end_time: End time in ISO 8601 format (e.g. "2026-08-24T16:00:00-05:00").
        description: Optional description for the event.

    Returns:
        Confirmation message with the created event ID and link.
    """
    logger.info("create_event called | summary=%r start=%s end=%s", summary, start_time, end_time)
    try:
        service = get_calendar_service()
        event_body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
        }
        created = google_api_call(
            "create_event",
            lambda: service.events().insert(calendarId="primary", body=event_body).execute(),
        )
        logger.info("create_event succeeded | event_id=%s", created.get("id"))
        return f"Event created: {created.get('summary')} (ID: {created['id']}). Link: {created.get('htmlLink')}"
    except (ToolExecutionError, AuthenticationError) as e:
        return str(e)
