"""Tests for proyecto_base.agent — run() and the module-level agent object.

The Strands ``Agent.__call__`` is mocked before/at import time so tests never
make a real Bedrock/network call.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def agent_module():
    """Import proyecto_base.agent with the module-level agent object mocked.

    Patches the already-constructed module-level ``agent`` in place, so the
    real ``Agent.__init__`` still runs once at import time (cheap, no network
    call) but every call to ``agent(...)`` is captured by a MagicMock.
    """
    import proyecto_base.agent as agent_module

    with patch.object(agent_module, "agent", MagicMock()) as mock_agent:
        yield agent_module, mock_agent


def test_run_invokes_agent_with_expected_greeting(agent_module):
    module, mock_agent = agent_module

    module.run()

    mock_agent.assert_called_once_with("Hello! How can you help me today?")


def test_system_prompt_matches_source():
    import proyecto_base.agent as agent_module

    assert agent_module.SYSTEM_PROMPT == "You are a helpful personal assistant."


def test_agent_object_constructed_with_system_prompt():
    """The module-level agent is a Strands Agent built from SYSTEM_PROMPT."""
    import proyecto_base.agent as agent_module
    from strands import Agent

    assert isinstance(agent_module.agent, Agent)
