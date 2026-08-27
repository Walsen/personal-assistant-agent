"""Centralized logging configuration for the personal assistant agent.

Call configure_logging() once, early in the process (done in agent.py at
import time), to set up a consistent log format across every module. Each
module then does `logger = logging.getLogger(__name__)` and logs through
that, rather than configuring logging ad-hoc per file.
"""

import logging
import os
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / ".logs"
LOG_FILE = LOG_DIR / "agent.log"

_configured = False


def configure_logging() -> None:
    """Configure root logging once for the whole application.

    Logs go to both the console (WARNING and above, to avoid cluttering the
    interactive chat) and to a rotating-free plain log file (INFO and above,
    for later inspection/auditing of what the agent actually did).

    The log level can be overridden with the AGENT_LOG_LEVEL environment
    variable (e.g. AGENT_LOG_LEVEL=DEBUG).
    """
    global _configured
    if _configured:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    level_name = os.environ.get("AGENT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
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
