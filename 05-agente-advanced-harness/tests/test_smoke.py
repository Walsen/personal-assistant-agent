"""Smoke tests for personal_assistant_agent (advanced harness stage).

Verifies the standalone modules that don't require any network/AWS/Google
call import cleanly and expose their public symbols: the steering handler,
the notes sub-agent prompt, the tools package, and the tool error helpers.

The top-level agent module (agent.py) is intentionally NOT imported here:
importing it constructs a real BedrockModel + Agent with skills and a
FileSessionManager at module scope, which is exercised by the other test
modules with the appropriate mocks. This smoke file stays fast and
dependency-light on purpose.
"""

from personal_assistant_agent.steering import (
    CONFIRMATION_REQUIRED_TOOLS,
    ConfirmationSteeringHandler,
)


def test_steering_handler_imports_and_exposes_public_api():
    handler = ConfirmationSteeringHandler()

    assert handler.name == "confirmation-steering"
    assert callable(handler.steer_before_tool)


def test_confirmation_required_tools_set_is_populated():
    assert "send_email" in CONFIRMATION_REQUIRED_TOOLS
    assert "create_event" in CONFIRMATION_REQUIRED_TOOLS


def test_notes_agent_prompt_is_non_empty_string():
    from personal_assistant_agent.notes_agent import NOTES_SYSTEM_PROMPT

    assert isinstance(NOTES_SYSTEM_PROMPT, str)
    assert NOTES_SYSTEM_PROMPT.strip()


def test_tools_package_is_populated():
    from personal_assistant_agent import tools

    assert isinstance(tools.ALL_TOOLS, list)
    assert len(tools.ALL_TOOLS) >= 7


def test_tool_error_helpers_import():
    from personal_assistant_agent.tools.errors import ToolExecutionError, google_api_call

    assert callable(google_api_call)
    assert issubclass(ToolExecutionError, Exception)
