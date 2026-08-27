"""Tests for Google Docs tools."""

from unittest.mock import Mock

from personal_assistant_agent.tools.auth import AuthenticationError
from personal_assistant_agent.tools.docs import (
    append_to_doc,
    create_doc,
    read_doc,
    replace_text_in_doc,
    search_docs,
)
from personal_assistant_agent.tools.errors import ToolExecutionError


class TestSearchDocs:
    def test_builds_query_without_search_term(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_drive_service",
            return_value=mock_service,
        )
        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}

        search_docs()

        _, kwargs = mock_service.files.return_value.list.call_args
        assert kwargs["q"] == "mimeType='application/vnd.google-apps.document' and trashed=false"
        assert kwargs["orderBy"] == "modifiedTime desc"

    def test_builds_query_with_search_term(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_drive_service",
            return_value=mock_service,
        )
        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}

        search_docs(query="Budget")

        _, kwargs = mock_service.files.return_value.list.call_args
        assert kwargs["q"] == (
            "mimeType='application/vnd.google-apps.document' and trashed=false and name contains 'Budget'"
        )

    def test_escapes_single_quotes_in_query(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_drive_service",
            return_value=mock_service,
        )
        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}

        search_docs(query="John's notes")

        _, kwargs = mock_service.files.return_value.list.call_args
        assert "John\\'s notes" in kwargs["q"]

    def test_returns_formatted_list_of_matching_docs(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_drive_service",
            return_value=mock_service,
        )
        mock_service.files.return_value.list.return_value.execute.return_value = {
            "files": [
                {
                    "id": "doc1",
                    "name": "Budget 2026",
                    "modifiedTime": "2026-01-01T00:00:00Z",
                    "webViewLink": "https://docs.google.com/document/d/doc1/edit",
                }
            ]
        }

        result = search_docs(query="Budget")

        assert "Budget 2026" in result
        assert "doc1" in result
        assert "2026-01-01T00:00:00Z" in result
        assert "https://docs.google.com/document/d/doc1/edit" in result

    def test_returns_message_when_no_docs_found(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_drive_service",
            return_value=mock_service,
        )
        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}

        result = search_docs(query="Nonexistent")

        assert result == "No matching Google Docs found."

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_drive_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.docs.google_api_call",
            side_effect=ToolExecutionError("search_docs failed: permission denied (403) - insufficient access."),
        )

        result = search_docs(query="Budget")

        assert result == "search_docs failed: permission denied (403) - insufficient access."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_drive_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = search_docs(query="Budget")

        assert result == "credentials.json is missing."


class TestReadDoc:
    def test_returns_concatenated_text_content(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.get.return_value.execute.return_value = {
            "body": {
                "content": [
                    {"paragraph": {"elements": [{"textRun": {"content": "Hello "}}]}},
                    {"paragraph": {"elements": [{"textRun": {"content": "world"}}]}},
                ]
            }
        }

        result = read_doc("doc1")

        assert result == "Hello world"

    def test_returns_placeholder_for_empty_document(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.get.return_value.execute.return_value = {"body": {"content": []}}

        result = read_doc("doc1")

        assert result == "(document is empty)"

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.docs.google_api_call",
            side_effect=ToolExecutionError("read_doc failed: the requested item was not found (404)."),
        )

        result = read_doc("bad-id")

        assert result == "read_doc failed: the requested item was not found (404)."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = read_doc("doc1")

        assert result == "credentials.json is missing."


class TestCreateDoc:
    def test_creates_doc_without_content(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.create.return_value.execute.return_value = {
            "documentId": "doc1",
            "title": "New Doc",
        }

        result = create_doc(title="New Doc")

        assert "doc1" in result
        assert "New Doc" in result
        mock_service.documents.return_value.batchUpdate.assert_not_called()

    def test_creates_doc_with_content_inserts_text(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.create.return_value.execute.return_value = {
            "documentId": "doc2",
            "title": "New Doc With Content",
        }

        create_doc(title="New Doc With Content", content="Initial text")

        _, kwargs = mock_service.documents.return_value.batchUpdate.call_args
        assert kwargs["documentId"] == "doc2"
        assert kwargs["body"]["requests"][0]["insertText"]["text"] == "Initial text"
        assert kwargs["body"]["requests"][0]["insertText"]["location"]["index"] == 1

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.docs.google_api_call",
            side_effect=ToolExecutionError("create_doc failed: invalid request (400) - bad title."),
        )

        result = create_doc(title="")

        assert result == "create_doc failed: invalid request (400) - bad title."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = create_doc(title="New Doc")

        assert result == "credentials.json is missing."


class TestAppendToDoc:
    def test_calculates_end_index_from_last_structural_element(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.get.return_value.execute.return_value = {
            "body": {
                "content": [
                    {"endIndex": 1},
                    {"endIndex": 25},
                ]
            }
        }
        mock_service.documents.return_value.batchUpdate.return_value.execute.return_value = {}

        result = append_to_doc(document_id="doc1", text="More text")

        _, kwargs = mock_service.documents.return_value.batchUpdate.call_args
        # Last element's endIndex (25) minus 1, to insert before the implicit trailing newline.
        assert kwargs["body"]["requests"][0]["insertText"]["location"]["index"] == 24
        assert kwargs["body"]["requests"][0]["insertText"]["text"] == "More text"
        assert "doc1" in result

    def test_clamps_end_index_to_at_least_one_for_empty_document(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        # A brand new/empty doc might report an endIndex of 1, which would
        # compute to 0 - the code should clamp this back up to 1.
        mock_service.documents.return_value.get.return_value.execute.return_value = {
            "body": {"content": [{"endIndex": 1}]}
        }
        mock_service.documents.return_value.batchUpdate.return_value.execute.return_value = {}

        append_to_doc(document_id="doc1", text="First line")

        _, kwargs = mock_service.documents.return_value.batchUpdate.call_args
        assert kwargs["body"]["requests"][0]["insertText"]["location"]["index"] == 1

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.docs.google_api_call",
            side_effect=ToolExecutionError("append_to_doc failed: the requested item was not found (404)."),
        )

        result = append_to_doc(document_id="bad-id", text="text")

        assert result == "append_to_doc failed: the requested item was not found (404)."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = append_to_doc(document_id="doc1", text="text")

        assert result == "credentials.json is missing."


class TestReplaceTextInDoc:
    def test_replaces_text_and_reports_occurrence_count(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.batchUpdate.return_value.execute.return_value = {
            "replies": [{"replaceAllText": {"occurrencesChanged": 3}}]
        }

        result = replace_text_in_doc(
            document_id="doc1", find_text="old", replace_text="new", match_case=False
        )

        assert "3" in result
        assert "old" in result
        assert "new" in result
        assert "doc1" in result
        _, kwargs = mock_service.documents.return_value.batchUpdate.call_args
        request = kwargs["body"]["requests"][0]["replaceAllText"]
        assert request["containsText"] == {"text": "old", "matchCase": False}
        assert request["replaceText"] == "new"

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.docs.google_api_call",
            side_effect=ToolExecutionError("replace_text_in_doc failed: the requested item was not found (404)."),
        )

        result = replace_text_in_doc(document_id="bad-id", find_text="a", replace_text="b")

        assert result == "replace_text_in_doc failed: the requested item was not found (404)."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = replace_text_in_doc(document_id="doc1", find_text="a", replace_text="b")

        assert result == "credentials.json is missing."
