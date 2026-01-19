"""Colored logging configuration for Neural Sieve CLI."""

import logging
import sys

# ANSI color codes
COLORS = {
    # Log levels
    "DEBUG": "\033[36m",      # Cyan
    "INFO": "\033[32m",       # Green
    "WARNING": "\033[33m",    # Yellow
    "ERROR": "\033[31m",      # Red
    "CRITICAL": "\033[35m",   # Magenta
    # Service prefixes
    "WATCHER": "\033[96m",    # Bright Cyan
    "DASHBOARD": "\033[95m",  # Bright Magenta
    "STARTUP": "\033[94m",    # Bright Blue
    "PROCESSOR": "\033[97m",  # Bright White
    "LLM": "\033[93m",        # Bright Yellow
    # Formatting
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
}

# Service prefix patterns to colorize
SERVICE_PREFIXES = ["WATCHER", "DASHBOARD", "STARTUP", "PROCESSOR", "LLM"]


class ColoredFormatter(logging.Formatter):
    """Logging formatter with ANSI colors for levels and service prefixes."""

    def format(self, record: logging.LogRecord) -> str:
        # Save original values
        original_levelname = record.levelname
        original_msg = record.msg

        # Color the level name
        level_color = COLORS.get(record.levelname, "")
        reset = COLORS["RESET"]
        record.levelname = f"{level_color}{record.levelname:<7}{reset}"

        # Color service prefixes in the message
        if isinstance(record.msg, str):
            msg = record.msg
            for prefix in SERVICE_PREFIXES:
                bracket_prefix = f"[{prefix}]"
                if bracket_prefix in msg:
                    colored_prefix = f"{COLORS.get(prefix, '')}{COLORS['BOLD']}[{prefix}]{reset}"
                    msg = msg.replace(bracket_prefix, colored_prefix)
            record.msg = msg

        # Format the record
        result = super().format(record)

        # Restore original values (in case record is reused)
        record.levelname = original_levelname
        record.msg = original_msg

        return result


def setup_colored_logging(verbose: bool = False) -> None:
    """Configure colored logging for the CLI.

    Args:
        verbose: If True, set log level to DEBUG. Otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Create handler with colored formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        ColoredFormatter(
            fmt="%(asctime)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)

    root_logger.addHandler(handler)

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)
