"""Centralized logging configuration for the personal assistant agent.

Call configure_logging() once, early in the process (done in agent.py at
import time), to set up a consistent log format across every module. Each
module then does `logger = logging.getLogger(__name__)` and logs through
that, rather than configuring logging ad-hoc per file.
"""

import logging
import os
import tempfile
from pathlib import Path

# Default location for local CLI development: three levels up from this file
# (personal_assistant_agent/ -> project root) puts logs alongside .sessions/.
# This directory is not guaranteed to be writable everywhere this code runs
# (e.g. AgentCore Runtime's deployed container only guarantees /tmp is
# writable), so this is only a preference - see _resolve_log_dir() below,
# which falls back to the system temp dir if it can't be created/written to.
_PREFERRED_LOG_DIR = Path(__file__).resolve().parent.parent.parent / ".logs"

_configured = False


def _resolve_log_dir() -> Path:
    """Pick a writable log directory. Prefers _PREFERRED_LOG_DIR (local dev),
    but falls back to the system temp directory if that can't be created or
    written to (e.g. read-only filesystem in a deployed container), so a
    logging misconfiguration never prevents the agent from starting.
    """
    override = os.environ.get("AGENT_LOG_DIR")
    candidates = [Path(override)] if override else []
    candidates.append(_PREFERRED_LOG_DIR)

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.touch()
            probe.unlink()
            return candidate
        except OSError:
            continue

    fallback = Path(tempfile.gettempdir()) / "personal_assistant_agent_logs"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def configure_logging() -> None:
    """Configure root logging once for the whole application.

    Logs go to both the console (WARNING and above, to avoid cluttering the
    interactive chat) and to a rotating-free plain log file (INFO and above,
    for later inspection/auditing of what the agent actually did).

    The log level can be overridden with the AGENT_LOG_LEVEL environment
    variable (e.g. AGENT_LOG_LEVEL=DEBUG). The log directory can be
    overridden with AGENT_LOG_DIR.
    """
    global _configured
    if _configured:
        return

    log_dir = _resolve_log_dir()
    log_file = log_dir / "agent.log"

    level_name = os.environ.get("AGENT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger("personal_assistant_agent")
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.propagate = False

    # Quiet down noisy third-party libraries unless explicitly debugging.
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

    _configured = True
