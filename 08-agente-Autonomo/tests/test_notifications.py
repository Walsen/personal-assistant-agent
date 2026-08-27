"""Tests for backend/notifications.py.

notifications.py reads its config (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
DISCORD_WEBHOOK_URL) from os.environ at *import* time, into module-level
constants. To exercise different configurations we patch those module-level
constants directly via monkeypatch.setattr(notifications, "X", ...) rather
than mutating the environment after import - the module is already loaded
by the time these tests run, so env vars alone would have no effect.
"""

import urllib.error

import pytest

import notifications


@pytest.fixture(autouse=True)
def _clear_channels(monkeypatch):
    """Every test starts with all notification channels disabled, then
    opts individual channels back in as needed."""
    monkeypatch.setattr(notifications, "TELEGRAM_BOT_TOKEN", None)
    monkeypatch.setattr(notifications, "TELEGRAM_CHAT_ID", None)
    monkeypatch.setattr(notifications, "DISCORD_WEBHOOK_URL", None)


def test_notify_is_silent_noop_when_no_channels_configured(mocker):
    urlopen_mock = mocker.patch("urllib.request.urlopen")

    notifications.notify("hello")

    urlopen_mock.assert_not_called()


def test_notify_calls_telegram_sendmessage_when_configured(mocker, monkeypatch):
    monkeypatch.setattr(notifications, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(notifications, "TELEGRAM_CHAT_ID", "12345")
    urlopen_mock = mocker.patch("urllib.request.urlopen")
    urlopen_mock.return_value.__enter__.return_value.status = 200

    notifications.notify("hello telegram")

    urlopen_mock.assert_called_once()
    request = urlopen_mock.call_args[0][0]
    assert request.full_url == "https://api.telegram.org/bot test-token/sendMessage".replace(" ", "")
    body = request.data.decode("utf-8")
    assert '"chat_id": "12345"' in body
    assert '"text": "hello telegram"' in body


def test_notify_calls_discord_webhook_when_configured(mocker, monkeypatch):
    monkeypatch.setattr(
        notifications, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/abc/def"
    )
    urlopen_mock = mocker.patch("urllib.request.urlopen")
    urlopen_mock.return_value.__enter__.return_value.status = 204

    notifications.notify("hello discord")

    urlopen_mock.assert_called_once()
    request = urlopen_mock.call_args[0][0]
    assert request.full_url == "https://discord.com/api/webhooks/abc/def"
    body = request.data.decode("utf-8")
    assert '"content": "hello discord"' in body


def test_notify_calls_both_channels_when_both_configured(mocker, monkeypatch):
    monkeypatch.setattr(notifications, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(notifications, "TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr(
        notifications, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/abc/def"
    )
    urlopen_mock = mocker.patch("urllib.request.urlopen")
    urlopen_mock.return_value.__enter__.return_value.status = 200

    notifications.notify("hello everyone")

    assert urlopen_mock.call_count == 2


def test_notify_truncates_telegram_message_to_max_length(mocker, monkeypatch):
    monkeypatch.setattr(notifications, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(notifications, "TELEGRAM_CHAT_ID", "12345")
    urlopen_mock = mocker.patch("urllib.request.urlopen")
    urlopen_mock.return_value.__enter__.return_value.status = 200
    long_message = "x" * 5000

    notifications.notify(long_message)

    request = urlopen_mock.call_args[0][0]
    import json

    payload = json.loads(request.data.decode("utf-8"))
    assert len(payload["text"]) == 4096


def test_notify_truncates_discord_message_to_max_length(mocker, monkeypatch):
    monkeypatch.setattr(
        notifications, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/abc/def"
    )
    urlopen_mock = mocker.patch("urllib.request.urlopen")
    urlopen_mock.return_value.__enter__.return_value.status = 204
    long_message = "y" * 3000

    notifications.notify(long_message)

    request = urlopen_mock.call_args[0][0]
    import json

    payload = json.loads(request.data.decode("utf-8"))
    assert len(payload["content"]) == 2000


def test_notify_swallows_http_error(mocker, monkeypatch):
    monkeypatch.setattr(notifications, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(notifications, "TELEGRAM_CHAT_ID", "12345")
    error = urllib.error.HTTPError(
        url="https://api.telegram.org/bottest-token/sendMessage",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=None,
    )
    mocker.patch.object(error, "read", return_value=b"unauthorized")
    mocker.patch("urllib.request.urlopen", side_effect=error)

    notifications.notify("hello")  # must not raise


def test_notify_swallows_url_error(mocker, monkeypatch):
    monkeypatch.setattr(
        notifications, "DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/abc/def"
    )
    mocker.patch(
        "urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")
    )

    notifications.notify("hello")  # must not raise


def test_notify_swallows_generic_exception(mocker, monkeypatch):
    monkeypatch.setattr(notifications, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(notifications, "TELEGRAM_CHAT_ID", "12345")
    mocker.patch("urllib.request.urlopen", side_effect=RuntimeError("boom"))

    notifications.notify("hello")  # must not raise
