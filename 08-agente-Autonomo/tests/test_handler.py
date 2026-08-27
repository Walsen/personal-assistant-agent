"""Tests for backend/handler.py.

handler.py creates its boto3 clients/resource (bedrock-agentcore client,
DynamoDB resource+Table) as module-level globals at *import* time, and
reads AGENT_RUNTIME_ARN/CHECKPOINT_TABLE_NAME from os.environ at import
time too. To test it safely (no real AWS calls) we:
  1. Set the required env vars via monkeypatch.setenv.
  2. Patch boto3.client/boto3.resource *before* importing the module, so
     the module-level globals end up bound to our mocks.
  3. (Re)import the module fresh via importlib, since a previous test may
     have already imported/cached it with different mocks.
  4. Patch `notify` on the imported module (it's imported into handler.py
     via `from notifications import notify`, so it lives as a name on the
     handler module, not on the notifications module).
"""

import datetime as real_datetime
import importlib
import sys

import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def handler_module(monkeypatch, mocker):
    monkeypatch.setenv(
        "AGENT_RUNTIME_ARN",
        "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-agent",
    )
    monkeypatch.setenv("CHECKPOINT_TABLE_NAME", "test-checkpoint-table")

    mock_bedrock_client = mocker.MagicMock(name="bedrock_agentcore_client")
    mock_table = mocker.MagicMock(name="checkpoint_table")
    mock_dynamodb_resource = mocker.MagicMock(name="dynamodb_resource")
    mock_dynamodb_resource.Table.return_value = mock_table

    mocker.patch("boto3.client", return_value=mock_bedrock_client)
    mocker.patch("boto3.resource", return_value=mock_dynamodb_resource)

    sys.modules.pop("handler", None)
    module = importlib.import_module("handler")

    mocker.patch.object(module, "notify")

    yield module

    sys.modules.pop("handler", None)


def _client_error(code: str) -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": "boom"}},
        operation_name="PutItem",
    )


# --- _current_run_key ------------------------------------------------------


def test_current_run_key_returns_iso_year_week(handler_module, mocker):
    fake_now = real_datetime.datetime(2026, 8, 27, tzinfo=real_datetime.timezone.utc)
    mock_datetime = mocker.patch.object(handler_module, "datetime")
    mock_datetime.datetime.now.return_value = fake_now
    mock_datetime.timezone.utc = real_datetime.timezone.utc

    result = handler_module._current_run_key()

    assert result == "2026-W35"
    mock_datetime.datetime.now.assert_called_once_with(real_datetime.timezone.utc)


def test_current_run_key_pads_single_digit_week(handler_module, mocker):
    fake_now = real_datetime.datetime(2026, 1, 5, tzinfo=real_datetime.timezone.utc)
    mock_datetime = mocker.patch.object(handler_module, "datetime")
    mock_datetime.datetime.now.return_value = fake_now
    mock_datetime.timezone.utc = real_datetime.timezone.utc

    result = handler_module._current_run_key()

    assert result == "2026-W02"


# --- _claim_run -------------------------------------------------------------


def test_claim_run_returns_true_on_successful_conditional_put(handler_module):
    result = handler_module._claim_run("2026-W35")

    assert result is True
    handler_module._checkpoint_table.put_item.assert_called_once()
    _, kwargs = handler_module._checkpoint_table.put_item.call_args
    assert kwargs["Item"]["run_key"] == "2026-W35"
    assert kwargs["Item"]["status"] == "in_progress"
    assert kwargs["ConditionExpression"] == "attribute_not_exists(run_key)"


def test_claim_run_returns_false_on_conditional_check_failed(handler_module):
    handler_module._checkpoint_table.put_item.side_effect = _client_error(
        "ConditionalCheckFailedException"
    )

    result = handler_module._claim_run("2026-W35")

    assert result is False


def test_claim_run_reraises_other_client_errors(handler_module):
    handler_module._checkpoint_table.put_item.side_effect = _client_error(
        "ProvisionedThroughputExceededException"
    )

    with pytest.raises(ClientError):
        handler_module._claim_run("2026-W35")


# --- handler() full flow ----------------------------------------------------


def test_handler_skips_when_run_already_claimed(handler_module, mocker):
    mocker.patch.object(handler_module, "_claim_run", return_value=False)
    mocker.patch.object(handler_module, "_current_run_key", return_value="2026-W35")
    invoke_mock = mocker.patch.object(handler_module, "_invoke_agent")

    result = handler_module.handler({}, None)

    assert result == {
        "status": "skipped",
        "run_key": "2026-W35",
        "reason": "already claimed",
    }
    invoke_mock.assert_not_called()
    handler_module.notify.assert_not_called()


def test_handler_completes_and_notifies_on_success(handler_module, mocker):
    mocker.patch.object(handler_module, "_claim_run", return_value=True)
    mocker.patch.object(handler_module, "_current_run_key", return_value="2026-W35")
    finalize_mock = mocker.patch.object(handler_module, "_finalize_run")
    agent_response = {
        "message": {"content": [{"text": "Weekly digest done."}]},
    }
    mocker.patch.object(handler_module, "_invoke_agent", return_value=agent_response)

    result = handler_module.handler({}, None)

    assert result["status"] == "completed"
    assert result["run_key"] == "2026-W35"
    finalize_mock.assert_called_once()
    args, kwargs = finalize_mock.call_args
    assert args[0] == "2026-W35" or kwargs.get("run_key") == "2026-W35"
    assert kwargs.get("status") == "completed" or "completed" in args
    handler_module.notify.assert_called_once()
    notified_message = handler_module.notify.call_args[0][0]
    assert "✅" in notified_message


def test_handler_raises_and_notifies_on_interrupt(handler_module, mocker):
    mocker.patch.object(handler_module, "_claim_run", return_value=True)
    mocker.patch.object(handler_module, "_current_run_key", return_value="2026-W35")
    finalize_mock = mocker.patch.object(handler_module, "_finalize_run")
    agent_response = {"status": "interrupt", "interrupts": ["send_email confirmation"]}
    mocker.patch.object(handler_module, "_invoke_agent", return_value=agent_response)

    with pytest.raises(RuntimeError):
        handler_module.handler({}, None)

    finalize_mock.assert_called_once()
    _, kwargs = finalize_mock.call_args
    assert kwargs.get("status") == "blocked_on_interrupt"
    handler_module.notify.assert_called_once()
    notified_message = handler_module.notify.call_args[0][0]
    assert "⚠️" in notified_message


def test_handler_raises_and_notifies_on_agent_invocation_failure(handler_module, mocker):
    mocker.patch.object(handler_module, "_claim_run", return_value=True)
    mocker.patch.object(handler_module, "_current_run_key", return_value="2026-W35")
    finalize_mock = mocker.patch.object(handler_module, "_finalize_run")
    mocker.patch.object(
        handler_module, "_invoke_agent", side_effect=RuntimeError("agentcore boom")
    )

    with pytest.raises(RuntimeError, match="agentcore boom"):
        handler_module.handler({}, None)

    finalize_mock.assert_called_once()
    _, kwargs = finalize_mock.call_args
    assert kwargs.get("status") == "failed"
    handler_module.notify.assert_called_once()
    notified_message = handler_module.notify.call_args[0][0]
    assert "❌" in notified_message
