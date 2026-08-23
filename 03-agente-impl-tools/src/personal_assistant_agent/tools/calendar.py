"""Google Calendar tools for the personal assistant agent."""

from strands import tool

from .auth import get_calendar_service


@tool
def list_upcoming_events(max_results: int = 10) -> str:
    """List the user's upcoming Google Calendar events, starting from now.

    Args:
        max_results: Maximum number of events to return (default: 10).

    Returns:
        A formatted list of upcoming events with title, start time, and event ID.
    """
    from datetime import datetime, timezone

    service = get_calendar_service()
    now = datetime.now(timezone.utc).isoformat()
    response = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
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
    service = get_calendar_service()
    event_body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
    }
    created = service.events().insert(calendarId="primary", body=event_body).execute()
    return f"Event created: {created.get('summary')} (ID: {created['id']}). Link: {created.get('htmlLink')}"
