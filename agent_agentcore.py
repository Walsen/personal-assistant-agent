"""Personal Assistant AI Agent — AgentCore Runtime entrypoint."""

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models.bedrock import BedrockModel
from tools.gmail_tools import read_emails, send_email
from tools.calendar_tools import list_events, create_event
from tools.docs_tools import create_document, get_document, update_document

app = BedrockAgentCoreApp()

model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

agent = Agent(
    model=model,
    system_prompt="""You are a personal assistant AI agent with access to the user's 
Gmail, Google Calendar, and Google Docs. You can:
- Read and send emails
- View and create calendar events  
- Create, read, and update Google Docs

Always confirm before sending emails or creating events. Be concise and helpful.
When listing information, format it clearly for easy reading.""",
    tools=[read_emails, send_email, list_events, create_event,
           create_document, get_document, update_document]
)


@app.entrypoint
def invoke(payload):
    """Process user input and return agent response."""
    user_message = payload.get("prompt", "Hello")
    result = agent(user_message)
    return {"result": result.message}


if __name__ == "__main__":
    app.run()
