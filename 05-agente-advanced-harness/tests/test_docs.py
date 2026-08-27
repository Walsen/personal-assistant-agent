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
                    "name": "Meeting Notes",
                    "modifiedTime": "2026-01-01T10:00:00Z",
                    "webViewLink": "https://docs.google.com/document/d/doc1",
                }
            ]
        }

        result = search_docs(query="Meeting")

        assert "Meeting Notes" in result
        assert "doc1" in result
        assert "https://docs.google.com/document/d/doc1" in result

    def test_query_is_included_in_drive_search_filter(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_drive_service",
            return_value=mock_service,
        )
        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}

        search_docs(query="Roadmap", max_results=3)

        _, kwargs = mock_service.files.return_value.list.call_args
        assert "Roadmap" in kwargs["q"]
        assert "mimeType='application/vnd.google-apps.document'" in kwargs["q"]
        assert kwargs["pageSize"] == 3

    def test_empty_query_lists_recently_modified_docs_without_name_filter(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_drive_service",
            return_value=mock_service,
        )
        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}

        search_docs()

        _, kwargs = mock_service.files.return_value.list.call_args
        assert "name contains" not in kwargs["q"]

    def test_returns_message_when_no_docs_found(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_drive_service",
            return_value=mock_service,
        )
        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}

        result = search_docs(query="nonexistent")

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

        result = search_docs(query="x")

        assert result == "search_docs failed: permission denied (403) - insufficient access."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_drive_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = search_docs(query="x")

        assert result == "credentials.json is missing."


class TestReadDoc:
    def test_returns_plain_text_content(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.get.return_value.execute.return_value = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [{"textRun": {"content": "Hello "}}, {"textRun": {"content": "world\n"}}]
                        }
                    }
                ]
            }
        }

        result = read_doc("doc123")

        assert result == "Hello world\n"

    def test_returns_placeholder_for_empty_document(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.get.return_value.execute.return_value = {"body": {"content": []}}

        result = read_doc("doc123")

        assert result == "(document is empty)"

    def test_skips_non_paragraph_elements(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.get.return_value.execute.return_value = {
            "body": {
                "content": [
                    {"sectionBreak": {}},
                    {"paragraph": {"elements": [{"textRun": {"content": "Actual text"}}]}},
                ]
            }
        }

        result = read_doc("doc123")

        assert result == "Actual text"

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

        result = read_doc("doc123")

        assert result == "credentials.json is missing."


class TestCreateDoc:
    def test_creates_doc_without_content(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.create.return_value.execute.return_value = {
            "documentId": "newdoc1",
            "title": "My Doc",
        }

        result = create_doc(title="My Doc")

        assert "My Doc" in result
        assert "newdoc1" in result
        mock_service.documents.return_value.batchUpdate.assert_not_called()

    def test_creates_doc_with_initial_content(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.create.return_value.execute.return_value = {
            "documentId": "newdoc2",
            "title": "My Doc",
        }

        result = create_doc(title="My Doc", content="Initial text")

        assert "newdoc2" in result
        mock_service.documents.return_value.batchUpdate.assert_called_once()
        _, kwargs = mock_service.documents.return_value.batchUpdate.call_args
        assert kwargs["documentId"] == "newdoc2"
        assert kwargs["body"]["requests"][0]["insertText"]["text"] == "Initial text"

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.docs.google_api_call",
            side_effect=ToolExecutionError("create_doc failed: Google API server error (500)."),
        )

        result = create_doc(title="My Doc")

        assert result == "create_doc failed: Google API server error (500)."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = create_doc(title="My Doc")

        assert result == "credentials.json is missing."


class TestAppendToDoc:
    def test_appends_text_at_correct_index(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.get.return_value.execute.return_value = {
            "body": {"content": [{"endIndex": 25}]}
        }

        result = append_to_doc("doc123", "more text")

        assert "doc123" in result
        _, kwargs = mock_service.documents.return_value.batchUpdate.call_args
        assert kwargs["documentId"] == "doc123"
        assert kwargs["body"]["requests"][0]["insertText"]["location"]["index"] == 24
        assert kwargs["body"]["requests"][0]["insertText"]["text"] == "more text"

    def test_end_index_is_clamped_to_at_least_one(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.get.return_value.execute.return_value = {
            "body": {"content": [{"endIndex": 1}]}
        }

        append_to_doc("doc123", "text")

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

        result = append_to_doc("bad-id", "text")

        assert result == "append_to_doc failed: the requested item was not found (404)."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = append_to_doc("doc123", "text")

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

        result = replace_text_in_doc("doc123", "old", "new")

        assert "3" in result
        assert "old" in result
        assert "new" in result
        assert "doc123" in result

    def test_passes_match_case_flag_through(self, mocker):
        mock_service = Mock()
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=mock_service,
        )
        mock_service.documents.return_value.batchUpdate.return_value.execute.return_value = {
            "replies": [{"replaceAllText": {"occurrencesChanged": 0}}]
        }

        replace_text_in_doc("doc123", "old", "new", match_case=False)

        _, kwargs = mock_service.documents.return_value.batchUpdate.call_args
        request = kwargs["body"]["requests"][0]["replaceAllText"]
        assert request["containsText"]["matchCase"] is False

    def test_returns_tool_execution_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            return_value=Mock(),
        )
        mocker.patch(
            "personal_assistant_agent.tools.docs.google_api_call",
            side_effect=ToolExecutionError("replace_text_in_doc failed: invalid request (400) - bad request parameters."),
        )

        result = replace_text_in_doc("doc123", "old", "new")

        assert result == "replace_text_in_doc failed: invalid request (400) - bad request parameters."

    def test_returns_authentication_error_message_instead_of_raising(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = replace_text_in_doc("doc123", "old", "new")

        assert result == "credentials.json is missing."
