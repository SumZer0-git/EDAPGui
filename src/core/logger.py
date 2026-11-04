"""Logging setup and rotation of the log files."""

import datetime
import logging
import os
from pathlib import Path

import colorlog

from core import paths

_filename = paths.LOG_FILE
_MAX_ROTATED_LOGS = 10

# Rename existing log file to create new one.
if os.path.exists(_filename):
    filename_only = Path(_filename).stem
    t = os.path.getmtime(_filename)
    v = datetime.datetime.fromtimestamp(t)
    x = v.strftime("%Y-%m-%d %H-%M-%S")
    os.replace(_filename, paths.LOG_DIR / f"{filename_only} {x}.log")

# Keep only the newest rotated log files.
_rotated = sorted(paths.LOG_DIR.glob(f"{Path(_filename).stem} ????-??-?? ??-??-??.log"))
for _old in _rotated[:-_MAX_ROTATED_LOGS]:
    try:
        _old.unlink()
    except OSError:
        pass

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


def set_log_level(level: int, reason: str = "changed") -> None:
    """Central place to switch the log level. Always writes a marker line so the log shows where it changed."""
    old = logging.getLevelName(logger.level)
    new = logging.getLevelName(level)
    if logger.level == level and reason != "at startup":
        return
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
