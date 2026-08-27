---
name: add-docs-drive-capability
description: Use when extending Google Docs tools with Drive-backed capabilities (searching docs by name, listing recently modified docs, or other Drive-query-based features) in this personal assistant agent. Based on the search_docs pattern introduced in step 04.
---

# Add a Drive-backed Docs capability

## Goal

Extend `tools/docs.py` with a new capability that needs Drive's file-search
API (not just the Docs content API), following the pattern `search_docs`
already established in this step.

## Background

Before this step, `read_doc`/`create_doc` required the caller to already
know a document's ID. `search_docs` closed that gap by querying Drive
(`get_drive_service()`, not `get_docs_service()`) so the model can resolve
"the doc about X" or "my most recent doc" to an ID without asking the user
to look it up manually.

## Steps

1. Confirm the `drive.readonly` scope is present in `tools/auth.py`'s
   `SCOPES` list (added starting step 04) - without it, Drive queries
   fail with a 403 regardless of code correctness. If you widen scopes,
   existing users need to redo the OAuth consent flow (see
   `google-oauth-setup` skill).

2. Use `get_drive_service()` (not `get_docs_service()`) for any query
   that searches/lists/filters files rather than reading/writing a
   specific document's content:
   ```python
   service = get_drive_service()
   q = "mimeType='application/vnd.google-apps.document' and trashed=false"
   if query:
       escaped_query = query.replace("'", "\\'")  # escape single quotes in Drive query syntax
       q += f" and name contains '{escaped_query}'"
   response = google_api_call(
       "my_tool",
       lambda: service.files().list(
           q=q, pageSize=max_results, orderBy="modifiedTime desc",
           fields="files(id, name, modifiedTime, webViewLink)",
       ).execute(),
   )
   ```
   Always set `fields=` explicitly to only the fields you need - an
   unrestricted Drive files().list() response is large and slow.

3. Mind Drive query string escaping: single quotes inside a user-supplied
   query segment must be escaped (`\\'`) since they're the query syntax's
   own delimiter, or Drive returns a 400 for malformed query syntax
   (this becomes a `ToolExecutionError` via `google_api_call`, not a
   crash, but it's confusing to debug without knowing the cause).

4. Default to "most recently modified" ordering when no search term is
   given, rather than erroring or returning nothing - `search_docs`'s
   pattern of "empty query -> recent docs" is more useful to the model
   than requiring an exact query every time.

5. Test both branches: query given (assert the `contains` clause and
   escaping appear in the constructed query) and query omitted (assert
   the base query with no `contains` clause). Mock `get_drive_service()`
   returning canned `files()` results - never hit the real Drive API.
