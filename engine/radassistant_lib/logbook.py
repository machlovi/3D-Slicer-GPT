"""Detailed session logging — a timestamped file that records exactly what the
model asked for, which tool ran, how long each took, and where it failed.

This is the ground truth for debugging "where is the model / segmentator failing"
and "what is making the UI hang": every tool call is logged with its **duration in
milliseconds** (measured on the Qt main thread, so a big number == a real UI freeze)
and every model round with its latency, stop reason and any error.

Pure stdlib and defensive: a logging failure must never break the agent, so every
public call swallows its own errors.

    from radassistant_lib import logbook
    logbook.setup()                       # once, at module load
    logbook.log_path()                    # -> the file to tail / send for debugging
"""

import logging
import os
from datetime import datetime

_LOGGER = None
_LOGPATH = None
_LOGDIR = None


def setup(log_dir=None):
    """Create the session log file (idempotent). Returns the logger."""
    global _LOGGER, _LOGPATH, _LOGDIR
    if _LOGGER is not None:
        return _LOGGER
    try:
        _LOGDIR = log_dir or os.path.join(os.path.expanduser("~"), ".radassistant", "logs")
        os.makedirs(_LOGDIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _LOGPATH = os.path.join(_LOGDIR, f"radassistant_{stamp}.log")
        logger = logging.getLogger("radassistant")
        logger.setLevel(logging.DEBUG)
        for h in list(logger.handlers):
            logger.removeHandler(h)
        handler = logging.FileHandler(_LOGPATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s.%(msecs)03d %(threadName)-14s %(levelname)-5s %(message)s",
            "%H:%M:%S"))
        logger.addHandler(handler)
        logger.propagate = False
        _LOGGER = logger
        logger.info("========== RadAssistant session log ==========")
        logger.info("log file: %s", _LOGPATH)
    except Exception:            # logging must never break the app
        _LOGGER = logging.getLogger("radassistant")  # no-op fallback
    return _LOGGER


def _log():
    return _LOGGER or setup()


def log_path():
    return _LOGPATH


def log_dir():
    return _LOGDIR


def _short(value, n=300):
    try:
        s = value if isinstance(value, str) else repr(value)
    except Exception:
        s = "<unrepresentable>"
    s = s.replace("\n", "\\n")
    return s if len(s) <= n else s[:n] + f"…(+{len(s) - n} chars)"


# -- structured event helpers (all defensive) --------------------------------

def turn(user_text):
    try:
        _log().info("USER   %s", _short(user_text, 600))
    except Exception:
        pass


def model(duration_ms, stop_reason, error=None, usage=None):
    try:
        msg = "MODEL  %6dms  stop=%s  usage=%s" % (duration_ms, stop_reason, usage or {})
        if error:
            _log().warning(msg + "  ERROR=%s", _short(error, 300))
        else:
            _log().info(msg)
    except Exception:
        pass


def tool_call(name, args):
    try:
        _log().debug("CALL   %-26s args=%s", name, _short(args, 400))
    except Exception:
        pass


def tool_result(name, ok, duration_ms, summary):
    try:
        line = "TOOL   %-26s %6dms  %s :: %s" % (
            name, duration_ms, "OK " if ok else "ERR", _short(summary, 300))
        (_log().info if ok else _log().warning)(line)
        if duration_ms >= 1500:      # flag anything that blocked the UI noticeably
            _log().warning("SLOW   %-26s took %.1fs on the main thread (UI froze)",
                           name, duration_ms / 1000.0)
    except Exception:
        pass


def event(msg, *args):
    try:
        _log().info(msg, *args)
    except Exception:
        pass


def error(where, exc):
    try:
        _log().error("ERROR  %s :: %s", where, _short(exc, 400))
    except Exception:
        pass
