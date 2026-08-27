"""Tests for backend/agent_client.py.

All tests pass a Mock() as the `client` param to invoke_agent() so no real
boto3 client is ever constructed and no AWS/network calls happen.
"""

import json
from unittest.mock import Mock

import agent_client


def _mock_client_with_response(payload: dict) -> Mock:
    """Build a Mock boto3 client whose invoke_agent_runtime() returns a
    response shaped like the real API: {"response": <stream-like with
    .read()>}.
    """
    client = Mock()
    stream = Mock()
    stream.read.return_value = json.dumps(payload).encode("utf-8")
    client.invoke_agent_runtime.return_value = {"response": stream}
    return client


def test_generates_new_session_id_when_body_has_none(mocker):
    client = _mock_client_with_response({"status": "completed"})
    fake_session_id = "generated-session-id-1234567890123"
    mocker.patch.object(agent_client, "new_session_id", return_value=fake_session_id)

    result = agent_client.invoke_agent("arn:aws:bedrock-agentcore:...", {"prompt": "hi"}, client=client)

    assert result["session_id"] == fake_session_id
    _, kwargs = client.invoke_agent_runtime.call_args
    assert kwargs["runtimeSessionId"] == fake_session_id


def test_reuses_session_id_from_body_when_provided(mocker):
    client = _mock_client_with_response({"status": "completed"})
    new_session_id_spy = mocker.patch.object(agent_client, "new_session_id")

    existing_session_id = "existing-session-id-caller-provided-123"
    result = agent_client.invoke_agent(
        "arn:aws:bedrock-agentcore:...",
        {"prompt": "hi", "session_id": existing_session_id},
        client=client,
    )

    assert result["session_id"] == existing_session_id
    new_session_id_spy.assert_not_called()
    _, kwargs = client.invoke_agent_runtime.call_args
    assert kwargs["runtimeSessionId"] == existing_session_id


def test_builds_prompt_payload_when_body_has_prompt(mocker):
    client = _mock_client_with_response({"status": "completed"})
    mocker.patch.object(agent_client, "new_session_id", return_value="sid-0000000000000000000000000000000")

    agent_client.invoke_agent(
        "arn:aws:bedrock-agentcore:...",
        {"prompt": "what's on my calendar today?"},
        client=client,
    )

    _, kwargs = client.invoke_agent_runtime.call_args
    sent_payload = json.loads(kwargs["payload"])
    assert sent_payload == {"prompt": "what's on my calendar today?"}


def test_builds_interrupt_responses_payload_when_body_has_them(mocker):
    client = _mock_client_with_response({"status": "completed"})
    mocker.patch.object(agent_client, "new_session_id", return_value="sid-0000000000000000000000000000000")

    interrupt_responses = [{"interrupt_id": "abc123", "response": "y"}]
    agent_client.invoke_agent(
        "arn:aws:bedrock-agentcore:...",
        {"interrupt_responses": interrupt_responses, "session_id": "existing-session-id-123456789012345"},
        client=client,
    )

    _, kwargs = client.invoke_agent_runtime.call_args
    sent_payload = json.loads(kwargs["payload"])
    assert sent_payload == {"interrupt_responses": interrupt_responses}


def test_parses_mocked_response_and_injects_session_id(mocker):
    mocker.patch.object(agent_client, "new_session_id", return_value="sid-0000000000000000000000000000000")
    client = _mock_client_with_response({"status": "completed", "message": {"role": "assistant", "content": "hi"}})

    result = agent_client.invoke_agent("arn:aws:bedrock-agentcore:...", {"prompt": "hi"}, client=client)

    assert result["status"] == "completed"
    assert result["message"] == {"role": "assistant", "content": "hi"}
    assert result["session_id"] == "sid-0000000000000000000000000000000"
