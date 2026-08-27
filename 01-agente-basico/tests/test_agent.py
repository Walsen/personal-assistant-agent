"""Tests for personal_assistant_agent.agent.

These tests mock strands.Agent and strands.models.bedrock.BedrockModel
before (re)importing the agent module, so module-level construction never
touches AWS/Bedrock over the network.
"""

import importlib
from unittest.mock import MagicMock, patch

import personal_assistant_agent.agent as agent_module


def _reload_with_mocks():
    """Reload the agent module while Agent/BedrockModel are patched.

    Returns the (module, mock_agent_cls, mock_bedrock_model_cls) tuple so
    tests can inspect construction calls.
    """
    with patch("strands.Agent") as mock_agent_cls, patch(
        "strands.models.bedrock.BedrockModel"
    ) as mock_bedrock_model_cls:
        mock_agent_cls.return_value = MagicMock(name="agent_instance")
        mock_bedrock_model_cls.return_value = MagicMock(name="bedrock_model_instance")
        module = importlib.reload(agent_module)
        # Capture call args before leaving the patch context (call_args
        # objects remain valid, but re-asserting on the mocks is clearer
        # while they are still the active patched objects).
        return module, mock_agent_cls, mock_bedrock_model_cls


def test_bedrock_model_configured_with_expected_model_id_and_region():
    """bedrock_model must use the Claude Sonnet model id and us-east-1 region."""
    module, _, mock_bedrock_model_cls = _reload_with_mocks()

    mock_bedrock_model_cls.assert_called_once()
    _, kwargs = mock_bedrock_model_cls.call_args
    assert kwargs["model_id"] == "global.anthropic.claude-sonnet-4-6"
    assert kwargs["region_name"] == "us-east-1"
    assert module.bedrock_model is mock_bedrock_model_cls.return_value


def test_agent_constructed_with_bedrock_model_and_system_prompt():
    """The module-level agent must be built from bedrock_model and SYSTEM_PROMPT."""
    module, mock_agent_cls, mock_bedrock_model_cls = _reload_with_mocks()

    mock_agent_cls.assert_called_once_with(
        model=mock_bedrock_model_cls.return_value,
        system_prompt=module.SYSTEM_PROMPT,
    )
    assert module.agent is mock_agent_cls.return_value


def test_run_invokes_agent_with_expected_greeting():
    """run() must call the module-level agent with the greeting text."""
    module, mock_agent_cls, _ = _reload_with_mocks()
    mock_agent_instance = mock_agent_cls.return_value

    module.run()

    mock_agent_instance.assert_called_once_with(
        "Hello! How can you help me today?"
    )
