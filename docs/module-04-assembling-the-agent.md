# Module 4: Assembling the Personal Assistant Agent

**Duration:** 30 minutes

---

## 4.1 System Prompt Design (10 min)

The system prompt defines **who** your agent is and **how** it behaves. It's the most important piece of agent configuration after the tools themselves.

### Our System Prompt

```python
SYSTEM_PROMPT = """You are a personal assistant AI agent with access to the user's 
Gmail, Google Calendar, and Google Docs. You can:
- Read and send emails
- View and create calendar events  
- Create, read, and update Google Docs

Always confirm before sending emails or creating events. Be concise and helpful.
When listing information, format it clearly for easy reading."""
```

### System Prompt Best Practices

| Do | Don't |
|----|-------|
| Define the agent's role clearly | Leave it vague ("you are helpful") |
| List what tools are available | Assume the model knows |
| Set boundaries ("confirm before sending") | Allow unrestricted actions |
| Specify output format preferences | Let formatting be random |
| Keep it concise | Write pages of instructions |

### Safety Considerations

For a personal assistant with real API access:
- **Always confirm** before sending emails or creating events
- **Never expose** raw credentials in responses
- **Limit scope** — don't give delete permissions unless needed
- **Log actions** — keep an audit trail of what the agent did

---

## 4.2 Wiring Tools to the Agent (10 min)

### The Complete Agent Definition

```python
from strands import Agent
from strands.models.bedrock import BedrockModel
from tools.gmail_tools import read_emails, send_email
from tools.calendar_tools import list_events, create_event
from tools.docs_tools import create_document, get_document, update_document

model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[read_emails, send_email, list_events, create_event,
           create_document, get_document, update_document]
)
```

### Model Selection

| Model | Best For | Cost |
|-------|----------|------|
| Claude Sonnet 4 | Production, complex reasoning | $$ |
| Claude Haiku 3.5 | Fast responses, simple tasks | $ |
| Nova Pro | AWS-native, good balance | $$ |
| Llama 3.1 70B | Open source, self-hosted | $ |

For this workshop, we use **Claude Sonnet** via Bedrock — best balance of tool-use accuracy and speed.

### How the Agent Decides Which Tool to Use

The model sees:
1. Your system prompt
2. The user's message
3. A JSON schema for each tool (auto-generated from `@tool` decorators)

It then reasons about which tool(s) to call, in what order, with what parameters.

---

## 4.3 Interactive Testing (10 min)

### Running the Agent

```bash
python agent.py
```

### Test Scenarios

Try these natural language requests:

**Gmail:**
```
You: What are my unread emails?
You: Show me emails from GitHub this week
You: Send an email to test@example.com saying "Hello from my AI agent"
```

**Calendar:**
```
You: What's on my calendar this week?
You: Create a meeting called "Team Standup" tomorrow at 9am for 30 minutes
You: Do I have anything scheduled for Friday?
```

**Google Docs:**
```
You: Create a new document called "Meeting Notes August 14"
You: Write a summary of my calendar for this week in a new Google Doc
```

**Multi-tool (the agent chains tools):**
```
You: Read my unread emails and create a Google Doc summarizing the important ones
You: Check my calendar for tomorrow and send me an email with the schedule
```

### Observing the Agent's Reasoning

Watch the console output — you'll see:
1. The model's reasoning about which tool to use
2. The tool call with parameters
3. The tool's response
4. The model's final answer to the user

---

## Key Takeaways

- The system prompt shapes agent behavior more than you'd expect
- Tool descriptions are critical — they're how the model decides what to call
- The model can chain multiple tools in a single turn
- Always add safety guardrails for tools with side effects

---

## Resources

- [Strands: Prompts](https://strandsagents.com/docs/user-guide/concepts/agents/prompts/)
- [Strands: Agent Loop](https://strandsagents.com/docs/user-guide/concepts/agents/agent-loop/)
- [Strands: Model Providers](https://strandsagents.com/docs/user-guide/concepts/model-providers/)
