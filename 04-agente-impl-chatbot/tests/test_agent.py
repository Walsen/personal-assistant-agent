"""Tests for the interactive chatbot loop in agent.run()."""

from unittest.mock import Mock

from personal_assistant_agent import agent as agent_module


class TestRun:
    def test_exit_command_ends_the_loop_without_calling_agent(self, monkeypatch, mocker):
        mock_agent = mocker.patch.object(agent_module, "agent")
        monkeypatch.setattr("builtins.input", Mock(side_effect=["exit"]))

        agent_module.run()

        mock_agent.assert_not_called()

    def test_quit_command_ends_the_loop_without_calling_agent(self, monkeypatch, mocker):
        mock_agent = mocker.patch.object(agent_module, "agent")
        monkeypatch.setattr("builtins.input", Mock(side_effect=["quit"]))

        agent_module.run()

        mock_agent.assert_not_called()

    def test_exit_command_is_case_insensitive(self, monkeypatch, mocker):
        mock_agent = mocker.patch.object(agent_module, "agent")
        monkeypatch.setattr("builtins.input", Mock(side_effect=["EXIT"]))

        agent_module.run()

        mock_agent.assert_not_called()

    def test_empty_input_is_skipped_and_loop_continues(self, monkeypatch, mocker):
        mock_agent = mocker.patch.object(agent_module, "agent")
        monkeypatch.setattr("builtins.input", Mock(side_effect=["", "   ", "exit"]))

        agent_module.run()

        mock_agent.assert_not_called()

    def test_other_input_is_forwarded_to_agent(self, monkeypatch, mocker):
        mock_agent = mocker.patch.object(agent_module, "agent")
        monkeypatch.setattr("builtins.input", Mock(side_effect=["What's on my calendar?", "exit"]))

        agent_module.run()

        mock_agent.assert_called_once_with("What's on my calendar?")

    def test_multiple_messages_are_each_forwarded_in_order(self, monkeypatch, mocker):
        mock_agent = mocker.patch.object(agent_module, "agent")
        monkeypatch.setattr(
            "builtins.input", Mock(side_effect=["first message", "second message", "quit"])
        )

        agent_module.run()

        assert mock_agent.call_args_list == [
            mocker.call("first message"),
            mocker.call("second message"),
        ]

    def test_input_is_stripped_before_being_forwarded(self, monkeypatch, mocker):
        mock_agent = mocker.patch.object(agent_module, "agent")
        monkeypatch.setattr("builtins.input", Mock(side_effect=["  hello there  ", "exit"]))

        agent_module.run()

        mock_agent.assert_called_once_with("hello there")

    def test_keyboard_interrupt_ends_the_loop_without_calling_agent(self, monkeypatch, mocker):
        mock_agent = mocker.patch.object(agent_module, "agent")
        monkeypatch.setattr("builtins.input", Mock(side_effect=KeyboardInterrupt))

        agent_module.run()

        mock_agent.assert_not_called()

    def test_eof_error_ends_the_loop_without_calling_agent(self, monkeypatch, mocker):
        mock_agent = mocker.patch.object(agent_module, "agent")
        monkeypatch.setattr("builtins.input", Mock(side_effect=EOFError))

        agent_module.run()

        mock_agent.assert_not_called()
