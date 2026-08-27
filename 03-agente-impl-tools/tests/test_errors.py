"""Tests for tools/errors.py: google_api_call() and its error translation."""

import pytest
from googleapiclient.errors import HttpError

from personal_assistant_agent.tools.errors import ToolExecutionError, google_api_call


def _make_http_error(status: int, reason: str = "", body: str = "") -> HttpError:
    """Build a real HttpError with a fake response object.

    googleapiclient's HttpError.__init__(resp, content, uri=None) requires
    `resp.status` (and reads `resp.reason` while parsing content), and
    `content` must be bytes.
    """

    class _FakeResp:
        def __init__(self, status: int, reason: str) -> None:
            self.status = status
            self.reason = reason

    content = body.encode("utf-8") if body else b"{}"
    return HttpError(resp=_FakeResp(status, reason), content=content, uri="https://example.invalid/api")


class TestGoogleApiCallSuccess:
    def test_returns_func_result_on_success(self):
        result = google_api_call("some_tool", lambda: {"ok": True})

        assert result == {"ok": True}

    def test_does_not_raise_when_func_succeeds(self):
        calls = []

        def func():
            calls.append(1)
            return "done"

        result = google_api_call("some_tool", func)

        assert result == "done"
        assert calls == [1]


class TestGoogleApiCallHttpErrorTranslation:
    def test_401_translates_to_authentication_expired_message(self):
        error = _make_http_error(401, reason="Invalid Credentials")

        with pytest.raises(ToolExecutionError) as exc_info:
            google_api_call("list_recent_emails", lambda: (_ for _ in ()).throw(error))

        message = str(exc_info.value)
        assert "list_recent_emails" in message
        assert "401" in message
        assert "authentication expired" in message.lower()

    def test_403_translates_to_permission_denied_message(self):
        error = _make_http_error(403, reason="Insufficient Permission")

        with pytest.raises(ToolExecutionError) as exc_info:
            google_api_call("send_email", lambda: (_ for _ in ()).throw(error))

        message = str(exc_info.value)
        assert "send_email" in message
        assert "403" in message
        assert "permission denied" in message.lower()

    def test_404_translates_to_not_found_message(self):
        error = _make_http_error(404, reason="Requested entity was not found.")

        with pytest.raises(ToolExecutionError) as exc_info:
            google_api_call("get_email", lambda: (_ for _ in ()).throw(error))

        message = str(exc_info.value)
        assert "get_email" in message
        assert "404" in message
        assert "not found" in message.lower()

    def test_429_translates_to_rate_limited_message(self):
        error = _make_http_error(429, reason="Too Many Requests")

        with pytest.raises(ToolExecutionError) as exc_info:
            google_api_call("list_upcoming_events", lambda: (_ for _ in ()).throw(error))

        message = str(exc_info.value)
        assert "list_upcoming_events" in message
        assert "429" in message
        assert "rate limited" in message.lower()

    def test_500_translates_to_server_error_message(self):
        error = _make_http_error(500, reason="Internal error")

        with pytest.raises(ToolExecutionError) as exc_info:
            google_api_call("create_event", lambda: (_ for _ in ()).throw(error))

        message = str(exc_info.value)
        assert "create_event" in message
        assert "500" in message
        assert "server error" in message.lower()

    def test_http_error_is_chained_as_cause(self):
        error = _make_http_error(401, reason="Invalid Credentials")

        with pytest.raises(ToolExecutionError) as exc_info:
            google_api_call("some_tool", lambda: (_ for _ in ()).throw(error))

        assert exc_info.value.__cause__ is error


class TestGoogleApiCallUnexpectedErrorTranslation:
    def test_generic_exception_becomes_tool_execution_error(self):
        with pytest.raises(ToolExecutionError) as exc_info:
            google_api_call("read_doc", lambda: (_ for _ in ()).throw(ValueError("boom")))

        message = str(exc_info.value)
        assert "read_doc" in message
        assert "unexpected error" in message.lower()
        assert "boom" in message

    def test_generic_exception_is_chained_as_cause(self):
        original = ValueError("boom")

        with pytest.raises(ToolExecutionError) as exc_info:
            google_api_call("read_doc", lambda: (_ for _ in ()).throw(original))

        assert exc_info.value.__cause__ is original
