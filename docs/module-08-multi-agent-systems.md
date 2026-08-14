# Module 8: Multi-Agent Systems — Building a Team of Specialized Agents

**Duration:** 45 minutes (optional advanced section)

---

## Overview

A single agent with 7 tools works well, but as complexity grows you hit limits: context gets crowded, the model struggles to pick the right tool, and you can't easily mix models optimized for different tasks. The solution: **multi-agent systems** — a team of specialized agents that collaborate.

Strands provides four patterns for multi-agent orchestration:

| Pattern | Execution | Path Determined By | Best For |
|---------|-----------|-------------------|----------|
| **Agents as Tools** | Nested (synchronous) | Orchestrator decides | Simple delegation |
| **Graph** | Controlled + dynamic | Developer edges + LLM at each node | Conditional workflows |
| **Swarm** | Autonomous handoffs | Agents decide collaboratively | Emergent collaboration |
| **Workflow** | Deterministic DAG | Fixed dependency graph | Repeatable pipelines |

---

## 8.1 Agents as Tools — The Simplest Pattern (10 min)

The easiest way to build a multi-agent system: pass one agent directly as a tool to another.

### Concept

```
┌─────────────────────────────────────────────────┐
│ Orchestrator Agent                               │
│ tools = [email_agent, calendar_agent, docs_agent]│
│                                                  │
│ "Read my emails and schedule follow-ups"         │
│    ├── calls email_agent("read unread emails")   │
│    ├── calls calendar_agent("create meeting...")  │
│    └── responds to user                          │
└─────────────────────────────────────────────────┘
```

### Implementation

```python
from strands import Agent
from strands.models.bedrock import BedrockModel
from tools.gmail_tools import read_emails, send_email
from tools.calendar_tools import list_events, create_event
from tools.docs_tools import create_document, get_document, update_document

# Specialist agents (each focused on one domain)
email_agent = Agent(
    name="email_agent",
    description="Handles all email operations: reading, searching, and sending emails via Gmail.",
    system_prompt="You are an email specialist. Read and send emails efficiently.",
    tools=[read_emails, send_email],
)

calendar_agent = Agent(
    name="calendar_agent",
    description="Manages calendar: views upcoming events and creates new ones.",
    system_prompt="You are a calendar specialist. Manage events precisely with correct ISO timestamps.",
    tools=[list_events, create_event],
)

docs_agent = Agent(
    name="docs_agent",
    description="Creates, reads, and updates Google Docs documents.",
    system_prompt="You are a document specialist. Create well-structured documents.",
    tools=[create_document, get_document, update_document],
)

# Orchestrator: delegates to specialist agents
orchestrator = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    system_prompt="""You are a personal assistant orchestrator. You have three specialist agents:
- email_agent: for all Gmail operations
- calendar_agent: for calendar viewing and event creation  
- docs_agent: for Google Docs operations

Delegate tasks to the appropriate specialist. For complex requests, 
break them into sub-tasks and delegate each to the right agent.
Always confirm before sending emails or creating events.""",
    tools=[email_agent, calendar_agent, docs_agent],
)
```

### Benefits of Agents as Tools

- **Specialization** — Each agent has a focused system prompt and limited tools
- **Model mixing** — Use a cheap model (Haiku) for simple agents, expensive (Sonnet) for the orchestrator
- **Isolated context** — Each specialist only sees its own conversation, not the full history
- **Reusability** — Same specialist agent can be used in different orchestrators

### Cost Optimization with Model Mixing

```python
cheap_model = BedrockModel(model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0")
smart_model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

# Simple tasks → cheap model
email_agent = Agent(model=cheap_model, tools=[read_emails, send_email], ...)
calendar_agent = Agent(model=cheap_model, tools=[list_events, create_event], ...)

# Complex orchestration → smart model
orchestrator = Agent(model=smart_model, tools=[email_agent, calendar_agent, docs_agent])
```

---

## 8.2 Swarm — Autonomous Collaborative Team (15 min)

A **Swarm** is a pool of specialist agents that autonomously hand off tasks to each other. No fixed edges — agents decide the path collaboratively.

### Concept

```
┌─────────────────────────────────────────────┐
│ Swarm                                        │
│                                              │
│  Triage ──→ Email Expert ──→ Calendar Expert │
│    │                              │          │
│    └──→ Docs Expert ←─────────────┘          │
│                                              │
│  Agents hand off based on the task at hand   │
└─────────────────────────────────────────────┘
```

### Implementation

