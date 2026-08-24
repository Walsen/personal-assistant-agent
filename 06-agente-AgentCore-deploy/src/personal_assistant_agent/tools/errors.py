"""Shared error handling for Google API-backed tools.

Google API calls can fail for reasons a tool caller (the agent, and
ultimately the user) can often react to sensibly: an invalid/stale ID, a
permission problem, a rate limit, or a transient network issue. Left
unhandled, `googleapiclient.errors.HttpError` bubbles up with a dense,
low-signal message (raw HTTP body + headers) that isn't useful to the model
or the person reading logs.

`google_api_call` wraps a single API call, logging it (tool name, outcome,
timing) and translating known failure modes into a short, actionable
message that becomes the tool's return value. Unexpected errors are still
logged with a full traceback for later debugging, but the model still gets
a clear, bounded error string instead of the tool crashing.
"""

import logging
import time
from typing import Callable, TypeVar

from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ToolExecutionError(Exception):
    """Raised when a Google API call fails in a way the tool should report
    back to the model as a normal (non-crashing) error message."""


def _translate_http_error(tool_name: str, error: HttpError) -> str:
    """Turn a Google API HttpError into a short, actionable message."""
    status = error.resp.status if error.resp else None
    reason = (error.reason or "").strip()

    if status == 401:
        return (
            f"{tool_name} failed: authentication expired or invalid (401). "
            "The stored Google credentials may need to be re-authorized "
            "(re-run the OAuth flow to refresh token.json)."
        )
    if status == 403:
        return (
            f"{tool_name} failed: permission denied (403) - {reason or 'insufficient access'}. "
            "Check that the required Google API scope is granted and the API is enabled "
            "in Google Cloud Console."
        )
    if status == 404:
        return f"{tool_name} failed: the requested item was not found (404) - {reason or 'not found'}."
    if status == 429:
        return f"{tool_name} failed: rate limited by the Google API (429). Wait a moment and try again."
    if status and status >= 500:
        return f"{tool_name} failed: Google API server error ({status}). This is usually transient - try again."
    if status == 400:
        return f"{tool_name} failed: invalid request (400) - {reason or 'bad request parameters'}."

    return f"{tool_name} failed: Google API error ({status}) - {reason or 'unknown reason'}."


def google_api_call(tool_name: str, func: Callable[[], T]) -> T:
    """Execute func() (a Google API call), logging the attempt/outcome and
    translating HttpError into a ToolExecutionError with an actionable
    message. Call sites should catch ToolExecutionError and return its
    message as the tool's result (rather than letting it propagate), so the
    model gets a clear string instead of a raw traceback.

    Args:
        tool_name: Name of the calling tool, used in log lines and error messages.
        func: Zero-argument callable that performs the API call (e.g. a lambda
            wrapping `service.users().messages().send(...).execute()`).

    Returns:
        Whatever func() returns, on success.

    Raises:
        ToolExecutionError: If the API call fails, with a translated,
            actionable message suitable for returning to the model.
    """
    start = time.monotonic()
    try:
        result = func()
    except HttpError as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        message = _translate_http_error(tool_name, e)
        logger.warning(
            "tool=%s | Google API call failed | status=%s | elapsed_ms=%.0f | %s",
            tool_name, getattr(e.resp, "status", None), elapsed_ms, message,
        )
        raise ToolExecutionError(message) from e
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.exception(
            "tool=%s | unexpected error during Google API call | elapsed_ms=%.0f",
            tool_name, elapsed_ms,
        )
        raise ToolExecutionError(
            f"{tool_name} failed due to an unexpected error: {e}"
        ) from e
    else:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info("tool=%s | Google API call succeeded | elapsed_ms=%.0f", tool_name, elapsed_ms)
        return result
