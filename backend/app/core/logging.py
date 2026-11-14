import logging
import sys
from contextvars import ContextVar
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | req=%(request_id)s user=%(user)s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_var: ContextVar[str] = ContextVar("user", default="-")


class ContextFilter(logging.Filter):
    """Adds the current request id and user to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user = user_var.get()
        return True


def setup_logging(log_dir: str, level: str, filename: str, retention_days: int = 14) -> None:
    """Log plain text lines to the console and to a daily-rotated file in log_dir."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_app_handler", False):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    context_filter = ContextFilter()
    file_handler = TimedRotatingFileHandler(
        Path(log_dir) / filename, when="midnight", backupCount=retention_days, encoding="utf-8"
    )
    console_handler = logging.StreamHandler(sys.stdout)
    for handler in (file_handler, console_handler):
        handler.setFormatter(formatter)
        handler.addFilter(context_filter)
        handler._app_handler = True
        root.addHandler(handler)
    root.setLevel(level.upper())
