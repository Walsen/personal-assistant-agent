"""Tests for ConfirmationSteeringHandler.

steer_before_tool is the core piece of logic here: the first attempt to call
a confirmation-required tool (send_email/create_event) must be blocked
(Guide) and its signature recorded, and only a second attempt with the
*exact same* input (simulating the model retrying after the user confirmed)
should be allowed through (Proceed) - and once allowed through once, the
signature is consumed so editing the same fields again requires a fresh
confirmation.
"""

import pytest
from strands.vended_plugins.steering import Guide, Proceed

from personal_assistant_agent.steering import (
    _STATE_KEY,
    ConfirmationSteeringHandler,
)


class FakeState:
    """Minimal stand-in for agent.state, backed by a plain dict."""

    def __init__(self):
        self._data: dict = {}

    def get(self, key):
        return self._data.get(key)

    def set(self, key, value):
        self._data[key] = value


class FakeAgent:
    """Minimal stand-in for the `agent` kwarg passed to steer_before_tool."""

    def __init__(self):
        self.state = FakeState()


@pytest.fixture
def handler():
    return ConfirmationSteeringHandler()


@pytest.fixture
def agent():
    return FakeAgent()


class TestNonConfirmationTools:
    @pytest.mark.asyncio
    async def test_tool_not_requiring_confirmation_always_proceeds(self, handler, agent):
        tool_use = {"name": "list_recent_emails", "input": {"max_results": 5}}

        action = await handler.steer_before_tool(agent=agent, tool_use=tool_use)

        assert isinstance(action, Proceed)

    @pytest.mark.asyncio
    async def test_tool_not_requiring_confirmation_does_not_touch_state(self, handler, agent):
        tool_use = {"name": "archive_email", "input": {"message_id": "msg1"}}

        await handler.steer_before_tool(agent=agent, tool_use=tool_use)

        assert agent.state.get(_STATE_KEY) is None


class TestFirstCallToConfirmationRequiredTool:
    @pytest.mark.asyncio
    async def test_send_email_is_guided_on_first_attempt(self, handler, agent):
        tool_use = {
            "name": "send_email",
            "input": {"to": "a@example.com", "subject": "Hi", "body": "Hello"},
        }

        action = await handler.steer_before_tool(agent=agent, tool_use=tool_use)

        assert isinstance(action, Guide)
        assert "send_email" in action.reason

    @pytest.mark.asyncio
    async def test_create_event_is_guided_on_first_attempt(self, handler, agent):
        tool_use = {
            "name": "create_event",
            "input": {"summary": "Sync", "start_time": "2026-01-01T10:00:00Z", "end_time": "2026-01-01T11:00:00Z"},
        }

        action = await handler.steer_before_tool(agent=agent, tool_use=tool_use)

        assert isinstance(action, Guide)
        assert "create_event" in action.reason

    @pytest.mark.asyncio
    async def test_first_call_records_signature_in_state(self, handler, agent):
        tool_use = {"name": "send_email", "input": {"to": "a@example.com", "subject": "Hi", "body": "Hello"}}

        await handler.steer_before_tool(agent=agent, tool_use=tool_use)

        guided_signatures = agent.state.get(_STATE_KEY)
        assert guided_signatures is not None
        assert len(guided_signatures) == 1


class TestRetryAfterConfirmation:
    @pytest.mark.asyncio
    async def test_identical_retry_proceeds(self, handler, agent):
        tool_use = {"name": "send_email", "input": {"to": "a@example.com", "subject": "Hi", "body": "Hello"}}

        first_action = await handler.steer_before_tool(agent=agent, tool_use=tool_use)
        second_action = await handler.steer_before_tool(agent=agent, tool_use=tool_use)

        assert isinstance(first_action, Guide)
        assert isinstance(second_action, Proceed)

    @pytest.mark.asyncio
    async def test_identical_retry_removes_signature_from_state(self, handler, agent):
        tool_use = {"name": "create_event", "input": {"summary": "Sync", "start_time": "t1", "end_time": "t2"}}

        await handler.steer_before_tool(agent=agent, tool_use=tool_use)
        await handler.steer_before_tool(agent=agent, tool_use=tool_use)

        assert agent.state.get(_STATE_KEY) == []

    @pytest.mark.asyncio
    async def test_third_call_with_same_input_is_guided_again(self, handler, agent):
        """Once the signature is consumed by a confirmed retry, calling the
        exact same action again from scratch should require confirmation
        again (it's a brand new action from the model's perspective)."""
        tool_use = {"name": "send_email", "input": {"to": "a@example.com", "subject": "Hi", "body": "Hello"}}

        await handler.steer_before_tool(agent=agent, tool_use=tool_use)  # guided
        await handler.steer_before_tool(agent=agent, tool_use=tool_use)  # proceed, consumed
        third_action = await handler.steer_before_tool(agent=agent, tool_use=tool_use)  # guided again

        assert isinstance(third_action, Guide)


class TestDifferentInputAfterGuided:
    @pytest.mark.asyncio
    async def test_different_recipient_is_still_guided(self, handler, agent):
        first_tool_use = {"name": "send_email", "input": {"to": "a@example.com", "subject": "Hi", "body": "Hello"}}
        different_tool_use = {
            "name": "send_email",
            "input": {"to": "b@example.com", "subject": "Hi", "body": "Hello"},
        }

        first_action = await handler.steer_before_tool(agent=agent, tool_use=first_tool_use)
        second_action = await handler.steer_before_tool(agent=agent, tool_use=different_tool_use)

        assert isinstance(first_action, Guide)
        assert isinstance(second_action, Guide)

    @pytest.mark.asyncio
    async def test_different_input_keeps_original_signature_pending(self, handler, agent):
        first_tool_use = {"name": "create_event", "input": {"summary": "Sync", "start_time": "t1", "end_time": "t2"}}
        different_tool_use = {
            "name": "create_event",
            "input": {"summary": "Different meeting", "start_time": "t1", "end_time": "t2"},
        }

        await handler.steer_before_tool(agent=agent, tool_use=first_tool_use)
        await handler.steer_before_tool(agent=agent, tool_use=different_tool_use)

        # Both signatures are now pending confirmation.
        assert len(agent.state.get(_STATE_KEY)) == 2

        # The original (first) input should still proceed once retried.
        action = await handler.steer_before_tool(agent=agent, tool_use=first_tool_use)
        assert isinstance(action, Proceed)
