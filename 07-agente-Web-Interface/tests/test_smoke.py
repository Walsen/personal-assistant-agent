"""Smoke tests for the web-interface backend (stage 07).

Verifies the two backend modules import cleanly and expose their public
symbols. agent_client.py builds no boto3 client at import time (the client
is created lazily inside invoke_agent), so it imports with no env/AWS
setup. handler.py reads AGENT_RUNTIME_ARN and builds a boto3 client at
import time, so it is imported with that env var set and boto3.client
patched - no real AWS/network call happens.
"""

import importlib


def test_agent_client_module_exposes_public_symbols():
    import agent_client

    assert callable(agent_client.new_session_id)
    assert callable(agent_client.invoke_agent)
    # A freshly generated session id satisfies the runtime's minimum length.
    assert len(agent_client.new_session_id()) >= agent_client._MIN_SESSION_ID_LEN


def test_handler_module_imports_and_exposes_handler(monkeypatch, mocker):
    monkeypatch.setenv(
        "AGENT_RUNTIME_ARN",
        "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test",
    )
    monkeypatch.delenv("ORIGIN_VERIFY_SECRET", raising=False)
    mocker.patch("boto3.client")

    import handler as handler_mod

    importlib.reload(handler_mod)

    assert callable(handler_mod.handler)
    assert callable(handler_mod._pick_origin)
    assert callable(handler_mod._response)


def test_handler_options_request_returns_204(monkeypatch, mocker):
    monkeypatch.setenv(
        "AGENT_RUNTIME_ARN",
        "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test",
    )
    mocker.patch("boto3.client")

    import handler as handler_mod

    importlib.reload(handler_mod)

    event = {"requestContext": {"http": {"method": "OPTIONS"}}, "headers": {}, "body": None}
    response = handler_mod.handler(event, None)

    assert response["statusCode"] == 204
