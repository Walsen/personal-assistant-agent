"""Smoke tests for personal_assistant_agent (basic agent stage).

Verifies the module imports and its public symbols (SYSTEM_PROMPT,
bedrock_model, agent, run) are wired up. Strands Agent/BedrockModel are
patched before reloading the module so no AWS/Bedrock call happens.
"""

import importlib
from unittest.mock import MagicMock, patch

import personal_assistant_agent.agent as agent_module


def _reload_with_mocks():
    with patch("strands.Agent") as mock_agent_cls, patch(
        "strands.models.bedrock.BedrockModel"
    ) as mock_bedrock_model_cls:
        mock_agent_cls.return_value = MagicMock(name="agent_instance")
        mock_bedrock_model_cls.return_value = MagicMock(name="bedrock_model_instance")
        module = importlib.reload(agent_module)
        return module, mock_agent_cls, mock_bedrock_model_cls


def test_agent_module_exposes_public_symbols():
    module, _, _ = _reload_with_mocks()

    assert hasattr(module, "SYSTEM_PROMPT")
    assert hasattr(module, "bedrock_model")
    assert hasattr(module, "agent")
    assert callable(module.run)


def test_system_prompt_is_non_empty_string():
    module, _, _ = _reload_with_mocks()

    assert isinstance(module.SYSTEM_PROMPT, str)
    assert module.SYSTEM_PROMPT.strip()


def test_run_invokes_agent_without_error():
    module, mock_agent_cls, _ = _reload_with_mocks()

    module.run()

    mock_agent_cls.return_value.assert_called_once()
