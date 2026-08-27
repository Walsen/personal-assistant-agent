"""Personal assistant agent definition."""

import logging

from strands import Agent
from strands.models.bedrock import BedrockModel

from .logging_config import configure_logging
from .tools import ALL_TOOLS

configure_logging()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a personal assistant AI agent with access to the user's 
Gmail, Google Calendar, and Google Docs. You can:
- Read and send emails
- View and create calendar events  
- Search for Google Docs by name (or list the most recently modified ones), read their content, create new documents, append text to existing ones, and find/replace text within them

When the user asks about a document without giving you its ID, use the search tool to find it first instead of asking them for the ID.

Always confirm before sending emails, creating events, or modifying an existing document (appending text or replacing text). Be concise and helpful.
When listing information, format it clearly for easy reading."""

bedrock_model = BedrockModel(
    model_id="global.anthropic.claude-sonnet-4-6",
    region_name="us-east-1",
    temperature=0.3,
)

agent = Agent(
    model=bedrock_model,
    system_prompt=SYSTEM_PROMPT,
    tools=ALL_TOOLS,
)


def run() -> None:
    """Entry point used by the CLI to start an interactive chatbot session.

    Reads user input from the terminal in a loop and forwards each message
    to the agent, which keeps conversation history for the duration of the
    session. Type "exit" or "quit" (or press Ctrl+D / Ctrl+C) to end the chat.
    """
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

        agent(user_input)
        print()


if __name__ == "__main__":
    run()
