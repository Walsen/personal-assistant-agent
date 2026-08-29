"""Smoke tests for the AgentCore Runtime application (stage 06).

Verifies the runtime entrypoint (main.py) and the agent module import
cleanly and expose their public symbols, and that a malformed payload is
rejected by invoke() without ever building an agent or making a model call.

No network/AWS/Bedrock call happens: agent.py builds its Agent lazily (not
at import time), and the one invoke() path exercised here is rejected
before build_agent() is reached.
"""

from unittest.mock import MagicMock

import pytest


def test_main_module_exposes_public_symbols():
    import main

    assert callable(main.invoke)
    assert callable(main._validate_payload)
    assert callable(main._format_response)
    assert hasattr(main, "app")


def test_agent_module_exposes_public_symbols():
    from personal_assistant_agent import agent as agent_module

    assert callable(agent_module.build_agent)
    assert callable(agent_module._build_session_manager)
    assert hasattr(agent_module, "SYSTEM_PROMPT")


def test_invoke_rejects_malformed_payload_without_building_agent(mocker):
    import main

    mock_build_agent = mocker.patch("main.build_agent")

    context = MagicMock()
    context.session_id = "smoke-session"
    response = main.invoke("not-a-dict", context)

    assert response["status"] == "error"
    mock_build_agent.assert_not_called()


@pytest.mark.parametrize("payload", [{"prompt": 123}, {"interrupt_responses": "nope"}])
def test_validate_payload_flags_bad_input(payload):
    import main

    assert main._validate_payload(payload) is not None
