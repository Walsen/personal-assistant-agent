from .calendar import create_event, list_upcoming_events
from .docs import create_doc, read_doc
from .gmail import get_email, list_recent_emails, send_email

ALL_TOOLS = [
    list_recent_emails,
    get_email,
    send_email,
    list_upcoming_events,
    create_event,
    read_doc,
    create_doc,
]
