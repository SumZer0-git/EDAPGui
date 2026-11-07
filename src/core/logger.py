"""Logging setup and rotation of the log files."""

import datetime
import logging
import os
from pathlib import Path

import colorlog

from core import paths

_filename = paths.LOG_FILE
_MAX_ROTATED_LOGS = 10


def _rotate_log(filename):
    if os.path.exists(filename):
        timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(filename)).strftime("%Y-%m-%d %H-%M-%S")
        os.replace(filename, filename.parent / f"{filename.stem} {timestamp}.log")
    rotated = sorted(filename.parent.glob(f"{filename.stem} ????-??-?? ??-??-??.log"))
    for old in rotated[:-_MAX_ROTATED_LOGS]:
        try:
            old.unlink()
        except OSError as error:
            logging.getLogger("ed_log").warning("Could not remove old log %s: %s", old, error)


_rotate_log(_filename)

_root_logger = logging.getLogger()
_log_path = Path(_filename).resolve()
_file_handler = next(
    (
        handler
        for handler in _root_logger.handlers
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename).resolve() == _log_path
    ),
    None,
)
if _file_handler is None:
    if not _root_logger.handlers:
        _root_logger.setLevel(logging.ERROR)
    _file_handler = logging.FileHandler(_filename, encoding="utf-8")
    _root_logger.addHandler(_file_handler)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", "%H:%M:%S"))

logger = colorlog.getLogger("ed_log")

# Default level of the log file; the UI switch (Error/Info/Debug) changes it at runtime.
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
handler.setLevel(logging.WARNING)  # change this to what is shown on console
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s %(white)s%(message)s",
        log_colors={
            "DEBUG": "fg_bold_cyan",
            "INFO": "fg_bold_green",
            "WARNING": "bg_bold_yellow,fg_bold_blue",
            "ERROR": "bg_bold_red,fg_bold_white",
            "CRITICAL": "bg_bold_red,fg_bold_yellow",
        },
        secondary_log_colors={},
    )
)
logger.addHandler(handler)

_debug_file_handler = None


def set_log_level(level: int, reason: str = "changed") -> None:
    """Central place to switch the log level. Always writes a marker line so the log shows where it changed."""
    global _debug_file_handler
    old = logging.getLevelName(logger.level)
    new = logging.getLevelName(level)
    if logger.level == level and reason != "at startup":
        return
    if level == logging.DEBUG and _debug_file_handler is None:
        _rotate_log(paths.DEBUG_LOG_FILE)
        _debug_file_handler = logging.FileHandler(paths.DEBUG_LOG_FILE, encoding="utf-8")
        _debug_file_handler.setFormatter(_file_handler.formatter)
        _root_logger.addHandler(_debug_file_handler)
    if _debug_file_handler is not None:
        _debug_file_handler.setLevel(logging.DEBUG if level == logging.DEBUG else logging.CRITICAL + 1)
    logger.setLevel(logging.DEBUG)  # make sure the marker is written regardless of the old and new level
    logger.info(f"=== Log level {reason}: {old} -> {new} ===")
    logger.setLevel(level)


def _install_exception_hooks() -> None:
    """Write otherwise console-only errors (also at shutdown, when the console closes at once) to the log file."""
    import sys
    import threading
    import tkinter

    def log_exception(exc_type, exc_value, exc_tb, where):
        logger.critical(f"Unhandled exception ({where})", exc_info=(exc_type, exc_value, exc_tb))

    previous_excepthook = sys.excepthook
    previous_thread_hook = threading.excepthook
    previous_unraisable = sys.unraisablehook

    def excepthook(exc_type, exc_value, exc_tb):
        log_exception(exc_type, exc_value, exc_tb, "main thread")
        previous_excepthook(exc_type, exc_value, exc_tb)

    def thread_hook(args):
        log_exception(args.exc_type, args.exc_value, args.exc_traceback, f"thread {getattr(args.thread, 'name', '?')}")
        previous_thread_hook(args)

    def unraisable_hook(args):
        log_exception(args.exc_type, args.exc_value, args.exc_traceback, f"unraisable, {args.err_msg}: {args.object!r}")
        previous_unraisable(args)

    def tk_callback_exception(self, exc_type, exc_value, exc_tb):
        log_exception(exc_type, exc_value, exc_tb, "Tk callback")

    sys.excepthook = excepthook
    threading.excepthook = thread_hook
    sys.unraisablehook = unraisable_hook
    tkinter.Tk.report_callback_exception = tk_callback_exception


_install_exception_hooks()

# logger.disabled = True
# logger.disabled = False
