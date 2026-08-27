"""Tests for main.py's AgentCore Runtime /invocations handler (`invoke`).

`build_agent` and the agent's own __call__ are always mocked here, so no
real model call ever happens. These tests exercise only invoke()'s own
logic: building the agent for the request's session, choosing between a
normal prompt and a resumed interrupt, and shaping the JSON response (see
main.py's module docstring for the exact response shapes).

Per the "Invocation Input" invariant in AGENTS.md, runtime payloads must be
validated and text prompts required to be strings - malformed/missing
prompt input must be handled without ever reaching build_agent()/the model
with a bad value.
"""

from unittest.mock import MagicMock

import pytest

from main import invoke


def _make_context(session_id="session-123"):
    context = MagicMock()
    context.session_id = session_id
    return context


class TestInvokeNormalCompletion:
    def test_returns_completed_status_with_message_for_a_normal_prompt(self, mocker):
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.stop_reason = "end_turn"
        mock_result.message = {"role": "assistant", "content": [{"text": "Hi there!"}]}
        mock_agent.return_value = mock_result
        mocker.patch("main.build_agent", return_value=mock_agent)

        response = invoke({"prompt": "Hello"}, _make_context())

        assert response == {"status": "completed", "message": mock_result.message}
        mock_agent.assert_called_once_with("Hello")

    def test_builds_agent_scoped_to_the_request_session_id(self, mocker):
        mock_agent = MagicMock()
        mock_result = MagicMock(stop_reason="end_turn", message={"role": "assistant", "content": []})
        mock_agent.return_value = mock_result
        mock_build_agent = mocker.patch(
            "main.build_agent", return_value=mock_agent
        )

        invoke({"prompt": "Hello"}, _make_context(session_id="abc-session"))

        mock_build_agent.assert_called_once_with("abc-session")

    def test_falls_back_to_default_session_id_when_context_session_id_is_falsy(self, mocker):
        mock_agent = MagicMock()
        mock_result = MagicMock(stop_reason="end_turn", message={"role": "assistant", "content": []})
        mock_agent.return_value = mock_result
        mock_build_agent = mocker.patch(
            "main.build_agent", return_value=mock_agent
        )

        invoke({"prompt": "Hello"}, _make_context(session_id=None))

        mock_build_agent.assert_called_once_with("default")

    def test_uses_default_greeting_prompt_when_prompt_key_missing(self, mocker):
        """No "prompt" key at all falls back to a friendly default rather
        than passing None into the agent."""
        mock_agent = MagicMock()
        mock_result = MagicMock(stop_reason="end_turn", message={"role": "assistant", "content": []})
        mock_agent.return_value = mock_result
        mocker.patch("main.build_agent", return_value=mock_agent)

        invoke({}, _make_context())

        mock_agent.assert_called_once_with("Hello! How can I help you today?")


