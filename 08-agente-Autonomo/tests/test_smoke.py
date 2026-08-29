"""Smoke tests for the autonomous weekly-digest backend (stage 08).

Verifies the two backend modules import cleanly and expose their public
symbols. handler.py reads AGENT_RUNTIME_ARN/CHECKPOINT_TABLE_NAME and builds
boto3 clients/resources at import time, so it is imported with those env
vars set and boto3.client/boto3.resource patched - no real AWS/network call
happens. notifications.py reads its config at import time but builds no
client, so it imports with no setup; notify() with no channels configured
is a silent no-op that touches no network.
"""

import importlib
import sys


def test_handler_module_imports_and_exposes_public_symbols(monkeypatch, mocker):
    monkeypatch.setenv(
        "AGENT_RUNTIME_ARN",
        "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-agent",
    )
    monkeypatch.setenv("CHECKPOINT_TABLE_NAME", "test-checkpoint-table")
    mocker.patch("boto3.client")
    mocker.patch("boto3.resource")

    sys.modules.pop("handler", None)
    handler_mod = importlib.import_module("handler")

    try:
        assert callable(handler_mod.handler)
        assert callable(handler_mod._current_run_key)
        assert callable(handler_mod._claim_run)
        assert callable(handler_mod._invoke_agent)
    finally:
        sys.modules.pop("handler", None)


def test_current_run_key_has_expected_shape(monkeypatch, mocker):
    monkeypatch.setenv(
        "AGENT_RUNTIME_ARN",
        "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-agent",
    )
    monkeypatch.setenv("CHECKPOINT_TABLE_NAME", "test-checkpoint-table")
    mocker.patch("boto3.client")
    mocker.patch("boto3.resource")

    sys.modules.pop("handler", None)
    handler_mod = importlib.import_module("handler")

    try:
        run_key = handler_mod._current_run_key()
        # e.g. "2026-W35": <4-digit year>-W<2-digit week>
        assert len(run_key) == 8
        assert run_key[4:6] == "-W"
        assert run_key[:4].isdigit()
        assert run_key[6:].isdigit()
    finally:
        sys.modules.pop("handler", None)


def test_notifications_module_imports_and_notify_is_safe_noop(mocker, monkeypatch):
    import notifications

    monkeypatch.setattr(notifications, "TELEGRAM_BOT_TOKEN", None)
    monkeypatch.setattr(notifications, "TELEGRAM_CHAT_ID", None)
    monkeypatch.setattr(notifications, "DISCORD_WEBHOOK_URL", None)
    urlopen_mock = mocker.patch("urllib.request.urlopen")

    assert callable(notifications.notify)
    notifications.notify("smoke")  # no channels configured -> silent no-op

    urlopen_mock.assert_not_called()
