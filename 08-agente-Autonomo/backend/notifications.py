"""Optional push notifications for autonomous run outcomes.

Sends a short message to Telegram and/or Discord whenever a scheduled
autonomous run (see handler.py) completes, fails, or stalls on an
interrupt it can't resolve unattended - so there's no need to go looking
in CloudWatch Logs to find out what an unattended run did while you
weren't watching.

Both channels are optional and independent: set the relevant environment
variables (via the CDK stack - see infra/stacks/autonomous_stack.py) to
enable a channel, leave them unset to skip it. If neither is configured,
notify() is a silent no-op and the digest run behaves exactly as it did
before this module existed - no new required configuration.

Uses only the standard library (urllib) - no extra dependencies to vendor
into the Lambda deployment package, since this backend/ directory is
zipped as-is with no pip install step (see Code.from_asset in the stack).
"""

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

_TELEGRAM_MAX_LEN = 4096
_DISCORD_MAX_LEN = 2000


def notify(message: str) -> None:
    """Best-effort push notification to every configured channel.

    Never raises: a notification failure (bad token, network blip, channel
    not configured, etc.) must not affect the digest run's own
    success/failure status, which is already tracked independently via the
    DynamoDB checkpoint and the Lambda's own return value/exception in
    handler.py. Losing a Telegram/Discord message is not worth failing an
    otherwise-successful digest run over.
    """
    sent_anywhere = False

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        _send_telegram(message)
        sent_anywhere = True

    if DISCORD_WEBHOOK_URL:
        _send_discord(message)
        sent_anywhere = True

    if not sent_anywhere:
        logger.info(
            "No notification channel configured (set TELEGRAM_BOT_TOKEN+TELEGRAM_CHAT_ID "
            "and/or DISCORD_WEBHOOK_URL to enable) - message not sent: %s",
            message[:100],
        )


def _send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = json.dumps(
        {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message[:_TELEGRAM_MAX_LEN],
        }
    ).encode("utf-8")
    _post_json(url, body, "Telegram")


def _send_discord(message: str) -> None:
    body = json.dumps({"content": message[:_DISCORD_MAX_LEN]}).encode("utf-8")
    _post_json(DISCORD_WEBHOOK_URL, body, "Discord")


def _post_json(url: str, body: bytes, channel_name: str) -> None:
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            logger.info("%s notification sent | status=%s", channel_name, response.status)
    except urllib.error.HTTPError as e:
        logger.warning(
            "%s notification failed | status=%s body=%s",
            channel_name,
            e.code,
            e.read()[:500],
        )
    except urllib.error.URLError as e:
        logger.warning("%s notification failed | reason=%s", channel_name, e.reason)
    except Exception:
        logger.exception("%s notification failed unexpectedly", channel_name)