```python
from strands import Agent, Swarm
from strands.models.bedrock import BedrockModel

model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

# Define specialist agents with handoff awareness
triage_agent = Agent(
    name="triage",
    system_prompt="""You are a triage agent. Analyze the user's request and hand off to:
- 'email_expert' for anything related to emails
- 'calendar_expert' for scheduling and events
- 'docs_expert' for document creation/editing
If the task spans multiple domains, handle the first part and hand off the rest.""",
    model=model,
)

email_expert = Agent(
    name="email_expert",
    system_prompt="You are an email expert. Handle Gmail operations. Hand off to 'calendar_expert' if you need to schedule something based on email content.",
    model=model,
    tools=[read_emails, send_email],
)

calendar_expert = Agent(
    name="calendar_expert",
    system_prompt="You are a calendar expert. Manage events. Hand off to 'docs_expert' if meeting notes need to be created.",
    model=model,
    tools=[list_events, create_event],
)

docs_expert = Agent(
    name="docs_expert",
    system_prompt="You are a documents expert. Create and manage Google Docs.",
    model=model,
    tools=[create_document, get_document, update_document],
)

# Create the swarm
swarm = Swarm(
    agents=[triage_agent, email_expert, calendar_expert, docs_expert],
    start_agent="triage",
)

# Run the swarm
result = swarm("Read my unread emails, schedule follow-ups for urgent ones, and create meeting notes docs")
```

### When Swarm Shines

- **Emergent workflows** — The path isn't known in advance
- **Complex multi-domain tasks** — "Read emails, schedule meetings, write summaries"
- **Collaborative problem-solving** — One agent's output informs the next agent's actions

### Swarm vs. Agents-as-Tools

| | Agents as Tools | Swarm |
|---|----------------|-------|
| Control | Orchestrator decides | Agents decide |
| Path | Top-down delegation | Peer-to-peer handoffs |
| Cycles | No (tree-shaped) | Yes (agents can hand back) |
| Context | Each agent is isolated | Shared context across handoffs |
| Best for | Clear hierarchy | Emergent collaboration |

---

## 8.3 Graph — Structured Flow with Dynamic Routing (10 min)

A **Graph** is a developer-defined flowchart where nodes are agents and edges are transitions. An LLM at each node decides which edge to follow.

### Concept

```
┌──────────┐     ┌──────────────┐     ┌─────────────┐
│  Intake  │────→│  Categorize  │──┬─→│ Email Path  │
└──────────┘     └──────────────┘  │  └─────────────┘
                                    │  ┌─────────────┐
                                    ├─→│Calendar Path│
                                    │  └─────────────┘
                                    │  ┌─────────────┐
                                    └─→│  Docs Path  │
                                       └─────────────┘
```

### Implementation

```python
from strands import Agent, Graph

model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

# Define node agents
intake = Agent(
    id="intake",
    system_prompt="Greet the user and understand their request. Summarize what they need.",
    model=model,
)

email_handler = Agent(
    id="email_handler",
    system_prompt="Handle email operations based on the user's request.",
    model=model,
    tools=[read_emails, send_email],
)

calendar_handler = Agent(
    id="calendar_handler",
    system_prompt="Handle calendar operations based on the user's request.",
    model=model,
    tools=[list_events, create_event],
)

docs_handler = Agent(
    id="docs_handler",
    system_prompt="Handle document operations based on the user's request.",
    model=model,
    tools=[create_document, get_document, update_document],
)

# Define the graph with conditional routing
graph = Graph(
    nodes=[intake, email_handler, calendar_handler, docs_handler],
    edges=[
        ("intake", "email_handler"),      # Can route to email
        ("intake", "calendar_handler"),   # Can route to calendar
        ("intake", "docs_handler"),       # Can route to docs
    ],
)

result = graph("I need to check my emails and create a meeting")
```

### When Graph Shines

- **Business processes** with clear steps and conditional branches
- **Error handling** — Define explicit error edges
- **Approval workflows** — Route to human review nodes
- **Deterministic + flexible** — You define the possible paths, the model picks

---

## 8.4 Workflow — Deterministic Parallel Pipelines (10 min)

A **Workflow** is a fixed dependency graph (DAG) that executes as a single tool call. Independent tasks run in parallel.

### Concept

```
┌─────────────┐     ┌──────────────┐
│ Read Emails │──┐  │ List Events  │──┐
└─────────────┘  │  └──────────────┘  │    ┌──────────────────┐
                 └────────────────────┴───→│ Create Summary   │
                                           │ Doc (depends on  │
                                           │ both outputs)    │
                                           └──────────────────┘
```

### Implementation

```python
from strands import Agent
from strands.multi_agent import Workflow

# Define a workflow as a tool the orchestrator can invoke
workflow = Workflow(
    name="daily_digest",
    description="Generate a daily digest: read emails + check calendar → create summary doc",
    tasks=[
        {
            "id": "fetch_emails",
            "agent": email_agent,
            "prompt": "Read the 10 most recent unread emails and summarize key items",
        },
        {
            "id": "fetch_calendar",
            "agent": calendar_agent,
            "prompt": "List all events for the next 3 days",
        },
        {
            "id": "create_digest",
            "agent": docs_agent,
            "prompt": "Create a Google Doc titled 'Daily Digest' with email summaries and upcoming events",
            "depends_on": ["fetch_emails", "fetch_calendar"],  # Runs after both complete
        },
    ],
)

# The orchestrator can trigger workflows
orchestrator = Agent(
    system_prompt="You are a personal assistant. Use the daily_digest workflow for morning briefings.",
    tools=[workflow, email_agent, calendar_agent, docs_agent],
)

orchestrator("Give me my morning briefing")
```

