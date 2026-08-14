"""Google Docs tools for the personal assistant agent."""

from strands import tool
from tools.auth import get_docs_service


@tool
def create_document(title: str, body_text: str = "") -> str:
    """Create a new Google Doc.

    Args:
        title: Document title.
        body_text: Optional initial text content for the document.

    Returns:
        Document ID and URL of the created document.
    """
    service = get_docs_service()
    doc = service.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    if body_text:
        service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": body_text}}]}
        ).execute()

    return f"Document created: '{title}'\nID: {doc_id}\nURL: https://docs.google.com/document/d/{doc_id}"


@tool
def get_document(document_id: str) -> str:
    """Read the content of a Google Doc.

    Args:
        document_id: The Google Doc document ID (from the URL).

    Returns:
        The plain text content of the document.
    """
    service = get_docs_service()
    doc = service.documents().get(documentId=document_id).execute()

    content = ""
    for element in doc.get("body", {}).get("content", []):
        if "paragraph" in element:
            for run in element["paragraph"].get("elements", []):
                if "textRun" in run:
                    content += run["textRun"]["content"]

    return f"**{doc['title']}**\n\n{content}" if content else f"Document '{doc['title']}' is empty."


@tool
def update_document(document_id: str, text_to_append: str) -> str:
    """Append text to an existing Google Doc.

    Args:
        document_id: The Google Doc document ID.
        text_to_append: Text to append at the end of the document.

    Returns:
        Confirmation that the document was updated.
    """
    service = get_docs_service()
    doc = service.documents().get(documentId=document_id).execute()

    # Find the end index of the document
    body_content = doc.get("body", {}).get("content", [])
    end_index = body_content[-1]["endIndex"] - 1 if body_content else 1

    service.documents().batchUpdate(
        documentId=document_id,
        body={"requests": [{"insertText": {"location": {"index": end_index}, "text": text_to_append}}]}
    ).execute()

    return f"Document '{doc['title']}' updated successfully. Appended {len(text_to_append)} characters."
