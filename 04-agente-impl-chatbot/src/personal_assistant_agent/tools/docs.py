"""Google Docs tools for the personal assistant agent."""

from strands import tool

from .auth import get_docs_service, get_drive_service


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
    service = get_drive_service()
    q = "mimeType='application/vnd.google-apps.document' and trashed=false"
    if query:
        escaped_query = query.replace("'", "\\'")
        q += f" and name contains '{escaped_query}'"

    response = (
        service.files()
        .list(
            q=q,
            pageSize=max_results,
            orderBy="modifiedTime desc",
            fields="files(id, name, modifiedTime, webViewLink)",
        )
        .execute()
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


@tool
def read_doc(document_id: str) -> str:
    """Read the text content of a Google Doc.

    Args:
        document_id: The Google Docs document ID (from the doc's URL).

    Returns:
        The plain text content of the document.
    """
    service = get_docs_service()
    doc = service.documents().get(documentId=document_id).execute()

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


@tool
def create_doc(title: str, content: str = "") -> str:
    """Create a new Google Doc with an optional initial body of text.

    Args:
        title: Title of the new document.
        content: Optional initial text content to insert into the document.

    Returns:
        Confirmation message with the created document ID and link.
    """
    service = get_docs_service()
    doc = service.documents().create(body={"title": title}).execute()
    document_id = doc["documentId"]

    if content:
        service.documents().batchUpdate(
            documentId=document_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
        ).execute()

    link = f"https://docs.google.com/document/d/{document_id}/edit"
    return f"Document created: {title} (ID: {document_id}). Link: {link}"


@tool
def append_to_doc(document_id: str, text: str) -> str:
    """Append text to the end of an existing Google Doc.

    Args:
        document_id: The Google Docs document ID (from the doc's URL, or from search_docs).
        text: The text to add at the end of the document.

    Returns:
        Confirmation message once the text has been appended.
    """
    service = get_docs_service()
    doc = service.documents().get(documentId=document_id).execute()

    # The last structural element's endIndex points just past the final
    # (implicit) newline, so insert one position before it.
    end_index = doc["body"]["content"][-1]["endIndex"] - 1
    end_index = max(end_index, 1)

    service.documents().batchUpdate(
        documentId=document_id,
        body={"requests": [{"insertText": {"location": {"index": end_index}, "text": text}}]},
    ).execute()

    return f"Text appended to document {document_id}."


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
    service = get_docs_service()
    result = service.documents().batchUpdate(
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
    ).execute()

    occurrences = result["replies"][0]["replaceAllText"].get("occurrencesChanged", 0)
    return f"Replaced {occurrences} occurrence(s) of '{find_text}' with '{replace_text}' in document {document_id}."
