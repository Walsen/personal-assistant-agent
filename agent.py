"""Personal Assistant AI Agent — Local interactive mode."""

from strands import Agent
from strands.models.bedrock import BedrockModel
from tools.gmail_tools import read_emails, send_email
from tools.calendar_tools import list_events, create_event
from tools.docs_tools import create_document, get_document, update_document

SYSTEM_PROMPT = """You are a personal assistant AI agent with access to the user's 
Gmail, Google Calendar, and Google Docs. You can:
- Read and send emails
- View and create calendar events  
- Create, read, and update Google Docs

Always confirm before sending emails or creating events. Be concise and helpful.
When listing information, format it clearly for easy reading."""

model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[read_emails, send_email, list_events, create_event,
           create_document, get_document, update_document]
)


def main():
    """Run the agent in interactive mode."""
    print("🤖 Personal Assistant Agent")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        response = agent(user_input)
        print(f"\nAssistant: {response.message}\n")


if __name__ == "__main__":
    main()
