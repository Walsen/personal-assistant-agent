"""Lambda handler that proxies web chat requests to the deployed AgentCore
Runtime agent (built in 06-agente-AgentCore-deploy).

This function does NOT reimplement the agent. It is a thin HTTP proxy: it
takes a browser-originated request, forwards it to the already-deployed
AgentCore Runtime via boto3's `invoke_agent_runtime` (see agent_client.py),
and relays the response back in the shape the frontend expects. This keeps
the agent runtime as the single source of truth and lets the web client and
the CLI (from step 06) hit the same deployed agent.

Exposed via a Lambda Function URL, fronted by CloudFront (see
infra/stacks/*), so the browser never talks to AWS APIs directly and never
needs AWS credentials. The Function URL itself has no IAM auth (it must
accept plain POST bodies from CloudFront, which ruled out CloudFront's
Origin Access Control for this origin - see the comment on
ORIGIN_VERIFY_HEADER in infra/stacks/web_interface_stack.py for why).
Instead, every request is required to carry a shared-secret header that
only the CloudFront distribution in this stack knows; requests missing or
failing that check are rejected before invoking the agent.

Request body (POST /chat), one of:
    {"prompt": "user message", "session_id": "<optional, omit on first turn>"}
    {"interrupt_responses": [{"interrupt_id": "...", "response": "y"}],
     "session_id": "<required - the session that raised the interrupt>"}

Response body mirrors what the agent's own main.py (step 06) returns, plus
the session_id the browser should send on the next turn:
    {"status": "completed", "message": {...}, "session_id": "..."}
    {"status": "interrupt", "interrupts": [...], "session_id": "..."}
    {"status": "error", "error": "..."}
"""

import json
import logging
import os

import boto3

from agent_client import invoke_agent

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
# Shared secret CloudFront injects as a custom origin header on every
# request it forwards here (see ORIGIN_VERIFY_HEADER in
# infra/stacks/web_interface_stack.py). Required in production; left
# optional so local invocation/testing of this handler doesn't need it.
ORIGIN_VERIFY_HEADER = "x-origin-verify"
ORIGIN_VERIFY_SECRET = os.environ.get("ORIGIN_VERIFY_SECRET")
# Comma-separated list of allowed browser origins for CORS. Set this to the
# CloudFront distribution's own domain once known (see infra/stacks/*.py).
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

_client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)


def handler(event, context):
    """Lambda Function URL entrypoint (API Gateway-style event shape)."""
    method = (event.get("requestContext", {}).get("http", {}) or {}).get("method", "POST")
    origin = _pick_origin(event)

    if method == "OPTIONS":
        return _response(204, "", origin)

    if ORIGIN_VERIFY_SECRET:
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        if headers.get(ORIGIN_VERIFY_HEADER) != ORIGIN_VERIFY_SECRET:
            logger.warning("Rejected request missing/invalid origin-verify header")
            return _response(403, {"status": "error", "error": "Forbidden"}, origin)

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError as e:
        return _response(400, {"status": "error", "error": f"Invalid JSON: {e}"}, origin)

    try:
        result = invoke_agent(AGENT_RUNTIME_ARN, body, client=_client)
    except Exception:
        logger.exception("Agent invocation failed")
        return _response(500, {"status": "error", "error": "Agent invocation failed. Check server logs."}, origin)

    return _response(200, result, origin)


def _pick_origin(event: dict) -> str:
    request_origin = (event.get("headers") or {}).get("origin", "")
    if "*" in ALLOWED_ORIGINS:
        return request_origin or "*"
    if request_origin in ALLOWED_ORIGINS:
        return request_origin
    return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else ""


def _response(status_code: int, body, origin: str) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        },
        "body": body if isinstance(body, str) else json.dumps(body),
    }
