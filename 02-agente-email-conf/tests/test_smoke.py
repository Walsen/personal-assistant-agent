"""Smoke tests for personal_assistant_agent (email-config stage).

Verifies the agent module and the auth tool module import cleanly and
expose their public symbols. Strands Agent/BedrockModel are patched before
reloading the agent module so no AWS/Bedrock call happens; no auth helper
is actually invoked, so no Google/network call happens either.
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
    assert hasattr(module, "agent")
    assert callable(module.run)


def test_auth_module_exposes_public_helpers():
    from personal_assistant_agent.tools import auth

    assert issubclass(auth.AuthenticationError, Exception)
    assert callable(auth.get_credentials)
    assert callable(auth.get_gmail_service)
    assert callable(auth.get_calendar_service)
    assert callable(auth.get_docs_service)


def test_run_invokes_agent_without_error():
    module, mock_agent_cls, _ = _reload_with_mocks()

    module.run()

    mock_agent_cls.return_value.assert_called_once()
