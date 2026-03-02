"""
logger.py
---------
Centralised logging configuration for the Sales Incentive Compensation Simulator.

Provides a factory function that returns a named logger pre-configured to write
to both a rotating file handler and the console.  All application modules should
obtain their loggers exclusively through :func:`get_logger` so that formatting
and handler configuration remain consistent across the entire codebase.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
_LOG_DIR: str = "logs"
_LOG_FILE: str = os.path.join(_LOG_DIR, "app.log")
_MAX_BYTES: int = 10 * 1024 * 1024   # 10 MB per file
_BACKUP_COUNT: int = 5               # keep the 5 most-recent rotated files
_LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# Track loggers that have already been configured so we never double-add handlers.
_configured_loggers: set[str] = set()


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Return a production-ready logger identified by *name*.

    The logger is initialised at most once per unique name.  Subsequent calls
    with the same name return the already-configured logger without adding
    duplicate handlers.

    Parameters
    ----------
    name : str
        Logical name for the logger (typically ``__name__`` of the calling
        module, e.g. ``"src.data_generator"``).
    level : int, optional
        Python logging level (default: ``logging.INFO``).

    Returns
    -------
    logging.Logger
        Fully configured logger instance.

    Notes
    -----
    * Console output is always enabled.
    * File output goes to ``logs/app.log`` with automatic rotation at 10 MB.
      The ``logs/`` directory is created on first use if it does not exist.
    """
    logger = logging.getLogger(name)

    # Guard against double-initialisation (e.g. during hot-reload in notebooks).
    if name in _configured_loggers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # ------------------------------------------------------------------ #
    # Console handler – writes INFO+ messages to stdout                   #
    # ------------------------------------------------------------------ #
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ------------------------------------------------------------------ #
    # Rotating file handler – writes to logs/app.log                      #
    # ------------------------------------------------------------------ #
    os.makedirs(_LOG_DIR, exist_ok=True)
    file_handler = RotatingFileHandler(
        filename=_LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Prevent log records from propagating to the root logger, which would
    # cause duplicate output in environments that configure a root handler.
    logger.propagate = False

    _configured_loggers.add(name)
    return logger
