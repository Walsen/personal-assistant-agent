# Module 1: Introduction to AI Agents & Strands SDK

**Duration:** 30 minutes

---

## 1.1 What is an AI Agent? (10 min)

### Chatbot vs. Agent

| | Chatbot | Agent |
|---|---------|-------|
| Capabilities | Text in → Text out | Text in → Actions + Text out |
| Tools | None | Can call external APIs, read files, execute code |
| Autonomy | Responds only | Decides what to do, executes, observes results |
| Loop | Single pass | Multi-step reasoning loop |

### The Agent Loop

```
User Request → Model Thinks → Selects Tool → Executes Tool → Observes Result → Thinks Again → ... → Final Response
```

The model autonomously decides:
1. **Which** tool to call (or none)
2. **What** parameters to pass
3. **When** to stop and respond to the user

### Real-World Use Cases
- Personal assistants (email, calendar, documents)
- Code generation and debugging agents
- Customer support with system access
- Research agents that search and synthesize
- DevOps agents that monitor and remediate

---

## 1.2 Strands Agents SDK Overview (20 min)

### What is Strands?

[Strands Agents](https://strandsagents.com/) is an **open-source Python SDK by AWS** for building AI agents with a model-driven approach.

- **GitHub:** https://github.com/strands-agents/sdk-python
- **PyPI:** `pip install strands-agents`
- **License:** Apache 2.0

### Core Pattern

```python
from strands import Agent

agent = Agent(
    model=model,           # Which LLM to use
    tools=[tool1, tool2],  # What the agent can do
    system_prompt="..."    # Who the agent is
)

# The agent handles everything else
response = agent("What are my unread emails?")
```

### The `@tool` Decorator

Custom tools are Python functions decorated with `@tool`. The SDK auto-generates the tool schema from:
- **Type hints** → parameter types and structure
- **Docstrings** → tool description and parameter descriptions

```python
from strands import tool

@tool
def greet(name: str) -> str:
    """Greet a person by name.
    
    Args:
        name: The name of the person to greet.
    """
    return f"Hello, {name}! Welcome to the workshop."
```

### Tool Sources

1. **Custom tools** — `@tool` decorated functions (what we'll build today)
2. **Community package** — `pip install strands-agents-tools` (30+ pre-built tools)
3. **MCP tools** — Connect to any Model Context Protocol server
4. **Agents as tools** — Nest agents inside other agents

### Supported Model Providers

- Amazon Bedrock (Claude, Nova, Llama, Mistral)
- Anthropic (direct API)
- OpenAI
- Google (Gemini)
- Ollama (local models)
- LiteLLM, SageMaker, and more

### Live Demo

```python
from strands import Agent, tool

@tool
def greet(name: str) -> str:
    """Greet a person by name."""
    return f"Hello, {name}! Welcome to the workshop."

agent = Agent(tools=[greet])
agent("Greet the workshop attendees")
```

---

## Key Takeaways

- Agents = Model + Tools + System Prompt
- Strands uses a model-driven approach (the model decides what to do)
- `@tool` decorator makes any Python function available to the agent
- Type hints and docstrings ARE the schema — no JSON boilerplate needed

---

## Resources

- [Strands Agents Documentation](https://strandsagents.com/)
- [Python Quickstart](https://strandsagents.com/docs/user-guide/quickstart/python/)
- [Tools Overview](https://strandsagents.com/docs/user-guide/concepts/tools/)
- [Community Tools Package](https://github.com/strands-agents/tools)
