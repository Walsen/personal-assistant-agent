"""Tests for backend/handler.py (the Lambda Function URL entrypoint).

handler.py reads AGENT_RUNTIME_ARN (required) and ORIGIN_VERIFY_SECRET
(optional) from the environment at import time, and constructs a boto3
client at import time too. So every test:
  1. sets the env vars it needs via monkeypatch.setenv,
  2. (re)imports the module via importlib.reload so it picks up those vars,
  3. patches `handler.invoke_agent` (where it's imported into handler.py)
     to avoid any real AWS call.
"""

import importlib
import json

import pytest


@pytest.fixture
def handler_module(monkeypatch):
    """Import (or reload) backend/handler.py with a fresh env each test."""
    monkeypatch.setenv("AGENT_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test")
    monkeypatch.delenv("ORIGIN_VERIFY_SECRET", raising=False)

    import handler as handler_mod

    importlib.reload(handler_mod)
    return handler_mod


def _event(method="POST", body=None, headers=None):
    return {
        "requestContext": {"http": {"method": method}},
        "headers": headers or {},
        "body": json.dumps(body) if body is not None else None,
    }


def test_options_request_returns_204(handler_module):
    response = handler_module.handler(_event(method="OPTIONS"), None)

    assert response["statusCode"] == 204


def test_missing_origin_verify_header_returns_403_when_secret_set(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test")
    monkeypatch.setenv("ORIGIN_VERIFY_SECRET", "super-secret")

    import handler as handler_mod

    importlib.reload(handler_mod)

    response = handler_mod.handler(_event(body={"prompt": "hi"}), None)

    assert response["statusCode"] == 403


def test_wrong_origin_verify_header_returns_403_when_secret_set(monkeypatch):
    monkeypatch.setenv("AGENT_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test")
    monkeypatch.setenv("ORIGIN_VERIFY_SECRET", "super-secret")

    import handler as handler_mod

    importlib.reload(handler_mod)

    response = handler_mod.handler(_event(body={"prompt": "hi"}, headers={"x-origin-verify": "wrong"}), None)

    assert response["statusCode"] == 403


def test_invalid_json_body_returns_400(handler_module):
    event = _event(method="POST")
    event["body"] = "{not valid json"

    response = handler_module.handler(event, None)

    assert response["statusCode"] == 400


def test_valid_request_returns_200_with_agent_response(handler_module, mocker):
    mocked_result = {"status": "completed", "message": {"role": "assistant", "content": "hi"}, "session_id": "sid-1"}
    mock_invoke_agent = mocker.patch.object(handler_module, "invoke_agent", return_value=mocked_result)

    response = handler_module.handler(_event(body={"prompt": "hi"}), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == mocked_result
    mock_invoke_agent.assert_called_once()


def test_agent_invocation_exception_is_caught_and_returns_500(handler_module, mocker):
    mocker.patch.object(handler_module, "invoke_agent", side_effect=RuntimeError("boom"))

    response = handler_module.handler(_event(body={"prompt": "hi"}), None)

    assert response["statusCode"] == 500
    assert json.loads(response["body"])["status"] == "error"
