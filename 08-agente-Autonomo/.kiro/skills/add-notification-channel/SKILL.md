---
name: add-notification-channel
description: Use when setting up, verifying, or adding a new push notification channel (Telegram, Discord, or a new one) for the autonomous weekly digest Lambda in this personal assistant agent step. Covers credential setup, curl verification, and CDK deploy wiring.
---

# Add or verify a notification channel

## Goal

Get Telegram and/or Discord notifications working for the autonomous
digest Lambda (`08-agente-Autonomo/backend/notifications.py`), or add
support for a new channel following the same optional/independent/never-
raises pattern.

## Setting up an existing channel (Telegram or Discord)

**Telegram:**
1. Message [@BotFather](https://t.me/BotFather) with `/newbot`, follow the
   prompts (name, then a username ending in `bot`). Copy the HTTP API
   token it returns - this is `TELEGRAM_BOT_TOKEN`. Treat it like a
   password.
2. Message your new bot directly (search its username, hit Start / send
   any message) - required, Telegram won't expose a chat ID for a
   conversation that doesn't exist yet.
3. Fetch the chat ID: open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser, find
   `result[0].message.chat.id`. If `result` is empty, step 2 wasn't done
   or too much time passed - message the bot again and retry.

**Discord:**
1. Channel settings (or right-click the channel) -> Integrations ->
   Webhooks -> New webhook -> Copy Webhook URL. That's the entire
   credential (`DISCORD_WEBHOOK_URL`), no separate token/ID needed.

## Verify BEFORE deploying (isolates credential bugs from deploy bugs)

```bash
# Telegram
curl -s -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "<CHAT_ID>", "text": "test"}'
# "ok":true = success. "ok":false -> description tells you the exact problem.

# Discord
curl -s -X POST "<WEBHOOK_URL>" -H "Content-Type: application/json" \
  -d '{"content": "test"}'
# Empty body + HTTP 204 = success. Add -w "\nHTTP %{http_code}\n" to see the code.
```

## Deploy

Add whichever credentials you have to the CDK deploy command (any
combination, or none):
```bash
JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk deploy \
  -c agentRuntimeArn=<arn> \
  -c telegramBotToken=<token> -c telegramChatId=<chat-id> \
  -c discordWebhookUrl=<webhook-url> \
  --require-approval never
```
Or `just infra-deploy <arn> "" <token> <chat-id> <webhook-url>` via this
step's `Justfile` (see its recipe signature for exact arg order).

These are plaintext CDK context values on the command line, which most
shells record in history - use env var substitution
(`-c telegramBotToken=$MY_TOKEN`) or clear shell history afterward if that
matters on this machine.

## Verify end-to-end after deploy

```bash
aws lambda invoke --function-name <DigestFunctionName> --region us-east-1 \
  --cli-binary-format raw-in-base64-out /tmp/out.json && cat /tmp/out.json
```
A ✅/❌/⚠️-prefixed message should arrive on every configured channel
within seconds - this is a faster end-to-end check than waiting for the
weekly schedule.

## Adding a NEW channel (not Telegram/Discord)

Follow `notifications.py`'s existing shape exactly:
1. Read the new channel's own env var(s) at module level (e.g.
   `SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")`).
2. Add a `_send_<channel>(message: str) -> None` helper using stdlib
   `urllib` only - this directory has no pip install step for
   `backend/`, it's zipped as-is (see `Code.from_asset` in
   `infra/stacks/autonomous_stack.py`), so no `requests` or other
   third-party HTTP library.
3. In `notify()`, add a new `if <CHANNEL>_ENV_VAR: _send_<channel>(message); sent_anywhere = True`
   branch - channels must stay independent and optional, never required.
4. The new helper must NEVER raise - catch `HTTPError`/`URLError`/generic
   `Exception` and just log a warning, exactly like `_send_telegram`/
   `_send_discord` do. A broken notification channel must never fail the
   digest run itself.
5. Wire the new env var through `infra/app.py` (read via
   `app.node.try_get_context(...)`) and `infra/stacks/autonomous_stack.py`
   (add to the Lambda's environment only if provided - see the existing
   conditional pattern for the other two channels).
6. Add tests mirroring `tests/test_notifications.py`'s shape: silent no-op
   when unset, correct URL/body when set, truncation at the channel's
   message length limit, and all of `HTTPError`/`URLError`/generic
   exception being swallowed without raising.
