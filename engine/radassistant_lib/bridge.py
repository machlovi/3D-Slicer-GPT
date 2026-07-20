"""Thread bridge between the Claude agent worker thread and Slicer's Qt main thread.

Slicer's MRML scene and Qt widgets may only be touched from the main thread,
while Anthropic API calls must NOT run on the main thread (they would freeze
the UI — the flaw in Talk2View's busy-wait loop). This bridge lets the worker
thread request tool execution on the main thread and stream UI events back,
with the main thread staying inside the normal Qt event loop the whole time.

  worker thread                    main thread (Qt event loop)
  -------------                    ---------------------------
  run_tool_blocking(name, args) -> tool_queue -> QTimer drains ->
      waits on Event                execute tool via registered executor
  <- result set, Event set       <- result attached to request

  emit(kind, payload)           -> ui_queue  -> QTimer drains -> UI callback
"""

import queue
import threading
import time

import qt
import slicer

from . import logbook


class ToolRequest:
    def __init__(self, name, args):
        self.name = name
        self.args = args
        self.done = threading.Event()
        self.result = None
        self.error = None


class MainThreadBridge:
    """Owns the queues and the main-thread QTimer that drains them."""

    def __init__(self, poll_interval_ms=30):
        self._ui_queue = queue.Queue()
        self._tool_queue = queue.Queue()
        self._tool_executor = None   # fn(name, args) -> dict, runs on main thread
        self._ui_handler = None      # fn(kind, payload), runs on main thread
        self._timer = qt.QTimer()
        self._timer.setInterval(poll_interval_ms)
        self._timer.connect("timeout()", self._drain)

    # -- main-thread setup ---------------------------------------------------

    def start(self, ui_handler, tool_executor):
        self._ui_handler = ui_handler
        self._tool_executor = tool_executor
        self._timer.start()

    def stop(self):
        self._timer.stop()

    # -- worker-thread API ---------------------------------------------------

    def emit(self, kind, payload=None):
        """Post a UI event from the worker thread (non-blocking)."""
        self._ui_queue.put((kind, payload))

    def run_tool_blocking(self, name, args, timeout_s=1800):
        """Execute a tool on the main thread; block the worker until done."""
        request = ToolRequest(name, args)
        self._tool_queue.put(request)
        if not request.done.wait(timeout_s):
            return {"text": f"Error: tool '{name}' timed out after {timeout_s}s.",
                    "is_error": True}
        if request.error is not None:
            return {"text": f"Error: {request.error}", "is_error": True}
        return request.result

    # -- main-thread pump ----------------------------------------------------

    def _drain(self):
        # UI events FIRST, so a status like "Running X…" paints BEFORE a heavy tool
        # blocks the main thread; then run queued tools (timed + logged, with a wait
        # cursor so the app visibly shows "busy" instead of looking dead).
        self._drain_ui()
        if not self._tool_queue.empty():
            self._process_events()      # flush the pending paint before we may block
        while True:
            try:
                request = self._tool_queue.get_nowait()
            except queue.Empty:
                break
            self._run_tool(request)

    def _drain_ui(self):
        while True:
            try:
                kind, payload = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                self._ui_handler(kind, payload)
            except Exception:
                import traceback
                traceback.print_exc()

    def _run_tool(self, request):
        logbook.tool_call(request.name, request.args)
        self._set_wait_cursor()
        t0 = time.time()
        try:
            request.result = self._tool_executor(request.name, request.args)
        except Exception as exc:        # tool bugs must never kill the pump
            import traceback
            traceback.print_exc()
            request.error = str(exc)
            logbook.error("tool " + str(request.name), exc)
        finally:
            request.done.set()
            self._restore_cursor()
        duration_ms = int((time.time() - t0) * 1000)
        res = request.result if isinstance(request.result, dict) else {}
        ok = not (request.error or res.get("is_error"))
        logbook.tool_result(request.name, ok, duration_ms,
                            request.error or res.get("text", ""))

    @staticmethod
    def _process_events():
        try:
            slicer.app.processEvents()
        except Exception:
            pass

    @staticmethod
    def _set_wait_cursor():
        try:
            qt.QApplication.setOverrideCursor(qt.QCursor(qt.Qt.WaitCursor))
        except Exception:
            pass

    @staticmethod
    def _restore_cursor():
        try:
            qt.QApplication.restoreOverrideCursor()
        except Exception:
            pass
