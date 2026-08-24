"""Shared logic for invoking the deployed AgentCore Runtime agent.

Used by both the Lambda handler (handler.py, deployed behind a Function URL
+ CloudFront) and the local dev server (local_server.py, for testing the
frontend against the real deployed agent without deploying anything).
"""

import json
import logging
import os
import uuid

import boto3

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Minimum length required by InvokeAgentRuntime's runtimeSessionId (33-256
# chars) - a bare uuid4 (36 chars) already satisfies this.
_MIN_SESSION_ID_LEN = 33


def new_session_id() -> str:
    return str(uuid.uuid4())


def invoke_agent(agent_runtime_arn: str, body: dict, client=None) -> dict:
    """Forward one chat turn to the deployed agent and return its response.

    `body` is the parsed JSON request from the browser: either
    {"prompt": "..."} or {"interrupt_responses": [...]}, plus an optional
    "session_id" to continue an existing conversation.
    """
    client = client or boto3.client("bedrock-agentcore", region_name=AWS_REGION)
    session_id = body.get("session_id") or new_session_id()

    if body.get("interrupt_responses"):
        payload = {"interrupt_responses": body["interrupt_responses"]}
    else:
        payload = {"prompt": body.get("prompt", "")}

    logger.info("Invoking agent runtime | session_id=%s has_prompt=%s", session_id, "prompt" in payload)

    response = client.invoke_agent_runtime(
        agentRuntimeArn=agent_runtime_arn,
        runtimeSessionId=session_id,
        contentType="application/json",
        accept="application/json",
        payload=json.dumps(payload).encode("utf-8"),
    )

    raw = response["response"].read()
    parsed = json.loads(raw)
    parsed["session_id"] = session_id
    return parsed
