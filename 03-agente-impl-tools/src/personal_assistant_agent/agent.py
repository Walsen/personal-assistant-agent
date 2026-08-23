"""Personal assistant agent definition."""

from strands import Agent
from strands.models.bedrock import BedrockModel

from .tools import ALL_TOOLS

SYSTEM_PROMPT = """You are a personal assistant AI agent with access to the user's 
Gmail, Google Calendar, and Google Docs. You can:
- Read and send emails
- View and create calendar events  
- Create, read, and update Google Docs

Always confirm before sending emails or creating events. Be concise and helpful.
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
    """Entry point used by the CLI to start an interactive agent session."""
    agent("List my 10 most recent emails.")


if __name__ == "__main__":
    run()
