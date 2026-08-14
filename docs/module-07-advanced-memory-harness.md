# Module 7: Advanced — Memory, Storage & Harness Components

**Duration:** 45 minutes (optional advanced section)

---

## Overview

So far our agent starts every conversation from scratch — it doesn't remember user preferences, past decisions, or earlier interactions. This module covers the **Strands Harness** components that make agents production-ready:

- **Memory** — Long-term knowledge that persists across sessions
- **Storage** — Pluggable backends (file, S3) for state persistence
- **Context Management** — Keeping conversations within model limits
- **Plugins** — Context Injector, Context Offloader, Session Management
- **Conversation Caching** — Resume sessions without replaying history

---

## 7.1 Memory: Making Your Agent Remember (15 min)

### The MemoryManager

The `MemoryManager` gives an agent long-term memory that persists across sessions. It handles three jobs:

| Job | Description | Default |
|-----|-------------|---------|
| **Recall** | Agent searches stored knowledge on demand via a tool | ✅ Enabled |
| **Injection** | Manager folds relevant knowledge into the prompt automatically | ✅ Enabled |
| **Extraction** | Turning conversation messages into memories | ❌ Opt-in |

### Quick Start with TestMemoryStore

The zero-setup store that persists to a local JSON file — perfect for development:

```python
from strands import Agent
from strands.memory import MemoryManager
from strands.vended_memory_stores.test_memory_store import TestMemoryStore

# Persists to ~/.strands/memory/preferences.json by default
store = TestMemoryStore(name="preferences")

agent = Agent(
    memory_manager=MemoryManager(stores=[store]),
    tools=[read_emails, send_email, list_events, create_event,
           create_document, get_document, update_document]
)
```

Now the agent can search its memory during conversations:
```
You: I prefer morning meetings before 10am
Assistant: Got it, I'll remember that you prefer morning meetings before 10am.

# ... next session ...
You: Schedule a meeting with the team
Assistant: Based on your preference for morning meetings, I'll create an event before 10am.
```

### Enabling Write Capabilities

Let the agent decide what to save with `add_tool_config`:

```python
agent = Agent(
    memory_manager=MemoryManager(
        stores=[store],
        add_tool_config=True,  # Agent can save memories itself
    ),
    tools=[...]
)
```

Or enable **automatic extraction** — memories captured from conversations without tool calls:

```python
from strands.vended_memory_stores import BedrockKnowledgeBaseStore

store = BedrockKnowledgeBaseStore(
    name="preferences",
    writable=True,
    extraction=True,  # Capture memories every 5 turns automatically
    config={
        "knowledge_base_id": "KB123",
        "data_source_type": "CUSTOM",
        "data_source_id": "DS456"
    },
)
```

### Context Injection

Injection searches memory **before** each model call and folds results into the prompt — the agent always has relevant context without explicitly searching:

```python
from strands.memory.types import MemoryInjectionConfig

agent = Agent(
    memory_manager=MemoryManager(
        stores=[store],
        injection=MemoryInjectionConfig(
            trigger="everyTurn",  # or "userTurn" (default)
            max_entries=3,
            format=lambda context: "\n".join(
                f"- {entry.content}" for entry in context.entries
            ),
        ),
    ),
)
```

### Multi-Store Pattern (Multi-Tenancy)

Use multiple stores for different knowledge scopes:

```python
personal = TestMemoryStore(name="personal")   # User-specific preferences
team = TestMemoryStore(name="team")           # Shared team knowledge

agent = Agent(
    memory_manager=MemoryManager(stores=[personal, team])
)
```

The agent sees all stores in its `search_memory` tool and can target a specific one by name.

### 🔨 Hands-On: Add Memory to Our Agent

```python
# agent_with_memory.py
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.memory import MemoryManager
from strands.vended_memory_stores.test_memory_store import TestMemoryStore
from tools import *

store = TestMemoryStore(name="assistant_memory")

agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    system_prompt="You are a personal assistant. Remember user preferences across sessions.",
    memory_manager=MemoryManager(
        stores=[store],
        add_tool_config=True,
    ),
    tools=[read_emails, send_email, list_events, create_event,
           create_document, get_document, update_document]
)
```

Test it:
```
Session 1:
You: I always want meeting invites to include a Zoom link
Assistant: I'll remember that. [saves to memory]

Session 2:
You: Create a meeting with the team tomorrow at 2pm
Assistant: [recalls preference] I'll include a Zoom link as you prefer...
```

---

## 7.2 Storage Backends (10 min)

### The Storage Abstraction

Storage backends persist agent state. You pick one backend; plugins like Context Offloader, Session Management, and Memory use it automatically.

| Backend | Where Data Lives | Best For |
|---------|-----------------|----------|
| `InMemoryStorage` | Process memory | Tests, short-lived agents |
| `LocalFileStorage` | Local filesystem | Development, single-machine |
| `S3Storage` | Amazon S3 | Production, multi-instance |

### Usage

```python
from strands.storage import LocalFileStorage, S3Storage

# Development
storage = LocalFileStorage("./agent-data/")

# Production
storage = S3Storage("my-agent-bucket", prefix="prod/sessions/")
```

Pass storage to plugins that need persistence:

```python
from strands.plugins import ContextOffloader

agent = Agent(
    plugins=[ContextOffloader(storage=storage)],
    tools=[...]
)
```

### Custom Storage

Implement four async methods (`write`, `read`, `delete`, `list`) for any backend — DynamoDB, Redis, PostgreSQL, etc.

---

## 7.3 Context Management & Caching (10 min)

### The Problem: Context Window Limits

Models have finite context windows (128K-200K tokens). Long conversations with many tool calls can exceed this limit. Strands provides two mechanisms:

### Conversation Management

Keeps the conversation within the model's context window during a session (truncation, summarization):

