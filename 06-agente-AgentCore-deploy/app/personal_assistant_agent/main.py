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

from bedrock_agentcore import BedrockAgentCoreApp

from personal_assistant_agent.agent import build_agent

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
    """
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
