"""Smoke tests for personal_assistant_agent (tools stage).

Verifies the agent module, the tools package, and each individual tool
module import cleanly and expose their public symbols. Strands
Agent/BedrockModel are patched before reloading the agent module so no
AWS/Bedrock call happens; no tool is actually executed, so no
Google/network call happens either.
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


def test_tools_package_exposes_all_tools():
    from personal_assistant_agent import tools

    expected = {
        "list_recent_emails",
        "get_email",
        "send_email",
        "list_upcoming_events",
        "create_event",
        "read_doc",
        "create_doc",
    }
    exported_names = {getattr(t, "__name__", getattr(t, "tool_name", None)) for t in tools.ALL_TOOLS}

    assert len(tools.ALL_TOOLS) == len(expected)
    # Every expected tool name shows up (tools may be Strands tool wrappers,
    # so accept either __name__ or a tool_name attribute).
    for name in expected:
        assert any(name in str(n) for n in exported_names), f"missing tool: {name}"


def test_tool_modules_import_and_expose_callables():
    from personal_assistant_agent.tools import calendar, docs, gmail
    from personal_assistant_agent.tools.errors import ToolExecutionError, google_api_call

    assert callable(google_api_call)
    assert issubclass(ToolExecutionError, Exception)
    for mod in (calendar, docs, gmail):
        assert mod is not None


def test_agent_constructed_with_tools():
    module, mock_agent_cls = _reload_agent_with_mocks()

    _, kwargs = mock_agent_cls.call_args
    assert "tools" in kwargs
    assert kwargs["tools"]
