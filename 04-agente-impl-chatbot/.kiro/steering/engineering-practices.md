---
inclusion: always
---

# Engineering practices

These practices apply to all code written or modified in this project (a
Python codebase built on the Strands Agents SDK, exposing Gmail, Google
Calendar, and Google Docs as agent tools, eventually deployed to Amazon
Bedrock AgentCore Runtime behind a web chat and an autonomous scheduler).
Examples below reference this repo's actual modules — apply the underlying
principle even in steps where a referenced module doesn't exist yet.

## 1. Clean Code & SOLID

- **Single Responsibility** — each function/module does one thing. Google
  API tools are split by service (`tools/gmail.py`, `tools/calendar.py`,
  `tools/docs.py`), auth lives on its own (`tools/auth.py`), and agent
  wiring (`agent.py`) stays separate from tool implementations. Don't mix
  HTTP-service boilerplate (Google API client calls) with business rules
  (steering/confirmation logic) in the same function.
- **Open/Closed** — prefer adding new behavior by adding a new tool/skill
  over editing existing ones. New tools slot into the `ALL_TOOLS` list in
  `tools/__init__.py`; new skills are new files under `skills/` picked up
  by `AgentSkills` — neither requires touching unrelated tools.
- **Liskov Substitution** — anything swapped behind an abstraction (e.g.
  `FileSessionManager` vs `S3SessionManager` chosen by
  `AGENT_SESSIONS_BUCKET`) must behave identically from the caller's
  perspective — `agent.py`/`main.py` shouldn't need to know which one is
  active.
- **Interface Segregation** — keep tool function signatures narrow (a
  `@tool` should take only the arguments it needs, not a bag of unrelated
  options). Don't make callers pass parameters they don't use.
- **Dependency Inversion** — tools depend on `get_gmail_service()` /
  `get_calendar_service()` (an abstraction over Google auth), not on
  constructing OAuth clients inline. Google API failures are funneled
  through `google_api_call()` (see `tools/errors.py`) rather than each
  tool handling `HttpError` itself.
- Favor small, well-named functions over long ones. Naming should reveal
  intent (`_resolve_interrupts`, not `handle2`). Comments explain *why*
  (e.g. why `delete_email` uses an `Interrupt` while `send_email` uses
  steering), not *what* the code already makes obvious.

## 2. Test-Driven Development (TDD)

- Write a failing test **before** implementing new behavior or a bug fix:
  red → green → refactor.
- For bug fixes: write a test reproducing the bug first, confirm it fails,
  then fix the code and confirm it passes.
- Keep tests small and fast, one behavior per test, with descriptive names
  (`test_delete_email_denied_when_user_declines_interrupt`).
- No test framework is configured in this repo yet — set one up (`pytest`
  is the standard choice for Python/uv projects) before adding the first
  test rather than skipping tests.
- Every new tool, steering handler, or CDK stack construct should have
  tests covering its normal case, edge cases (missing/invalid input), and
  error cases (e.g. a Google API 403/404/429) before being considered done.
- Run the full test suite before presenting any change as complete.

## 3. Design patterns — apply when they fit, not by default

- Reach for a pattern only when it solves a real structural problem, not
  as decoration.
- Fits already present in this codebase:
  - **Strategy** — session persistence (`FileSessionManager` vs
    `S3SessionManager`, selected by environment) and steering decisions
    (`Proceed` vs `Guide` in `steering.py`) are strategies selected at
    runtime rather than hardcoded branches.
  - **Facade / boundary wrapper** — `google_api_call()` centralizes error
    translation for every Google API call instead of duplicating
    `try/except HttpError` in every tool.
  - **Template Method** — the chatbot loop (`run()` → send message →
    `_resolve_interrupts()` → print) is a fixed pipeline with the
    interrupt-resolution step as the pluggable part.
- Document *why* a pattern was chosen in a short comment when not obvious
  (e.g. why `delete_email` uses a hard `Interrupt` but `send_email` uses
  soft `steering`).
- Don't over-engineer: a single conditional or a two-line tool function
  does not need a pattern.

## 4. Robust error handling

- Never let a raw Google API traceback reach the model or the user. Route
  every Google API call through `google_api_call()` so `HttpError` becomes
  a short, actionable `ToolExecutionError` message (see the 401/403/404/429
  translations in `tools/errors.py`) instead of a dense HTTP body.
- Be specific: catch `HttpError` and `AuthenticationError` explicitly at
  tool boundaries; only catch bare `Exception` at the true top-level
  boundary (`google_api_call`'s own fallback), and log there.
- Validate external input (tool arguments coming from the model, HTTP
  request bodies in `main.py`/Lambda handlers) before use — fail fast with
  a clear message instead of letting bad input reach the Google API.
- Irreversible or moderate-risk actions (`delete_email`, `send_email`,
  `create_event`) must have explicit confirmation built into the code
  (`Interrupt` or steering), not just a system-prompt instruction the
  model could ignore.
- Fail loudly in local development, fail safely when deployed (AgentCore
  Runtime, Lambda) — no leaked internals, no crashed invocation from a
  single bad request; a scheduled/autonomous invocation (step 08) should
  fail its own Lambda run rather than silently swallow an error.

## 5. Robust logging

- Use a structured logger (Python's `logging` module, configured once via
  `logging_config.configure_logging()`) — never bare `print()` beyond
  throwaway local debugging. Each module logs through
  `logging.getLogger(__name__)`.
- Log at the right level: `DEBUG` for developer detail, `INFO` for normal
  operational events (tool call succeeded, digest run completed),
  `WARNING` for recoverable issues (a translated Google API error), `ERROR`
  for handled failures, and let genuinely unexpected exceptions be logged
  with `logger.exception(...)` for full traceback.
- Include context in log messages (tool name, message/event IDs, elapsed
  time — see the `tool=%s | ... | elapsed_ms=%.0f` pattern in
  `tools/errors.py`) without logging email bodies, tokens, or other
  sensitive data.
- Interrupt and steering decisions must be logged (`interrupt raised`,
  `interrupt resolved`, `steering=guide`/`steering=proceed`) so it's
  auditable what the agent attempted and how it was gated.
- Configure log format/output centrally (`logging_config.py`), not ad hoc
  per module or per deployment target.

## Applying these practices

When implementing a feature or fix:
1. Write the failing test(s) first.
2. Implement the smallest clean, SOLID-compliant change to pass them.
3. Introduce a design pattern only if the change reveals a genuine
   structural need for one.
4. Route new external calls through the appropriate error-handling
   boundary and add explicit error handling for new failure modes.
5. Add logging at the appropriate points and levels.
6. Run the test suite and confirm everything passes before considering the
   work done.