### When Workflow Shines

- **Repeatable pipelines** — Same steps every time (daily reports, onboarding)
- **Parallel execution** — Independent tasks run concurrently
- **Single action** — Complex multi-step process wrapped as one tool

---

## 8.5 Choosing the Right Pattern

### Decision Tree

```
Is the execution path known in advance?
├── YES → Is it repeatable with parallel steps?
│         ├── YES → Workflow
│         └── NO  → Graph (with conditional edges)
└── NO  → Do you want a single orchestrator in control?
          ├── YES → Agents as Tools
          └── NO  → Swarm (peer-to-peer handoffs)
```

### Pattern Comparison

| Criteria | Agents as Tools | Graph | Swarm | Workflow |
|----------|----------------|-------|-------|----------|
| Complexity to set up | Low | Medium | Medium | Low |
| Flexibility | Medium | High | Very High | Low |
| Predictability | High | Medium | Low | Very High |
| Parallelism | No | No | No | Yes |
| Cycles allowed | No | Yes | Yes | No |
| Error handling | Orchestrator | Edge-based | Agent-driven | Task fails → halt |
| Best model usage | Mix models per agent | Same or mixed | Same or mixed | Mixed per task |

---

## 8.6 Hands-On: Build a Multi-Agent Personal Assistant Team

### Exercise: Agents-as-Tools Orchestrator

Create `agent_team.py`:

```python
from strands import Agent
from strands.models.bedrock import BedrockModel
from tools.gmail_tools import read_emails, send_email
from tools.calendar_tools import list_events, create_event
from tools.docs_tools import create_document, get_document, update_document

haiku = BedrockModel(model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0")
sonnet = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

# Specialist agents (cheap model — they do focused tasks)
email_agent = Agent(
    name="email_agent",
    description="Read and send emails via Gmail. Use for any email-related task.",
    system_prompt="You handle Gmail operations. Be concise in your responses.",
    model=haiku,
    tools=[read_emails, send_email],
)

calendar_agent = Agent(
    name="calendar_agent",
    description="View and create Google Calendar events. Use for scheduling.",
    system_prompt="You manage the calendar. Use ISO 8601 timestamps. Be precise.",
    model=haiku,
    tools=[list_events, create_event],
)

docs_agent = Agent(
    name="docs_agent",
    description="Create, read, and edit Google Docs. Use for documentation tasks.",
    system_prompt="You manage Google Docs. Create well-structured content.",
    model=haiku,
    tools=[create_document, get_document, update_document],
)

# Orchestrator (smart model — it reasons about delegation)
orchestrator = Agent(
    model=sonnet,
    system_prompt="""You are a personal assistant team leader. You have three specialists:
- email_agent: Gmail operations (read, search, send)
- calendar_agent: Calendar (view events, create meetings)
- docs_agent: Google Docs (create, read, update documents)

For complex requests, break them into sub-tasks and delegate each part.
Always confirm before sending emails or creating events.
Synthesize results from multiple agents into a coherent response.""",
    tools=[email_agent, calendar_agent, docs_agent],
)


def main():
    print("🤖 Multi-Agent Personal Assistant Team")
    print("Specialists: Email, Calendar, Docs")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ("exit", "quit"):
            break
        response = orchestrator(user_input)
        print(f"\nAssistant: {response.message}\n")


if __name__ == "__main__":
    main()
```

### Test Scenarios for Multi-Agent

Try these complex, multi-domain requests:

```
You: Read my unread emails and create a Google Doc summarizing the important ones

You: Check my calendar for this week, then send an email to team@company.com with the schedule

You: Find emails about the project deadline, create a calendar event for it, and draft a meeting agenda doc

You: Give me a morning briefing - emails, today's schedule, and save it all in a doc
```

Watch how the orchestrator breaks down complex requests and delegates to the right specialist.

---

## Key Takeaways

1. **Agents as Tools** is the simplest multi-agent pattern — just pass agents in the `tools` list
2. **Swarm** enables emergent collaboration via autonomous handoffs
3. **Graph** gives structured flows with conditional branching decided by the model
4. **Workflow** wraps repeatable pipelines as a single deterministic tool
5. **Model mixing** saves cost: cheap models for specialists, smart models for orchestrators
6. **Shared state** passes configuration across all agents without polluting prompts

---

## Resources

- [Multi-Agent Patterns Overview](https://strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/)
- [Agents as Tools](https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/)
- [Swarm Pattern](https://strandsagents.com/docs/user-guide/concepts/multi-agent/swarm/)
- [Graph Pattern](https://strandsagents.com/docs/user-guide/concepts/multi-agent/graph/)
- [Workflow Pattern](https://strandsagents.com/docs/user-guide/concepts/multi-agent/workflow/)
- [Agent-to-Agent (A2A) Protocol](https://strandsagents.com/docs/user-guide/concepts/multi-agent/agent-to-agent/)