```python
from strands import Agent

agent = Agent(
    conversation_manager=...,  # Built-in strategies available
    tools=[...]
)
```

### Context Offloader Plugin

Offloads large tool results to storage, replacing them with a summary. When the agent needs the full result, it's fetched on demand:

```python
from strands.plugins import ContextOffloader
from strands.storage import LocalFileStorage

agent = Agent(
    plugins=[ContextOffloader(storage=LocalFileStorage())],
    tools=[...]
)
```

This is critical for our personal assistant — a `read_emails` call returning 20 emails with full bodies would consume significant context. With the offloader, only summaries stay in context.

### Session Management (Resume Conversations)

Persist the full conversation so an agent can resume where it left off across restarts:

```python
from strands.storage import S3Storage

storage = S3Storage("my-bucket", prefix="sessions/")

# Agent picks up exactly where it left off
agent = Agent(
    session_id="user-123-session",
    storage=storage,
    tools=[...]
)
```

### How They Relate

| Feature | Scope | Purpose |
|---------|-------|---------|
| Session Management | Within a session | Persist & resume conversation |
| Conversation Management | Within a session | Keep within context limits |
| Memory | Across sessions | Durable knowledge (preferences, facts) |
| Context Offloader | Within a session | Large results → storage → summary |

---

## 7.4 Plugins: Extending Agent Behavior (10 min)

### Plugin Architecture

Plugins hook into the agent lifecycle to add capabilities without modifying core logic:

```python
agent = Agent(
    plugins=[plugin1, plugin2, ...],
    tools=[...]
)
```

### Context Injector

Inject arbitrary context into every model call — a clock, environment info, or custom data:

```python
from strands.vended_plugins import ContextInjector
from datetime import datetime

agent = Agent(
    plugins=[
        ContextInjector(
            render=lambda: f"Current time: {datetime.now().isoformat()}"
        )
    ],
    tools=[...]
)
```

The agent always knows the current time without needing a tool call.

### Steering Plugin

Dynamically modify the system prompt based on conversation state:

```python
from strands.plugins import Steering

agent = Agent(
    plugins=[
        Steering(
            rules=[
                "If the user mentions 'urgent', prioritize speed over thoroughness",
                "Always use formal language in emails",
            ]
        )
    ],
    tools=[...]
)
```

### GoalLoop Plugin

For autonomous agents that work toward a goal across multiple turns:

```python
from strands.plugins import GoalLoop

agent = Agent(
    plugins=[
        GoalLoop(
            goal="Process all unread emails and schedule follow-up meetings",
            max_iterations=10,
        )
    ],
    tools=[...]
)
```

### Hooks

Low-level lifecycle callbacks for custom behavior:

```python
from strands.hooks import BeforeInvocationEvent, AfterInvocationEvent

def log_invocation(event: AfterInvocationEvent):
    print(f"Agent completed turn {event.turn_count}")

agent.add_hook(log_invocation, AfterInvocationEvent)
```

---

## 7.5 Putting It All Together: Production-Ready Agent

Here's our personal assistant with all advanced features:

```python
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.memory import MemoryManager
from strands.memory.types import MemoryInjectionConfig
from strands.vended_memory_stores.test_memory_store import TestMemoryStore
from strands.vended_plugins import ContextInjector
from strands.plugins import ContextOffloader
from strands.storage import LocalFileStorage
from datetime import datetime
from tools import *

# Storage backend
storage = LocalFileStorage("./agent-state/")

# Memory store
memory_store = TestMemoryStore(name="user_preferences")

# Production agent with all features
agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    system_prompt="""You are a personal assistant with access to Gmail, Calendar, 
and Google Docs. You remember user preferences across sessions.
Always confirm before sending emails or creating events.""",
    
    # Memory: remember across sessions
    memory_manager=MemoryManager(
        stores=[memory_store],
        add_tool_config=True,
        injection=MemoryInjectionConfig(trigger="userTurn", max_entries=5),
    ),
    
    # Plugins: context management
    plugins=[
        ContextInjector(render=lambda: f"Current time: {datetime.now().isoformat()}"),
        ContextOffloader(storage=storage),
    ],
    
    # Tools: Google Workspace
    tools=[read_emails, send_email, list_events, create_event,
           create_document, get_document, update_document],
)
```

---

## Key Takeaways

1. **Memory** makes agents personalized — they remember preferences and facts across sessions
2. **Storage** decouples state from the process — local files for dev, S3 for prod
3. **Context Offloader** prevents context overflow from large tool responses
4. **Context Injector** provides always-available context (time, environment) without tool calls
5. **Session Management** lets agents resume mid-conversation after restarts
6. **Hooks & Plugins** extend behavior without modifying core agent logic

---

## Resources

- [Memory Overview](https://strandsagents.com/docs/user-guide/concepts/memory/overview/)
- [Test Memory Store](https://strandsagents.com/docs/user-guide/concepts/memory/test-memory-store/)
- [Bedrock Knowledge Base Store](https://strandsagents.com/docs/user-guide/concepts/memory/bedrock-knowledge-base/)
- [Storage Backends](https://strandsagents.com/docs/user-guide/concepts/storage/)
- [Context Offloader](https://strandsagents.com/docs/user-guide/concepts/plugins/context-offloader/)
- [Context Injector](https://strandsagents.com/docs/user-guide/concepts/plugins/context-injector/)
- [Session Management](https://strandsagents.com/docs/user-guide/concepts/agents/session-management/)
- [Conversation Management](https://strandsagents.com/docs/user-guide/concepts/agents/conversation-management/)
- [Plugins Overview](https://strandsagents.com/docs/user-guide/concepts/plugins/)
- [Hooks](https://strandsagents.com/docs/user-guide/concepts/agents/hooks/)
