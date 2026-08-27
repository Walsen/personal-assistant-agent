---
name: add-confirmation-gate
description: Use when adding a new tool that performs an irreversible or moderate-risk action (sends something, creates something, deletes something, modifies external state) and deciding whether/how to require user confirmation before it executes. Covers the steering vs hard Interrupt decision and implementation for this personal assistant agent.
---

# Add a confirmation gate to a risky tool

## Goal

Decide whether a new tool needs a confirmation gate, which of the two
mechanisms this repo uses fits, and implement it correctly - so a
system-prompt instruction ("please confirm before...") isn't the only
thing standing between the model and an irreversible action.

## Decision: steering vs. hard Interrupt

| | Soft steering (`steering.py`) | Hard Interrupt (`tool_context.interrupt(...)`) |
|---|---|---|
| Used for | `send_email`, `create_event` | `delete_email` |
| Mechanism | First call is deterministically blocked with a `Guide` telling the model to summarize and ask the user; the *exact same* tool call on retry is allowed through | Tool itself calls `tool_context.interrupt(name, reason={...})`, which pauses execution and requires a synchronous response before the tool body runs at all |
| Reversibility of the gated action | Moderate risk, but not always catastrophic if it slips through | Irreversible or hard-to-reverse (Trash auto-purges after ~30 days) |
| Best fit for | Actions where "ask, then let the model naturally proceed after the user says yes in the next message" reads naturally in conversation | Actions that must never execute without an explicit, structured yes/no - including from an unattended/autonomous caller (see step 08), which can't answer a steering `Guide` conversationally but WILL simply stall forever on an Interrupt (safe failure mode) |

Default to hard Interrupt if you're unsure - it's the stricter mechanism
and degrades safely (stalls, rather than silently proceeding) when there's
no human in the loop, which matters once step 08's autonomous runner can
invoke any tool.

## Implementing soft steering

1. Add the tool name to `steering.py`'s `CONFIRMATION_REQUIRED_TOOLS` set.
2. No other code change is needed - `ConfirmationSteeringHandler` already
   handles any tool name in that set generically, tracking per-input
   signatures in `agent.state` so a retry with the *same* arguments (after
   the user confirms) proceeds, but a *different* set of arguments
   requires a fresh confirmation.
3. Make sure the system prompt still says to summarize the action and ask
   before calling it - steering blocks the first attempt, but the model
   needs to know to try again after the user says yes, since nothing
   automatically retries the call for it.

## Implementing a hard Interrupt

1. Add `context=True` to the `@tool` decorator and accept a
   `tool_context: ToolContext` first parameter.
2. Call `tool_context.interrupt(name, reason={...})` before doing anything
   irreversible. `reason` should carry enough detail (IDs, subject,
   sender/recipient) for the confirmation UI/prompt to show the user what
   they're approving.
3. Check the response value explicitly (this repo's convention: accept
   `"y"`/`"yes"` case-insensitively as approval, anything else as denial)
   and return a clear "NOT performed" message on denial rather than
   raising.
4. Only after approval, wrap the actual API call in `google_api_call(...)`
   as usual.
5. See `tools/gmail.py`'s `delete_email` for the full reference
   implementation, and `agent.py`'s `_resolve_interrupts()` for how the
   CLI resolves a pending interrupt via `input()` (steps 06+ instead
   return the interrupt directly in an HTTP response - see
   `06-agente-AgentCore-deploy/DEPLOY_AGENTCORE.md`).

## Testing

For steering: call `ConfirmationSteeringHandler.steer_before_tool()`
directly (it's async) with a fake `agent.state` (plain dict-backed) and a
`tool_use` dict matching `{"name": ..., "input": {...}}`. Assert: a
non-gated tool always returns `Proceed`; first call to a gated tool
returns `Guide` and records a signature; identical retry returns `Proceed`
and consumes the signature; different input still `Guide`s.

For hard Interrupt: mock `tool_context.interrupt(...)` to return `"y"` (or
`"yes"`) and confirm the underlying API call happens; mock it returning
anything else and confirm the API call is NOT made and a "NOT performed"
message is returned instead.

See `05-agente-advanced-harness/tests/test_steering.py` and
`tests/test_gmail.py`'s `delete_email` tests for the exact current
reference shape.
