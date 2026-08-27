---
name: add-google-tool
description: Use when adding a new Gmail, Calendar, or Docs tool (a new @tool function backed by a Google Workspace API call) to this personal assistant agent. Covers the get_*_service/google_api_call/ALL_TOOLS wiring pattern and matching test shape used in steps 03-06.
---

# Add a new Google Workspace tool

## Goal

Add a new `@tool`-decorated function backed by a Google API call, following
this repo's established error-handling, logging, and test conventions
instead of ad hoc `try/except HttpError`.

## Steps

1. Pick the right module: `tools/gmail.py`, `tools/calendar.py`, or
   `tools/docs.py`. If it needs Drive (search-by-name style), that's
   `tools/docs.py` too (see `search_docs`), using `get_drive_service()`.

2. Write the function:
   ```python
   @tool
   def my_new_tool(arg: str) -> str:
       """One-line summary for the model.

       Args:
           arg: what it's for.

       Returns:
           what the model sees back.
       """
       logger.info("my_new_tool called | arg=%s", arg)
       try:
           service = get_gmail_service()  # or calendar/docs/drive
           result = google_api_call(
               "my_new_tool",
               lambda: service.some().api().call(...).execute(),
           )
           logger.info("my_new_tool succeeded | ...")
           return "<formatted string the model reads>"
       except (ToolExecutionError, AuthenticationError) as e:
           return str(e)
   ```
   Never call `.execute()` directly outside `google_api_call()` - that's
   what translates `HttpError` (401/403/404/429/500) into a short,
   actionable message instead of a raw traceback reaching the model.

3. If this module doesn't yet have `tools/errors.py` / logging wired in
   (true for steps 02-04 as of writing, though 02-04 were already
   backported this session to match step 05's pattern) - check first
   rather than assuming, then follow the exact pattern already present
   in `tools/gmail.py`/`calendar.py`/`docs.py` in that same step.

4. Register the tool in `tools/__init__.py`'s `ALL_TOOLS` list - a tool
   not in that list is invisible to the agent even if fully implemented.

5. If the action is irreversible or moderate-risk (sends something,
   creates something, deletes something), do NOT just rely on a
   system-prompt instruction to "confirm first" - use the
   `add-confirmation-gate` skill (steering or hard Interrupt) instead.
   Only read-only or clearly reversible actions (like `archive_email`)
   should skip that step.

6. Write tests mirroring the existing shape in that step's `tests/`
   directory: mock `get_*_service()` (patch where imported into the tool
   module, not where it's defined) to return a `Mock()` with chained
   `.x().y().execute()` calls returning canned dicts. Cover the normal
   case and both `ToolExecutionError` and `AuthenticationError` being
   caught and returned as a string (not raised). Never make a real
   Google API call in a test.

7. Run `devbox run -- uv run pytest -v` in that step before considering
   the tool done.
