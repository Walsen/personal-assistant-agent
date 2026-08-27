"""Tests for build_agent()'s session manager selection in agent.py.

build_agent(session_id) must pick FileSessionManager when AGENT_SESSIONS_BUCKET
is unset (local CLI development) and S3SessionManager when it is set
(AgentCore Runtime deployment, per the Liskov Substitution note in the
engineering-practices steering doc: agent.py shouldn't need to know which one
is active, callers just get a working session_manager either way).

The S3SessionManager import is mocked in every test that exercises the S3
branch so no real AWS Secrets/S3 call is ever made.
"""

import importlib

import pytest
from strands.session.file_session_manager import FileSessionManager


@pytest.fixture(autouse=True)
def isolated_sessions_dir(tmp_path, monkeypatch):
    """Redirect the local FileSessionManager storage dir to tmp_path so
    tests never read/write the real project's .sessions/ directory.
    """
    import personal_assistant_agent.agent as agent_module

    monkeypatch.setattr(agent_module, "SESSIONS_DIR", tmp_path / ".sessions")
    return tmp_path


class TestBuildSessionManagerWithoutBucket:
    def test_uses_file_session_manager_when_bucket_env_var_unset(self, monkeypatch):
        monkeypatch.delenv("AGENT_SESSIONS_BUCKET", raising=False)

        import personal_assistant_agent.agent as agent_module

        importlib.reload(agent_module)
        monkeypatch.setattr(agent_module, "SESSIONS_BUCKET", None)

        manager = agent_module._build_session_manager("session-1")

        assert isinstance(manager, FileSessionManager)

    def test_build_agent_uses_file_session_manager_when_bucket_unset(self, monkeypatch):
        monkeypatch.delenv("AGENT_SESSIONS_BUCKET", raising=False)

        import personal_assistant_agent.agent as agent_module

        monkeypatch.setattr(agent_module, "SESSIONS_BUCKET", None)

        agent = agent_module.build_agent("session-2")

        assert isinstance(agent._session_manager, FileSessionManager)


class TestBuildSessionManagerWithBucket:
    def test_uses_s3_session_manager_when_bucket_env_var_set(self, monkeypatch, mocker):
        monkeypatch.setenv("AGENT_SESSIONS_BUCKET", "my-sessions-bucket")

        import personal_assistant_agent.agent as agent_module

        monkeypatch.setattr(agent_module, "SESSIONS_BUCKET", "my-sessions-bucket")
        monkeypatch.setattr(agent_module, "SESSIONS_S3_PREFIX", "personal-assistant-sessions")

        mock_s3_session_manager_cls = mocker.patch(
            "strands.session.s3_session_manager.S3SessionManager"
        )

        manager = agent_module._build_session_manager("session-3")

        mock_s3_session_manager_cls.assert_called_once_with(
            session_id="session-3",
            bucket="my-sessions-bucket",
            prefix="personal-assistant-sessions",
        )
        assert manager is mock_s3_session_manager_cls.return_value

    def test_build_agent_uses_s3_session_manager_when_bucket_set(self, monkeypatch, mocker):
        monkeypatch.setenv("AGENT_SESSIONS_BUCKET", "my-sessions-bucket")

        import personal_assistant_agent.agent as agent_module

        monkeypatch.setattr(agent_module, "SESSIONS_BUCKET", "my-sessions-bucket")

        mock_s3_session_manager_cls = mocker.patch(
            "strands.session.s3_session_manager.S3SessionManager"
        )

        agent = agent_module.build_agent("session-4")

        mock_s3_session_manager_cls.assert_called_once()
        assert agent._session_manager is mock_s3_session_manager_cls.return_value


class TestBuildAgentPerSessionIsolation:
    def test_build_agent_returns_a_fresh_agent_each_call(self, monkeypatch):
        """Each AgentCore Runtime invocation must get its own Agent instance
        scoped to its session id (see build_agent's docstring) rather than
        reusing a shared agent across sessions.
        """
        monkeypatch.delenv("AGENT_SESSIONS_BUCKET", raising=False)

        import personal_assistant_agent.agent as agent_module

        monkeypatch.setattr(agent_module, "SESSIONS_BUCKET", None)

        agent_a = agent_module.build_agent("session-a")
        agent_b = agent_module.build_agent("session-b")

        assert agent_a is not agent_b
        assert agent_a._session_manager is not agent_b._session_manager
