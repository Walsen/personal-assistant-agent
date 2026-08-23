from .calendar import create_event, list_upcoming_events
from .docs import append_to_doc, create_doc, read_doc, replace_text_in_doc, search_docs
from .gmail import archive_email, delete_email, get_email, list_recent_emails, send_email

ALL_TOOLS = [
    list_recent_emails,
    get_email,
    send_email,
    archive_email,
    delete_email,
    list_upcoming_events,
    create_event,
    search_docs,
    read_doc,
    create_doc,
    append_to_doc,
    replace_text_in_doc,
]
