"""Personal assistant agent definition."""

import logging
import os
from pathlib import Path

from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.session import FileSessionManager
from strands.vended_plugins.skills import AgentSkills

from .logging_config import configure_logging
from .notes_agent import notes_tool
from .steering import ConfirmationSteeringHandler
from .tools import ALL_TOOLS

configure_logging()
logger = logging.getLogger(__name__)

# This file lives at app/personal_assistant_agent/personal_assistant_agent/agent.py
# (AgentCore CLI layout: codeLocation=app/personal_assistant_agent/). Two levels
# up is the agent's code root (app/personal_assistant_agent/), where skills/
# and main.py live alongside the personal_assistant_agent/ package.
AGENT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = AGENT_ROOT / "skills"
SESSIONS_DIR = AGENT_ROOT / ".sessions"

# AgentCore Runtime containers are ephemeral: the local filesystem is not a
# durable place to store session state, since a container can be replaced at
# any time. When running under AgentCore (or whenever AGENT_SESSIONS_BUCKET
# is set), sessions are persisted to S3 instead of the local .sessions/ dir
# used for local CLI development.
SESSIONS_BUCKET = os.environ.get("AGENT_SESSIONS_BUCKET")
SESSIONS_S3_PREFIX = os.environ.get("AGENT_SESSIONS_PREFIX", "personal-assistant-sessions")

SYSTEM_PROMPT = """You are a personal assistant AI agent with access to the user's 
Gmail, Google Calendar, and Google Docs. You can:
- Read and send emails
- View and create calendar events  
- Search for Google Docs by name (or list the most recently modified ones), read their content, create new documents, append text to existing ones, and find/replace text within them

When the user asks about a document without giving you its ID, use the search tool to find it first instead of asking them for the ID.

Always confirm before sending emails, creating events, or modifying an existing document (appending text or replacing text). Be concise and helpful.
When listing information, format it clearly for easy reading.

For inbox cleanup, prefer archive_email over delete_email since archiving is
reversible. delete_email requires the user's explicit in-terminal
confirmation before it executes and should only be used when the user has
clearly asked to delete (not just clean up or archive) a specific message.

You have access to specialized skills listed in <available_skills>. When a
user's request matches a skill's description, activate it with the `skills`
tool before proceeding, and follow its instructions.

For requests to take notes on, summarize into notes, or extract action items
from an email, document, or conversation, delegate the actual note
structuring to the notes_agent tool rather than doing it yourself. Pass it
the raw source text (e.g. from get_email or read_doc)."""

bedrock_model = BedrockModel(
    model_id="global.anthropic.claude-sonnet-4-6",
    region_name="us-east-1",
    temperature=0.3,
)

DEFAULT_SESSION_ID = "personal-assistant-cli"


def _build_session_manager(session_id: str):
    """Build the appropriate session manager for the current environment.

    Locally (no AGENT_SESSIONS_BUCKET set), sessions persist to disk under
    .sessions/, which survives CLI restarts on the same machine.

    When AGENT_SESSIONS_BUCKET is set (set this in the AgentCore Runtime
    deployment), sessions persist to S3 instead, since AgentCore Runtime
    containers are ephemeral and have no durable local disk.
    """
    if SESSIONS_BUCKET:
        from strands.session.s3_session_manager import S3SessionManager

        logger.info("Using S3SessionManager | bucket=%s prefix=%s", SESSIONS_BUCKET, SESSIONS_S3_PREFIX)
        return S3SessionManager(
            session_id=session_id,
            bucket=SESSIONS_BUCKET,
            prefix=SESSIONS_S3_PREFIX,
        )

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Using FileSessionManager | storage_dir=%s", SESSIONS_DIR)
    return FileSessionManager(session_id=session_id, storage_dir=str(SESSIONS_DIR))


def build_agent(session_id: str = DEFAULT_SESSION_ID) -> Agent:
    """Build a fresh Agent bound to the given session id.

    Each AgentCore Runtime invocation should build its own Agent scoped to
    the caller's session id, so that separate users/sessions don't share
    conversation history or steering/interrupt state.
    """
    session_manager = _build_session_manager(session_id)
    return Agent(
        model=bedrock_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[*ALL_TOOLS, notes_tool],
        plugins=[AgentSkills(skills=str(SKILLS_DIR)), ConfirmationSteeringHandler()],
        session_manager=session_manager,
    )


# Default agent instance used by the interactive CLI (run(), below). Built
# lazily (only when run() actually starts, not at module import time) so
# that importing this module - e.g. from main.py's `from .agent import
# build_agent` - never has a side effect of constructing an Agent or
# touching the session backend. AgentCore Runtime deployments build a
# separate per-session agent via build_agent() directly instead of using
# this shared instance - see main.py.
agent: Agent | None = None


def run() -> None:
    """Entry point used by the CLI to start an interactive chatbot session.

    Reads user input from the terminal in a loop and forwards each message
    to the agent, which keeps conversation history for the duration of the
    session. Type "exit" or "quit" (or press Ctrl+D / Ctrl+C) to end the chat.
    """
    global agent
    if agent is None:
        agent = build_agent(DEFAULT_SESSION_ID)

    print("Personal Assistant Agent - type 'exit' or 'quit' to end the session.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        result = agent(user_input)
        _resolve_interrupts(result)
        print()


def _resolve_interrupts(result) -> None:
    """Prompt the user in the terminal for any pending tool interrupts
    (e.g. delete_email confirmation) and resume the agent until it finishes.
    """
    while result.stop_reason == "interrupt":
        responses = []
        for interrupt in result.interrupts:
            logger.info("interrupt raised | name=%s reason=%s", interrupt.name, interrupt.reason)
            if interrupt.name == "gmail-delete-approval":
                reason = interrupt.reason or {}
                subject = reason.get("subject") or "(no subject)"
                sender = reason.get("sender") or "(unknown sender)"
                message_id = reason.get("message_id", "")
                prompt = (
                    f"\nConfirm deletion of email:\n"
                    f"  From: {sender}\n"
                    f"  Subject: {subject}\n"
                    f"  Message ID: {message_id}\n"
                    "Delete this email? (y/N): "
                )
                user_response = input(prompt).strip()
            else:
                user_response = input(f"\n{interrupt.name} requires input: ").strip()

            logger.info("interrupt resolved | name=%s response=%r", interrupt.name, user_response)
            responses.append(
                {"interruptResponse": {"interruptId": interrupt.id, "response": user_response}}
            )
        result = agent(responses)


if __name__ == "__main__":
    run()
