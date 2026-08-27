"""Google Docs tools for the personal assistant agent."""

import logging

from strands import tool

from .auth import AuthenticationError, get_docs_service, get_drive_service
from .errors import ToolExecutionError, google_api_call

logger = logging.getLogger(__name__)


@tool
def search_docs(query: str = "", max_results: int = 10) -> str:
    """Search for Google Docs in the user's Drive by name, or list the most
    recently modified docs if no query is given.

    Args:
        query: Optional text to search for in the document name. If empty,
            returns the most recently modified documents instead.
        max_results: Maximum number of documents to return (default: 10).

    Returns:
        A formatted list of matching documents with name, ID, and last modified time.
    """
    logger.info("search_docs called | query=%r max_results=%s", query, max_results)
    try:
        service = get_drive_service()
        q = "mimeType='application/vnd.google-apps.document' and trashed=false"
        if query:
            escaped_query = query.replace("'", "\\'")
            q += f" and name contains '{escaped_query}'"

        response = google_api_call(
            "search_docs",
            lambda: service.files()
            .list(q=q, pageSize=max_results, orderBy="modifiedTime desc",
                  fields="files(id, name, modifiedTime, webViewLink)")
            .execute(),
        )
        files = response.get("files", [])
        if not files:
            return "No matching Google Docs found."

        lines = []
        for f in files:
            lines.append(
                f"- {f['name']} (ID: {f['id']}, last modified: {f['modifiedTime']})\n  Link: {f.get('webViewLink', '')}"
            )
        return "\n".join(lines)
    except (ToolExecutionError, AuthenticationError) as e:
        return str(e)


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


@tool
def append_to_doc(document_id: str, text: str) -> str:
    """Append text to the end of an existing Google Doc.

    Args:
        document_id: The Google Docs document ID (from the doc's URL, or from search_docs).
        text: The text to add at the end of the document.

    Returns:
        Confirmation message once the text has been appended.
    """
    logger.info("append_to_doc called | document_id=%s", document_id)
    try:
        service = get_docs_service()
        doc = google_api_call(
            "append_to_doc",
            lambda: service.documents().get(documentId=document_id).execute(),
        )

        # The last structural element's endIndex points just past the final
        # (implicit) newline, so insert one position before it.
        end_index = doc["body"]["content"][-1]["endIndex"] - 1
        end_index = max(end_index, 1)

        google_api_call(
            "append_to_doc",
            lambda: service.documents()
            .batchUpdate(
                documentId=document_id,
                body={"requests": [{"insertText": {"location": {"index": end_index}, "text": text}}]},
            )
            .execute(),
        )
        logger.info("append_to_doc succeeded | document_id=%s", document_id)
        return f"Text appended to document {document_id}."
    except (ToolExecutionError, AuthenticationError) as e:
        return str(e)


@tool
def replace_text_in_doc(document_id: str, find_text: str, replace_text: str, match_case: bool = True) -> str:
    """Find and replace all occurrences of a piece of text within a Google Doc.

    Args:
        document_id: The Google Docs document ID (from the doc's URL, or from search_docs).
        find_text: The exact text to search for.
        replace_text: The text to replace each occurrence with.
        match_case: Whether the search should be case-sensitive (default: True).

    Returns:
        Confirmation message with the number of replacements made.
    """
    logger.info("replace_text_in_doc called | document_id=%s find_text=%r", document_id, find_text)
    try:
        service = get_docs_service()
        result = google_api_call(
            "replace_text_in_doc",
            lambda: service.documents()
            .batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {
                            "replaceAllText": {
                                "containsText": {"text": find_text, "matchCase": match_case},
                                "replaceText": replace_text,
                            }
                        }
                    ]
                },
            )
            .execute(),
        )
        occurrences = result["replies"][0]["replaceAllText"].get("occurrencesChanged", 0)
        logger.info("replace_text_in_doc succeeded | document_id=%s occurrences=%s", document_id, occurrences)
        return f"Replaced {occurrences} occurrence(s) of '{find_text}' with '{replace_text}' in document {document_id}."
    except (ToolExecutionError, AuthenticationError) as e:
        return str(e)
