"""Steering handler enforcing confirmation before moderate-risk write actions.

Unlike delete_email (which uses a hard Interrupt requiring a synchronous
human response before the tool can even run), send_email and create_event
use steering: the first attempt to call either tool is deterministically
blocked with guidance telling the model to summarize the action and ask the
user to confirm. Only once the model retries the exact same tool call (which
it is expected to do after the user replies affirmatively in a later
message) does the call proceed.

This turns "always confirm before sending emails / creating events" from a
system-prompt suggestion the model could ignore into a rule enforced in
code.
"""

import json
import logging
from typing import Any

from strands.hooks import BeforeToolCallEvent
from strands.vended_plugins.steering import Guide, Proceed, SteeringHandler, ToolSteeringAction

logger = logging.getLogger(__name__)

CONFIRMATION_REQUIRED_TOOLS = {"send_email", "create_event"}
_STATE_KEY = "confirmation_steering_guided_signatures"


def _signature(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Build a stable signature for a tool call so repeat attempts (after
    the user confirms) can be recognized as "the same" action."""
    return f"{tool_name}:{json.dumps(tool_input, sort_keys=True)}"


class ConfirmationSteeringHandler(SteeringHandler):
    """Requires the model to have already asked for (and be retrying after)
    user confirmation before send_email or create_event actually executes.
    """

    name = "confirmation-steering"

    async def steer_before_tool(
        self, *, agent, tool_use: BeforeToolCallEvent, **kwargs: Any
    ) -> ToolSteeringAction:
        tool_name = tool_use.get("name")
        if tool_name not in CONFIRMATION_REQUIRED_TOOLS:
            return Proceed(reason="Not a tool requiring confirmation")

        tool_input = tool_use.get("input", {}) or {}
        signature = _signature(tool_name, tool_input)

        guided_signatures: list[str] = agent.state.get(_STATE_KEY) or []

        if signature in guided_signatures:
            # The model already surfaced this exact action once and is
            # retrying it, which per the system prompt should only happen
            # after the user explicitly confirmed. Let it through, and drop
            # the signature so a future edit to the same fields requires a
            # fresh confirmation.
            agent.state.set(_STATE_KEY, [s for s in guided_signatures if s != signature])
            logger.info("steering=proceed | tool=%s | previously guided, allowing retry", tool_name)
            return Proceed(reason="User already confirmed this exact action")

        agent.state.set(_STATE_KEY, guided_signatures + [signature])
        logger.info("steering=guide | tool=%s | blocking until user confirms", tool_name)
        return Guide(
            reason=(
                f"Before calling {tool_name}, summarize exactly what this action will do "
                "(e.g. recipient/subject for an email, or title/time for an event) and ask "
                "the user to explicitly confirm. Do not call this tool again until the user "
                "has replied affirmatively in a new message."
            )
        )
