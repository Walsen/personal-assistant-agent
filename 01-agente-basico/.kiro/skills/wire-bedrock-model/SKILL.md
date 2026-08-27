---
name: wire-bedrock-model
description: Use when adding, changing, or debugging the BedrockModel configuration (model_id, region, temperature) or the system prompt in this repo's personal assistant agent steps. Covers the conventions used across steps 01-06.
---

# Wire a BedrockModel into the agent

## Goal

Configure or change the `strands.models.bedrock.BedrockModel` and system
prompt consistently with how every other step in this repo does it, so
behavior (and later, tests that mock it) stays predictable across steps.

## Current convention (as of step 01+)

```python
from strands import Agent
from strands.models.bedrock import BedrockModel

bedrock_model = BedrockModel(
    model_id="global.anthropic.claude-sonnet-4-6",
    region_name="us-east-1",
    temperature=0.3,
)

agent = Agent(
    model=bedrock_model,
    system_prompt=SYSTEM_PROMPT,
)
```

## Steps

1. Read the current `agent.py` in the step you're modifying first - don't
   assume the shape above is unchanged; later steps add `tools=`,
   `plugins=`, and `session_manager=` on top of this same base.

2. If changing `model_id`: check whether the new model is enabled for your
   account in Amazon Bedrock's model access page for the target region
   before wiring it in - an un-enabled model fails at first invocation
   with an access-denied error, not at construction time.

3. If changing `region_name`: confirm the target region has the model
   enabled too - `region_name` here is the Bedrock inference region, not
   necessarily where you deploy other resources (S3/Lambda/etc in later
   steps can be a different region).

4. `temperature` conventionally stays at `0.3` across this repo for
   consistent, less creative tool-calling behavior. Only raise it if the
   task genuinely benefits from more variation (e.g. brainstorming), and
   note why in a comment.

5. System prompt conventions seen across steps: state what the agent can
   do as a bullet list, explicitly require confirmation before
   send_email/create_event/doc-modifying actions, and ask for concise,
   clearly-formatted output. Keep new capability bullets in sync with
   `ALL_TOOLS` (adding a tool without mentioning it in the prompt means the
   model won't reliably discover it end-to-end from user phrasing alone).

6. After changing model config, re-run that step's test suite
   (`devbox run -- uv run pytest -v`) - tests that construct/mock
   `BedrockModel` assert on exact `model_id`/`region_name` values (see
   `01-agente-basico/tests/test_agent.py`), so a config change requires a
   matching test update, not just a source change.
