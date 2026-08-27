"""Tests for tools/docs.py."""

from unittest.mock import Mock

from googleapiclient.errors import HttpError

from personal_assistant_agent.tools.auth import AuthenticationError
from personal_assistant_agent.tools.docs import create_doc, read_doc


def _make_http_error(status: int, reason: str = "error") -> HttpError:
    class _FakeResp:
        def __init__(self, status: int, reason: str) -> None:
            self.status = status
            self.reason = reason

    return HttpError(resp=_FakeResp(status, reason), content=b"{}", uri="https://example.invalid/api")


class TestReadDoc:
    def test_returns_plain_text_content(self, mocker):
        mock_service = Mock()
        mock_service.documents.return_value.get.return_value.execute.return_value = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Hello "}},
                                {"textRun": {"content": "world.\n"}},
                            ]
                        }
                    },
                    {"sectionBreak": {}},
                ]
            }
        }
        mocker.patch("personal_assistant_agent.tools.docs.get_docs_service", return_value=mock_service)

        result = read_doc("doc-123")

        assert result == "Hello world.\n"

    def test_returns_empty_document_message_when_no_content(self, mocker):
        mock_service = Mock()
        mock_service.documents.return_value.get.return_value.execute.return_value = {"body": {"content": []}}
        mocker.patch("personal_assistant_agent.tools.docs.get_docs_service", return_value=mock_service)

        result = read_doc("doc-empty")

        assert result == "(document is empty)"

    def test_returns_error_message_on_authentication_error(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            side_effect=AuthenticationError("credentials.json is missing."),
        )

        result = read_doc("doc-123")

        assert result == "credentials.json is missing."

    def test_returns_error_message_on_http_error(self, mocker):
        mock_service = Mock()
        mock_service.documents.return_value.get.return_value.execute.side_effect = _make_http_error(
            404, "Requested entity was not found."
        )
        mocker.patch("personal_assistant_agent.tools.docs.get_docs_service", return_value=mock_service)

        result = read_doc("does-not-exist")

        assert "read_doc" in result
        assert "not found" in result.lower()


class TestCreateDoc:
    def test_returns_confirmation_without_content(self, mocker):
        mock_service = Mock()
        mock_service.documents.return_value.create.return_value.execute.return_value = {
            "documentId": "doc-new",
        }
        mocker.patch("personal_assistant_agent.tools.docs.get_docs_service", return_value=mock_service)

        result = create_doc(title="My new doc")

        assert "My new doc" in result
        assert "doc-new" in result
        assert "https://docs.google.com/document/d/doc-new/edit" in result
        mock_service.documents.return_value.batchUpdate.assert_not_called()

    def test_returns_confirmation_and_inserts_content_when_provided(self, mocker):
        mock_service = Mock()
        mock_service.documents.return_value.create.return_value.execute.return_value = {
            "documentId": "doc-new",
        }
        mock_service.documents.return_value.batchUpdate.return_value.execute.return_value = {}
        mocker.patch("personal_assistant_agent.tools.docs.get_docs_service", return_value=mock_service)

        result = create_doc(title="My new doc", content="Initial text.")

        assert "My new doc" in result
        assert "doc-new" in result
        mock_service.documents.return_value.batchUpdate.assert_called_once()
        _, kwargs = mock_service.documents.return_value.batchUpdate.call_args
        assert kwargs["documentId"] == "doc-new"
        assert kwargs["body"]["requests"][0]["insertText"]["text"] == "Initial text."

    def test_returns_error_message_on_authentication_error(self, mocker):
        mocker.patch(
            "personal_assistant_agent.tools.docs.get_docs_service",
            side_effect=AuthenticationError("auth failed"),
        )

        result = create_doc(title="My new doc")

        assert result == "auth failed"

    def test_returns_error_message_on_http_error_during_create(self, mocker):
        mock_service = Mock()
        mock_service.documents.return_value.create.return_value.execute.side_effect = _make_http_error(
            429, "Too Many Requests"
        )
        mocker.patch("personal_assistant_agent.tools.docs.get_docs_service", return_value=mock_service)

        result = create_doc(title="My new doc")

        assert "create_doc" in result
        assert "rate limited" in result.lower()

    def test_returns_error_message_on_http_error_during_content_insert(self, mocker):
        mock_service = Mock()
        mock_service.documents.return_value.create.return_value.execute.return_value = {
            "documentId": "doc-new",
        }
        mock_service.documents.return_value.batchUpdate.return_value.execute.side_effect = _make_http_error(
            500, "Internal error"
        )
        mocker.patch("personal_assistant_agent.tools.docs.get_docs_service", return_value=mock_service)

        result = create_doc(title="My new doc", content="Initial text.")

        assert "create_doc" in result
        assert "server error" in result.lower()