class TestInvokeInterruptResponse:
    def test_returns_interrupt_status_with_expected_shape_when_stop_reason_is_interrupt(self, mocker):
        mock_agent = MagicMock()

        mock_interrupt = MagicMock()
        mock_interrupt.id = "int-1"
        mock_interrupt.name = "gmail-delete-approval"
        mock_interrupt.reason = {"subject": "Old newsletter", "sender": "a@b.com", "message_id": "m1"}

        mock_result = MagicMock()
        mock_result.stop_reason = "interrupt"
        mock_result.interrupts = [mock_interrupt]
        mock_agent.return_value = mock_result
        mocker.patch("main.build_agent", return_value=mock_agent)

        response = invoke({"prompt": "delete that email"}, _make_context())

        assert response == {
            "status": "interrupt",
            "interrupts": [
                {
                    "id": "int-1",
                    "name": "gmail-delete-approval",
                    "reason": {"subject": "Old newsletter", "sender": "a@b.com", "message_id": "m1"},
                }
            ],
        }

    def test_handles_multiple_pending_interrupts(self, mocker):
        mock_agent = MagicMock()

        interrupt_a = MagicMock(id="int-a", reason={"foo": "bar"})
        interrupt_a.name = "tool-a"
        interrupt_b = MagicMock(id="int-b", reason={})
        interrupt_b.name = "tool-b"

        mock_result = MagicMock(stop_reason="interrupt", interrupts=[interrupt_a, interrupt_b])
        mock_agent.return_value = mock_result
        mocker.patch("main.build_agent", return_value=mock_agent)

        response = invoke({"prompt": "do two risky things"}, _make_context())

        assert response["status"] == "interrupt"
        assert [i["id"] for i in response["interrupts"]] == ["int-a", "int-b"]
        assert [i["name"] for i in response["interrupts"]] == ["tool-a", "tool-b"]

    def test_resumes_a_pending_interrupt_via_interrupt_responses(self, mocker):
        """A follow-up request carrying interrupt_responses calls the agent
        with the resume payload shape instead of a plain prompt string."""
        mock_agent = MagicMock()
        mock_result = MagicMock(stop_reason="end_turn", message={"role": "assistant", "content": []})
        mock_agent.return_value = mock_result
        mocker.patch("main.build_agent", return_value=mock_agent)

        payload = {
            "interrupt_responses": [{"interrupt_id": "int-1", "response": "y"}]
        }

        response = invoke(payload, _make_context())

        mock_agent.assert_called_once_with(
            [{"interruptResponse": {"interruptId": "int-1", "response": "y"}}]
        )
        assert response == {"status": "completed", "message": mock_result.message}

    def test_resumes_multiple_interrupt_responses_in_order(self, mocker):
        mock_agent = MagicMock()
        mock_result = MagicMock(stop_reason="end_turn", message={"role": "assistant", "content": []})
        mock_agent.return_value = mock_result
        mocker.patch("main.build_agent", return_value=mock_agent)

        payload = {
            "interrupt_responses": [
                {"interrupt_id": "int-1", "response": "y"},
                {"interrupt_id": "int-2", "response": "n"},
            ]
        }

        invoke(payload, _make_context())

        mock_agent.assert_called_once_with(
            [
                {"interruptResponse": {"interruptId": "int-1", "response": "y"}},
                {"interruptResponse": {"interruptId": "int-2", "response": "n"}},
            ]
        )


class TestInvokeMalformedInput:
    """Runtime payloads must be validated - a caller-supplied prompt that
    is not a string must be rejected before it ever reaches build_agent()
    or the model, per the "Invocation Input" invariant.
    """

    @pytest.mark.parametrize("bad_prompt", [123, 3.14, ["a", "b"], {"nested": "dict"}, True])
    def test_rejects_non_string_prompt_without_calling_build_agent(self, mocker, bad_prompt):
        mock_build_agent = mocker.patch("main.build_agent")

        response = invoke({"prompt": bad_prompt}, _make_context())

        mock_build_agent.assert_not_called()
        assert response["status"] == "error"
        assert "prompt" in response["message"].lower()

    def test_rejects_non_dict_payload_without_calling_build_agent(self, mocker):
        mock_build_agent = mocker.patch("main.build_agent")

        response = invoke("just a raw string, not a dict", _make_context())

        mock_build_agent.assert_not_called()
        assert response["status"] == "error"

    def test_rejects_none_payload_without_calling_build_agent(self, mocker):
        mock_build_agent = mocker.patch("main.build_agent")

        response = invoke(None, _make_context())

        mock_build_agent.assert_not_called()
        assert response["status"] == "error"

    def test_rejects_malformed_interrupt_responses_missing_required_keys(self, mocker):
        mock_build_agent = mocker.patch("main.build_agent")

        response = invoke({"interrupt_responses": [{"response": "y"}]}, _make_context())

        mock_build_agent.assert_not_called()
        assert response["status"] == "error"

    def test_rejects_interrupt_responses_that_is_not_a_list(self, mocker):
        mock_build_agent = mocker.patch("main.build_agent")

        response = invoke({"interrupt_responses": "not-a-list"}, _make_context())

        mock_build_agent.assert_not_called()
        assert response["status"] == "error"

    def test_empty_string_prompt_is_treated_as_valid_input(self, mocker):
        """An empty string is a valid (if useless) string prompt - it should
        not be rejected the same way non-string types are. Falsy-but-string
        input still reaches the agent unchanged.
        """
        mock_agent = MagicMock()
        mock_result = MagicMock(stop_reason="end_turn", message={"role": "assistant", "content": []})
        mock_agent.return_value = mock_result
        mocker.patch("main.build_agent", return_value=mock_agent)

        response = invoke({"prompt": ""}, _make_context())

        mock_agent.assert_called_once_with("")
        assert response["status"] == "completed"
