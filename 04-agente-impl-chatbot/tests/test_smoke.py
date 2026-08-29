"""Smoke tests for personal_assistant_agent (chatbot stage).

Verifies the agent module and the tools package import cleanly and expose
their public symbols. Strands Agent/BedrockModel are patched before
reloading the agent module so no AWS/Bedrock call happens; the interactive
run() loop is exercised only far enough to confirm it exits cleanly on an
"exit" command (input() is mocked, so no terminal is needed).
"""

import importlib
from unittest.mock import MagicMock, patch

import personal_assistant_agent.agent as agent_module


def _reload_agent_with_mocks():
    with patch("strands.Agent") as mock_agent_cls, patch(
        "strands.models.bedrock.BedrockModel"
    ) as mock_bedrock_model_cls:
        mock_agent_cls.return_value = MagicMock(name="agent_instance")
        mock_bedrock_model_cls.return_value = MagicMock(name="bedrock_model_instance")
        module = importlib.reload(agent_module)
        return module, mock_agent_cls


def test_agent_module_exposes_public_symbols():
    module, _ = _reload_agent_with_mocks()

    assert hasattr(module, "SYSTEM_PROMPT")
    assert hasattr(module, "agent")
    assert callable(module.run)


def test_tools_package_is_populated():
    from personal_assistant_agent import tools

    assert isinstance(tools.ALL_TOOLS, list)
    assert len(tools.ALL_TOOLS) >= 7


def test_tool_modules_import():
    from personal_assistant_agent.tools import calendar, docs, gmail  # noqa: F401

    assert callable(gmail.send_email.__wrapped__ if hasattr(gmail.send_email, "__wrapped__") else True)


def test_run_loop_exits_cleanly_on_exit_command(monkeypatch, mocker):
    mock_agent = mocker.patch.object(agent_module, "agent")
    monkeypatch.setattr("builtins.input", MagicMock(side_effect=["exit"]))

    agent_module.run()  # must not raise

    mock_agent.assert_not_called()
