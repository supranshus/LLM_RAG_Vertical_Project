import contextvars
import logging
import re

from app.core.logging import request_id_var, setup_logging, user_var

LINE = re.compile(
    r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \| INFO \| (?P<name>\S+) \| (?P<ctx>.*?) \| (?P<msg>.*)"
)


def _last_line(path):
    for handler in logging.getLogger().handlers:
        handler.flush()
    return path.read_text(encoding="utf-8").splitlines()[-1]


def test_setup_logging_creates_dir_and_writes_utf8(tmp_path):
    log_dir = tmp_path / "nested" / "logs"
    setup_logging(str(log_dir), "INFO", "backend.log")

    def emit():
        request_id_var.set("ab12")
        user_var.set("aditi@org")
        logging.getLogger("app.test").info("namaste नमस्ते")

    contextvars.Context().run(emit)
    line = _last_line(log_dir / "backend.log")
    match = LINE.fullmatch(line)
    assert match, line
    assert match["name"] == "app.test"
    assert match["ctx"] == "req=ab12 user=aditi@org"
    assert match["msg"] == "namaste नमस्ते"


def test_defaults_when_no_context(tmp_path):
    setup_logging(str(tmp_path), "INFO", "backend.log")
    contextvars.Context().run(logging.getLogger("x").info, "hi")
    assert _last_line(tmp_path / "backend.log").endswith("| req=- user=- | hi")


def test_setup_logging_is_idempotent(tmp_path):
    setup_logging(str(tmp_path), "INFO", "backend.log")
    setup_logging(str(tmp_path), "INFO", "backend.log")
    logging.getLogger("dup").info("once")
    for handler in logging.getLogger().handlers:
        handler.flush()
    text = (tmp_path / "backend.log").read_text(encoding="utf-8")
    assert text.count("once") == 1
