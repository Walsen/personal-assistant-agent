"""AgentCore Runtime entrypoint for the personal assistant agent.

Wraps the existing Strands agent (personal_assistant_agent/agent.py) as an
HTTP service using the Bedrock AgentCore Runtime Python SDK. This file is
what the AgentCore CLI (`agentcore deploy`) packages and runs in AWS - the
agent implementation itself is unchanged from earlier local-CLI steps.

Two things differ from a long-lived terminal chatbot loop, both because
AgentCore Runtime is a stateless HTTP request/response service instead of a
long-lived terminal process:

1. Session handling: each invocation is scoped to the caller's session id
   (from AgentCore Runtime's request context) via build_agent(session_id),
   so separate callers/sessions don't share conversation history or
   pending confirmations.

2. Interrupts: delete_email's confirmation can't block on a synchronous
   input() call here, since there is no terminal attached to an HTTP
   request. Instead, a pending interrupt is returned directly in the JSON
   response (see the "interrupt" response shape below), and the caller
   resumes it by sending a follow-up request containing
   interrupt_responses. The session manager (S3SessionManager when
   AGENT_SESSIONS_BUCKET is set - see agent.py) persists the pending
   interrupt between these two calls.

Request payload shape:
    {"prompt": "user message"}
    or, to resume a pending interrupt:
    {"interrupt_responses": [{"interrupt_id": "...", "response": "y"}]}

Response payload shape (normal completion):
    {"status": "completed", "message": <assistant message content>}

Response payload shape (pending confirmation):
    {
        "status": "interrupt",
        "interrupts": [{"id": "...", "name": "...", "reason": {...}}]
    }
"""

import logging

from bedrock_agentcore import BedrockAgentCoreApp

from personal_assistant_agent.agent import build_agent

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict, context) -> dict:
    """Process one AgentCore Runtime invocation.

    Args:
        payload: JSON body of the request (see module docstring for shape).
        context: AgentCore RequestContext, used here for its session_id.

    Returns:
        A JSON-serializable dict describing either a completed response or
        a pending interrupt the caller must resolve in a follow-up request.
        Malformed input (missing/wrong-typed prompt, malformed
        interrupt_responses) returns {"status": "error", "message": ...}
        instead of ever reaching build_agent()/the model - see
        _validate_payload().
    """
    error = _validate_payload(payload)
    if error:
        logger.warning("invoke rejected malformed payload | reason=%s", error)
        return {"status": "error", "message": error}

    session_id = context.session_id or "default"
    agent = build_agent(session_id)

    interrupt_responses = payload.get("interrupt_responses")
    if interrupt_responses:
        resume_payload = [
            {"interruptResponse": {"interruptId": r["interrupt_id"], "response": r["response"]}}
            for r in interrupt_responses
        ]
        result = agent(resume_payload)
    else:
        prompt = payload.get("prompt", "Hello! How can I help you today?")
        result = agent(prompt)

    return _format_response(result)


def _validate_payload(payload) -> str | None:
    """Validate a raw invocation payload before it reaches build_agent() or
    the model, per the "Invocation Input" invariant: runtime payloads must
    be validated and text prompts required to be strings.

    Returns:
        None if the payload is valid, otherwise a short human-readable
        message describing why it was rejected.
    """
    if not isinstance(payload, dict):
        return "Invalid request: payload must be a JSON object."

    if "prompt" in payload and not isinstance(payload["prompt"], str):
        return "Invalid request: 'prompt' must be a string."

    interrupt_responses = payload.get("interrupt_responses")
    if interrupt_responses is not None:
        if not isinstance(interrupt_responses, list):
            return "Invalid request: 'interrupt_responses' must be a list."
        for entry in interrupt_responses:
            if (
                not isinstance(entry, dict)
                or "interrupt_id" not in entry
                or "response" not in entry
            ):
                return (
                    "Invalid request: each entry in 'interrupt_responses' must be an "
                    "object with 'interrupt_id' and 'response'."
                )

    return None


def _format_response(result) -> dict:
    """Convert an AgentResult into the JSON response shape described in the
    module docstring, handling both normal completion and pending interrupts.
    """
    if result.stop_reason == "interrupt":
        return {
            "status": "interrupt",
            "interrupts": [
                {"id": i.id, "name": i.name, "reason": i.reason}
                for i in result.interrupts
            ],
        }

    return {"status": "completed", "message": result.message}


if __name__ == "__main__":
    app.run()
