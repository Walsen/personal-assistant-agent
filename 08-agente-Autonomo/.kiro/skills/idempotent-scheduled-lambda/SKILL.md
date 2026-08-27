---
name: idempotent-scheduled-lambda
description: Use when adding a new scheduled/autonomous task (beyond the existing weekly digest) that invokes the agent unattended and needs to be safe against duplicate/retried triggers. Covers the DynamoDB conditional-put checkpoint pattern used by the weekly digest handler.
---

# Idempotent scheduled Lambda pattern

## Goal

Add a new EventBridge Scheduler-triggered Lambda that invokes the agent
autonomously, safe against the scheduler or Lambda itself retrying a
trigger (which would otherwise double-run the task, e.g. appending the
same digest section twice).

## The core pattern (see `backend/handler.py`)

1. **Derive a deterministic run key from time, not a random ID** - so a
   retry of "the same logical run" produces the same key and can be
   detected as a duplicate:
   ```python
   def _current_run_key() -> str:
       iso = datetime.datetime.now(datetime.timezone.utc).isocalendar()
       return f"{iso.year}-W{iso.week:02d}"   # one key per ISO week
   ```
   Adjust the granularity to the task's own schedule (daily task -> date
   string; monthly -> year-month string).

2. **Claim the run key with a conditional DynamoDB put** before doing
   anything else - this is an atomic "only I get to proceed" check:
   ```python
   try:
       table.put_item(
           Item={"run_key": run_key, "status": "in_progress", ...},
           ConditionExpression="attribute_not_exists(run_key)",
       )
       return True   # this invocation claimed it, proceed
   except ClientError as e:
       if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
           return False   # already claimed/completed, skip
       raise   # any other DynamoDB error should propagate, not be swallowed
   ```
   If the claim fails (already claimed), the handler should return early
   with `{"status": "skipped", ...}` rather than proceeding - never invoke
   the agent twice for the same run key.

3. **Finalize the run's outcome** (completed/failed/blocked_on_interrupt)
   with a follow-up `update_item` after the actual work, so the
   checkpoint table doubles as an audit log, not just a lock:
   ```python
   table.update_item(
       Key={"run_key": run_key},
       UpdateExpression="SET #s = :status, detail = :detail, finished_at = :finished_at",
       ExpressionAttributeNames={"#s": "status"},
       ExpressionAttributeValues={...},
   )
   ```

4. **Set a TTL on checkpoint items** (this repo uses ~90 days) so the
   table doesn't grow unbounded - add a `ttl` attribute (epoch seconds)
   and enable DynamoDB TTL on that attribute in the CDK stack.

5. **Fail the Lambda invocation on purpose** when the agent hits something
   it can't handle unattended (e.g. `result.get("status") == "interrupt"`)
   - raise rather than swallowing, so CloudWatch's `Errors` metric reflects
   reality and an alarm (if added later) fires. A scheduled task silently
   returning "success" when it actually stalled is worse than a visible
   failure.

## CDK wiring checklist (new stack, or new resource in an existing one)

- Lambda function pointed at `Code.from_asset("../backend")` (or wherever
  the handler lives) - no pip install step, stdlib/boto3-only dependencies
  unless you add a build step.
- DynamoDB table with a `run_key` (String) partition key, TTL enabled on
  the `ttl` attribute, `RemovalPolicy.DESTROY` for a demo/step-scoped
  stack (matches this repo's pattern of fully reversible per-step stacks).
- EventBridge Scheduler rule with the desired `scheduleExpression`
  (`rate(...)` or `cron(...)`), targeting the Lambda, with a retry policy
  - remember retries are exactly the thing this idempotency pattern
    protects against, don't disable retries as a substitute for the
    checkpoint.
- Lambda execution role: least privilege - only `dynamodb:PutItem`/
  `UpdateItem`/`GetItem` on the specific table ARN, plus whatever the task
  itself needs (e.g. `bedrock-agentcore:InvokeAgentRuntime` scoped to the
  one runtime ARN, following step 07/08's existing pattern).

## Testing

Mock `boto3.resource("dynamodb")` and `boto3.client(...)` entirely - never
let a test touch real AWS. Cover: claim succeeds when key doesn't exist;
claim fails (returns False) when `ConditionalCheckFailedException` is
raised; claim re-raises other `ClientError`s; the full handler flow for
each outcome (skipped/completed/failed/blocked_on_interrupt), asserting
the right finalize status and notification (if wired) for each. See
`08-agente-Autonomo/tests/test_handler.py` for the reference shape.
