"""Smoke tests for proyecto_base.

These are minimal "does it import and are the public symbols wired up?"
checks. They construct nothing over the network: the module-level Strands
Agent is built once at import time (cheap, no Bedrock call) and every
agent(...) invocation is mocked.
"""

from unittest.mock import MagicMock, patch


def test_agent_module_imports():
    """The agent module imports cleanly and exposes its public symbols."""
    import proyecto_base.agent as agent_module

    assert hasattr(agent_module, "SYSTEM_PROMPT")
    assert hasattr(agent_module, "agent")
    assert callable(agent_module.run)


def test_system_prompt_is_non_empty_string():
    import proyecto_base.agent as agent_module

    assert isinstance(agent_module.SYSTEM_PROMPT, str)
    assert agent_module.SYSTEM_PROMPT.strip()


def test_run_does_not_raise_with_mocked_agent():
    """run() wires the greeting through to the agent without blowing up."""
    import proyecto_base.agent as agent_module

    with patch.object(agent_module, "agent", MagicMock()) as mock_agent:
        agent_module.run()

    mock_agent.assert_called_once()
