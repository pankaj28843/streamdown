"""Logging configuration with rich handler."""

import logging

from rich.logging import RichHandler


def configure_logging(log_level: str = "info") -> None:
    """
    Configure logging with rich.logging.RichHandler.

    This function sets up structured logging with rich formatting for
    better readability in the terminal. It supports standard log levels
    and formats error messages with structured information.

    Args:
        log_level: Logging level (debug, info, warn, error)

    Requirements: 6.5
    """
    # Map string log level to logging constant
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }

    level = level_map.get(log_level.lower(), logging.INFO)

    # Configure rich handler
    handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_path=False,
        markup=True,
    )

    # Set format for log messages
    handler.setFormatter(
        logging.Formatter(
            fmt="%(message)s",
            datefmt="[%X]",
        )
    )

    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
    )

    # Set level for streamdown logger
    logger = logging.getLogger("streamdown")
    logger.setLevel(level)
    
    # Suppress httpx and httpcore logs to prevent interference with progress bars
    # These libraries log every HTTP request at INFO level which creates noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module name.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(f"streamdown.{name}")
