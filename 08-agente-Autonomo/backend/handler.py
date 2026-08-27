"""Lambda entrypoint for the autonomous weekly digest run.

Triggered on a schedule (EventBridge Scheduler, see
infra/stacks/autonomous_stack.py) instead of by a human typing a prompt.
Invokes the same already-deployed AgentCore Runtime agent from
06-agente-AgentCore-deploy - no separate "autonomous agent" exists, this is
the same agent given a fixed instruction instead of free-form chat input.

Why this is safe to run unattended
-----------------------------------
The agent's existing safety mechanisms (steering.py's confirmation gate on
send_email/create_event, and delete_email's hard Interrupt) already require
a synchronous human reply before those tools can execute. A scheduled
Lambda invocation has no human to reply, so if the model ever attempted one
of those tools it would simply stall in "interrupt" status or get
steering-blocked - it can never complete an irreversible action on its own.
This run is additionally instructed (see DEFAULT_PROMPT) to stick to
read-only tools (list_recent_emails, get_email) plus Google Docs tools that
are NOT gated by steering (search_docs, create_doc, append_to_doc), so it
writes its weekly summary into a running Google Doc instead of taking any
write action against email or the calendar.

Idempotency
-----------
EventBridge Scheduler and Lambda can both retry. A DynamoDB conditional put
"claims" the current run_key (e.g. "2026-W35") before invoking the agent,
so a retried/duplicate trigger for the same week is a no-op instead of
running (and appending to the digest doc) twice.

Observability
-------------
If the agent invocation raises, or comes back with status == "interrupt"
(meaning it tried to do something requiring human approval, which should
not happen given the prompt below, but is possible if the model
misinterprets the request), this handler raises so the Lambda invocation
shows as failed - that surfaces in the Lambda's CloudWatch Errors metric,
which is what an alarm would be wired to if one is added later.

Notifications
-------------
Since nobody is watching an unattended run happen, a short message is
pushed to Telegram and/or Discord (see notifications.py) on every outcome:
completion (with an excerpt of what the agent reported), failure, or a
stalled interrupt. This is the primary way you'd actually notice a
scheduled run misbehaved, short of proactively checking CloudWatch Logs.
Both channels are optional - see notifications.py and
infra/stacks/autonomous_stack.py for how to enable them.
"""

import datetime
import logging
import os

import boto3
from botocore.exceptions import ClientError

from notifications import notify

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]
CHECKPOINT_TABLE_NAME = os.environ["CHECKPOINT_TABLE_NAME"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
DIGEST_DOC_TITLE = os.environ.get("DIGEST_DOC_TITLE", "Weekly Assistant Digest")

DEFAULT_PROMPT = (
    "Run your weekly-billing-summary skill for the last 7 days. Then, use "
    f"search_docs to find a Google Doc named exactly '{DIGEST_DOC_TITLE}'. "
    "If it exists, call append_to_doc to add a new section to it, headed "
    "with today's date, containing the summary you just produced. If it "
    f"does not exist, call create_doc with that exact title ('{DIGEST_DOC_TITLE}') "
    "and add the first dated section with the summary. "
    "This is an unattended, scheduled run: do not send any emails, do not "
    "create any calendar events, and do not delete or archive anything as "
    "part of this task - only report."
)
PROMPT = os.environ.get("DIGEST_PROMPT", DEFAULT_PROMPT)

_bedrock_agentcore = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
_dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
_checkpoint_table = _dynamodb.Table(CHECKPOINT_TABLE_NAME)

# ~90 days, so old checkpoint items don't accumulate forever.
_CHECKPOINT_TTL_SECONDS = 90 * 24 * 60 * 60


def handler(event, context):
    """EventBridge Scheduler entrypoint. `event` carries no useful payload
    (the schedule doesn't pass one) - the run key is derived from the
    current date instead.
    """
    run_key = _current_run_key()

    if not _claim_run(run_key):
        logger.info("Run %s already claimed/completed - skipping.", run_key)
        return {"status": "skipped", "run_key": run_key, "reason": "already claimed"}

    session_id = f"autonomous-weekly-digest-{run_key}"
    logger.info("Starting autonomous run | run_key=%s session_id=%s", run_key, session_id)

    try:
        result = _invoke_agent(session_id)
    except Exception as e:
        logger.exception("Agent invocation failed for run %s", run_key)
        _finalize_run(run_key, status="failed", detail="invocation raised an exception")
        notify(
            f"❌ Weekly digest run {run_key} FAILED: agent invocation raised "
            f"{type(e).__name__}. Check CloudWatch Logs for details."
        )
        raise

    if result.get("status") == "interrupt":
        logger.warning(
            "Autonomous run %s hit an interrupt it cannot resolve unattended: %s",
            run_key,
            result.get("interrupts"),
        )
        _finalize_run(run_key, status="blocked_on_interrupt", detail=str(result.get("interrupts")))
        notify(
            f"⚠️ Weekly digest run {run_key} stalled: the agent tried to do something "
            "requiring human confirmation, which an unattended run can't resolve. "
            "Check CloudWatch Logs for details."
        )
        raise RuntimeError(
            f"Run {run_key} stalled on an interrupt requiring human approval - "
            "see CloudWatch logs for details."
        )

    excerpt = _extract_text(result)[:500]
    _finalize_run(run_key, status="completed", detail=excerpt)
    logger.info("Autonomous run %s completed.", run_key)
    notify(f"✅ Weekly digest run {run_key} completed:\n\n{excerpt}")
    return {"status": "completed", "run_key": run_key, "session_id": session_id}


def _current_run_key() -> str:
    """ISO year-week string, e.g. '2026-W35' - one run per calendar week."""
    iso = datetime.datetime.now(datetime.timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _claim_run(run_key: str) -> bool:
    """Atomically claim run_key via a conditional put. Returns True if this
    invocation is the one that claimed it (should proceed), False if
    another invocation already claimed/completed this run_key.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        _checkpoint_table.put_item(
            Item={
                "run_key": run_key,
                "status": "in_progress",
                "claimed_at": now.isoformat(),
                "ttl": int(now.timestamp()) + _CHECKPOINT_TTL_SECONDS,
            },
            ConditionExpression="attribute_not_exists(run_key)",
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def _finalize_run(run_key: str, status: str, detail: str) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    _checkpoint_table.update_item(
        Key={"run_key": run_key},
        UpdateExpression="SET #s = :status, detail = :detail, finished_at = :finished_at",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": status,
            ":detail": detail,
            ":finished_at": now.isoformat(),
        },
    )


def _invoke_agent(session_id: str) -> dict:
    import json

    response = _bedrock_agentcore.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=session_id,
        contentType="application/json",
        accept="application/json",
        payload=json.dumps({"prompt": PROMPT}).encode("utf-8"),
    )
    return json.loads(response["response"].read())


def _extract_text(result: dict) -> str:
    message = result.get("message") or {}
    content = message.get("content") or []
    return "\n".join(block.get("text", "") for block in content if block.get("text"))
