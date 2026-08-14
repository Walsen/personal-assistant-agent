"""Google Calendar tools for the personal assistant agent."""

from datetime import datetime, timedelta
from strands import tool
from tools.auth import get_calendar_service


@tool
def list_events(days_ahead: int = 7, max_results: int = 10) -> str:
    """List upcoming calendar events.

    Args:
        days_ahead: Number of days to look ahead (1-30).
        max_results: Maximum number of events to return (1-50).

    Returns:
        Formatted list of upcoming events with time, title, and location.
    """
    service = get_calendar_service()
    now = datetime.utcnow().isoformat() + "Z"
    time_max = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"

    results = service.events().list(
        calendarId="primary", timeMin=now, timeMax=time_max,
        maxResults=max_results, singleEvents=True, orderBy="startTime"
    ).execute()

    events = results.get("items", [])
    if not events:
        return "No upcoming events found."

    output = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        location = event.get("location", "No location")
        output.append(f"- **{event['summary']}**\n  When: {start}\n  Where: {location}")
    return "\n\n".join(output)


@tool
def create_event(
    summary: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
    attendees: str = ""
) -> str:
    """Create a new Google Calendar event.

    Args:
        summary: Event title/name.
        start_time: Start time in ISO format (e.g., '2026-08-20T10:00:00-04:00').
        end_time: End time in ISO format (e.g., '2026-08-20T11:00:00-04:00').
        description: Optional event description.
        location: Optional event location.
        attendees: Optional comma-separated email addresses of attendees.

    Returns:
        Confirmation with event link.
    """
    service = get_calendar_service()
    event_body = {
        "summary": summary,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
    }
    if description:
        event_body["description"] = description
    if location:
        event_body["location"] = location
    if attendees:
        event_body["attendees"] = [{"email": e.strip()} for e in attendees.split(",")]

    event = service.events().insert(calendarId="primary", body=event_body).execute()
    return f"Event created: {event['summary']}\nLink: {event.get('htmlLink')}"
