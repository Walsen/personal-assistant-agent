"""Google Docs tools for the personal assistant agent."""

import logging

from strands import tool

from .auth import AuthenticationError, get_docs_service
from .errors import ToolExecutionError, google_api_call

logger = logging.getLogger(__name__)


@tool
def read_doc(document_id: str) -> str:
    """Read the text content of a Google Doc.

    Args:
        document_id: The Google Docs document ID (from the doc's URL).

    Returns:
        The plain text content of the document.
    """
    logger.info("read_doc called | document_id=%s", document_id)
    try:
        service = get_docs_service()
        doc = google_api_call(
            "read_doc",
            lambda: service.documents().get(documentId=document_id).execute(),
        )
        text_parts = []
        for element in doc.get("body", {}).get("content", []):
            paragraph = element.get("paragraph")
            if not paragraph:
                continue
            for run in paragraph.get("elements", []):
                text_run = run.get("textRun")
                if text_run:
                    text_parts.append(text_run.get("content", ""))

        return "".join(text_parts) or "(document is empty)"
    except (ToolExecutionError, AuthenticationError) as e:
        return str(e)


@tool
def create_doc(title: str, content: str = "") -> str:
    """Create a new Google Doc with an optional initial body of text.

    Args:
        title: Title of the new document.
        content: Optional initial text content to insert into the document.

    Returns:
        Confirmation message with the created document ID and link.
    """
    logger.info("create_doc called | title=%r has_content=%s", title, bool(content))
    try:
        service = get_docs_service()
        doc = google_api_call(
            "create_doc",
            lambda: service.documents().create(body={"title": title}).execute(),
        )
        document_id = doc["documentId"]

        if content:
            google_api_call(
                "create_doc",
                lambda: service.documents()
                .batchUpdate(
                    documentId=document_id,
                    body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
                )
                .execute(),
            )

        logger.info("create_doc succeeded | document_id=%s", document_id)
        link = f"https://docs.google.com/document/d/{document_id}/edit"
        return f"Document created: {title} (ID: {document_id}). Link: {link}"
    except (ToolExecutionError, AuthenticationError) as e:
        return str(e)
