"""RadAssistantDeep - in-process LangChain deep-agent chat panel for 3D Slicer.

No external venv and no Web Server exec bridge: the agent runs inside Slicer's OWN
Python, wrapping the native RadAssistant ToolRegistry (~45 validated tools) directly.
The LangChain stack is pip_installed into Slicer's Python on first run. The agent loop
runs on a worker thread so the UI stays responsive during model calls; every tool call
hops back to the Qt main thread via MainThreadBridge (native tools touch Slicer/MRML).

Setup: add this folder to Additional module paths (it also self-registers after the first
load) and restart. The chat auto-docks on the right. Research/visualization aid - NOT a
diagnostic device. Do not enter PHI.
"""

import html
import os
import queue
import sys
import threading
import uuid

import ctk
import qt
import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleWidget,
)

_SETTINGS_PREFIX = "RadAssistantDeep/"
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEEP_CORE = os.path.dirname(os.path.dirname(_MODULE_DIR))               # .../deep  (LangChain layer)
_NATIVE = os.path.join(os.path.dirname(_DEEP_CORE), "engine")            # .../RadAssistant_DeepAgent/engine
_SKILLS = os.path.join(_NATIVE, "skills")
for _p in (_DEEP_CORE, _NATIVE):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# Packages that must exist in Slicer's Python for the in-process agent.
_REQUIRED = ["deepagents", "langchain", "langgraph", "langchain-openai", "langgraph-checkpoint-sqlite"]


def _esc(text):
    return html.escape("" if text is None else str(text))


class RadAssistantDeep(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "RadAssistantDeep"
        # Dock-only (right-side panel), like native RadAssistant: hidden from the selector
        # so its chat widget can't be pulled into the left panel when clicked.
        parent.categories = []
        parent.dependencies = []
        parent.contributors = ["RadAssistant"]
        parent.helpText = (
            "In-process LangChain deep-agent for 3D Slicer (no venv). Research and "
            "visualization aid - NOT a diagnostic device. Do not enter PHI."
        )
        parent.acknowledgementText = "MIT licensed."
        self._ensure_persistent_module_path()
        slicer.app.connect("startupCompleted()", self._auto_show_chat_dock)
        qt.QTimer.singleShot(0, self._auto_show_chat_dock)

    def _auto_show_chat_dock(self):
        """Dock the chat on the right and always show it. Headless-safe; never raises."""
        try:
            main_window = slicer.util.mainWindow()
            if main_window is None:
                return
            existing = main_window.findChild("QDockWidget", "RadAssistantDeepDockWidget")
            if existing is not None:
                existing.setVisible(True)
                existing.raise_()
                return
            widget = slicer.modules.radassistantdeep.widgetRepresentation()
            if widget is None:
                return
            dock = qt.QDockWidget("RadAssistant (Deep)", main_window)
            dock.setObjectName("RadAssistantDeepDockWidget")
            dock.setWidget(widget)
            dock.setMinimumWidth(400)
            dock.setFeatures(qt.QDockWidget.DockWidgetFloatable | qt.QDockWidget.DockWidgetMovable)
            main_window.addDockWidget(qt.Qt.RightDockWidgetArea, dock)
            action = dock.toggleViewAction()
            action.setText("RadAssistant (Deep) chat")
            action.setToolTip("Show/hide the RadAssistant deep-agent panel")
            view_menu = main_window.findChild("QMenu", "menuView")
            if view_menu:
                view_menu.addAction(action)
            for toolbar in main_window.findChildren("QToolBar"):
                if toolbar.objectName == "MainToolBar":
                    toolbar.addAction(action)
                    break
            dock.setVisible(True)
            dock.raise_()
        except Exception:
            import logging
            logging.warning("RadAssistantDeep: could not create the chat dock panel.")

    def _ensure_persistent_module_path(self):
        """Add this module's folder to Slicer's permanent module paths once, so it
        loads on every restart. Dev-only: skips an installed-extension location."""
        try:
            mine = os.path.normcase(os.path.normpath(_MODULE_DIR))
            for attr in ("extensionsInstallPath", "slicerHome"):
                base = getattr(slicer.app, attr, "") or ""
                if base and mine.startswith(os.path.normcase(os.path.normpath(base))):
                    return
            s = slicer.app.revisionUserSettings()
            key = "Modules/AdditionalPaths"
            raw = s.value(key)
            lst = [] if raw is None else ([raw] if isinstance(raw, str) else [str(x) for x in raw])
            have = [os.path.normcase(os.path.normpath(x)) for x in slicer.app.toSlicerHomeAbsolutePaths(lst)]
            if mine not in have:
                lst.append(_MODULE_DIR)
                s.setValue(key, slicer.app.toSlicerHomeRelativePaths(lst))
        except Exception:
            pass


class RadAssistantDeepLogic(ScriptedLoadableModuleLogic):
    def _get(self, key, default=""):
        return slicer.app.userSettings().value(_SETTINGS_PREFIX + key, default)

    def _set(self, key, value):
        slicer.app.userSettings().setValue(_SETTINGS_PREFIX + key, value)


class RadAssistantDeepWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        self.logic = RadAssistantDeepLogic()
        self._built = None
        self._bridge = None
        self._run_config = None
        self._worker = None
        self._stop = threading.Event()
        self._decision_q = queue.Queue()
        self._history = []
        self._streaming_text = ""
        self._thinking_text = ""
        self._render_pending = False
        self._render_timer = qt.QTimer()
        self._render_timer.setInterval(120)   # batch repaints ~8/s (native panel's cadence)
        self._render_timer.connect("timeout()", self._render_if_needed)
        self._render_timer.start()

        # --- Setup section ----------------------------------------------------
        setupBox = ctk.ctkCollapsibleButton()
        setupBox.text = "Setup"
        self.layout.addWidget(setupBox)
        form = qt.QFormLayout(setupBox)

        self.modelEdit = qt.QLineEdit(self.logic._get("model", "openai:qwen-vision"))
        self.modelEdit.toolTip = "provider:model - e.g. openai:qwen-vision (local server), anthropic:claude-opus-4-8, ollama:qwen3:14b"
        form.addRow("Model:", self.modelEdit)

        self.serverEdit = qt.QLineEdit(self.logic._get("serverUrl", ""))
        self.serverEdit.placeholderText = "http://127.0.0.1:11441/v1  (blank for cloud/default)"
        self.serverEdit.toolTip = "Model server address. For a local llama.cpp/vLLM server use http://127.0.0.1:<port>/v1."
        form.addRow("Server URL:", self.serverEdit)

        self.apiKeyEdit = qt.QLineEdit(self.logic._get("apiKey", ""))
        self.apiKeyEdit.echoMode = qt.QLineEdit.Password
        self.apiKeyEdit.placeholderText = "optional (local servers ignore it)"
        form.addRow("API key:", self.apiKeyEdit)

        self.approvalCombo = qt.QComboBox()
        self.approvalCombo.addItems(["manual", "accept", "auto"])
        self.approvalCombo.currentText = self.logic._get("approval", "accept")
        self.approvalCombo.toolTip = "manual: ask before non-trivial actions | accept: ask only irreversible/PHI | auto: never ask"
        form.addRow("Approvals:", self.approvalCombo)

        self.visionCheck = qt.QCheckBox()
        self.visionCheck.checked = self.logic._get("vision", "false") == "true"
        self.visionCheck.toolTip = "Tick only if the model can see screenshots."
        form.addRow("Model has vision:", self.visionCheck)

        self.thinkingCheck = qt.QCheckBox()
        self.thinkingCheck.checked = self.logic._get("showThinking", "true") == "true"
        self.thinkingCheck.toolTip = "Show the model's reasoning (thinking) live in the chat."
        form.addRow("Show thinking:", self.thinkingCheck)

        btnRow = qt.QHBoxLayout()
        self.connectButton = qt.QPushButton("Connect")
        self.connectButton.connect("clicked()", self.onConnect)
        btnRow.addWidget(self.connectButton)
        self.disconnectButton = qt.QPushButton("Disconnect")
        self.disconnectButton.enabled = False
        self.disconnectButton.connect("clicked()", self.onDisconnect)
        btnRow.addWidget(self.disconnectButton)
        form.addRow(btnRow)

        # --- Chat section -----------------------------------------------------
        chatBox = ctk.ctkCollapsibleButton()
        chatBox.text = "Chat"
        self.layout.addWidget(chatBox)
        chatLayout = qt.QVBoxLayout(chatBox)

        self.transcript = qt.QTextBrowser()
        self.transcript.setOpenExternalLinks(True)
        self.transcript.minimumHeight = 380
        chatLayout.addWidget(self.transcript)

        topRow = qt.QHBoxLayout()
        self.newChatButton = qt.QPushButton("New chat")
        self.newChatButton.enabled = False
        self.newChatButton.connect("clicked()", self.onNewChat)
        topRow.addWidget(self.newChatButton)
        topRow.addStretch(1)
        chatLayout.addLayout(topRow)

        inputRow = qt.QHBoxLayout()
        self.inputEdit = qt.QLineEdit()
        self.inputEdit.placeholderText = "Ask RadAssistant to do something with the scene..."
        self.inputEdit.connect("returnPressed()", self.onSend)
        self.inputEdit.enabled = False
        inputRow.addWidget(self.inputEdit)
        self.sendButton = qt.QPushButton("Send")
        self.sendButton.enabled = False
        self.sendButton.connect("clicked()", self.onSend)
        inputRow.addWidget(self.sendButton)
        self.stopButton = qt.QPushButton("Stop")
        self.stopButton.enabled = False
        self.stopButton.connect("clicked()", self.onStop)
        inputRow.addWidget(self.stopButton)
        chatLayout.addLayout(inputRow)

        self.layout.addStretch(1)
        self._appendSystem(
            "Not connected. Set the model + server URL above, then click Connect. "
            "Research/visualization aid - not a diagnostic device. Do not enter PHI."
        )

    # -- transcript helpers (reused from the proven panel) ---------------------
    # -- transcript: buffer + 120ms timer + setMarkdown (native panel's approach) --
    # Streamed deltas accumulate in buffers; a 120ms QTimer repaints the whole
    # transcript ONCE as markdown. This replaces per-token insertText, which
    # relaid-out the QTextBrowser on every token (O(n^2) and plain-text only).
    def _append(self, markdown):
        self._history.append(markdown)
        self._render_pending = True

    def _appendSystem(self, text):
        self._append("*%s*" % text.replace("\n", " "))

    def _appendUser(self, text):
        self._append("**You:** " + text)

    def _appendTool(self, name, text, is_error):
        first = (text or "").strip().splitlines()
        head = (first[0] if first else "")[:200]
        mark = "⚠" if is_error else "✓"
        self._append("`%s %s` — %s" % (mark, name, head))

    def _stream_delta(self, kind, mid, text):
        if kind == "thinking":
            self._thinking_text += text
            if self.thinkingCheck.checked:
                self._render_pending = True
        else:
            self._streaming_text += text
            self._render_pending = True

    def _finalize_stream(self):
        self._flush_streaming()

    def _flush_streaming(self):
        if self._streaming_text.strip():
            self._history.append("**RadAssistant:** " + self._streaming_text.strip())
        self._streaming_text = ""
        self._thinking_text = ""
        self._render_pending = True

    def _render_if_needed(self):
        if not self._render_pending:
            return
        self._render_pending = False
        parts = list(self._history)
        if self.thinkingCheck.checked and self._thinking_text.strip():
            parts.append("> 💭 *" + self._thinking_text.strip().replace("\n", " ") + "*")
        if self._streaming_text.strip():
            parts.append("**RadAssistant:** " + self._streaming_text.strip())
        self.transcript.setMarkdown("\n\n".join(parts))
        sb = self.transcript.verticalScrollBar()
        sb.setValue(sb.maximum)

    # -- connect ---------------------------------------------------------------
    def _saveSettings(self):
        self.logic._set("model", self.modelEdit.text)
        self.logic._set("serverUrl", self.serverEdit.text)
        self.logic._set("apiKey", self.apiKeyEdit.text)
        self.logic._set("approval", self.approvalCombo.currentText)
        self.logic._set("vision", "true" if self.visionCheck.checked else "false")
        self.logic._set("showThinking", "true" if self.thinkingCheck.checked else "false")

    def _ensure_deps(self):
        try:
            import deepagents, langchain, langgraph  # noqa: F401
            return True
        except ImportError:
            if not slicer.util.confirmYesNoDisplay(
                "RadAssistant (Deep) needs the LangChain packages installed into Slicer's "
                "Python (one-time). Install now? This may take a couple of minutes."
            ):
                self._appendSystem("Cannot start: LangChain packages are not installed.")
                return False
            self._appendSystem("Installing LangChain into Slicer's Python (one-time)...")
            slicer.app.processEvents()
            try:
                slicer.util.pip_install(" ".join(_REQUIRED))
            except Exception as exc:
                slicer.util.errorDisplay("Dependency install failed:\n%s" % exc)
                return False
            return True

    def _model_reachable(self, base_url):
        """Quick reachability probe so Connect fails fast with a clear message
        instead of hanging on the first turn when the model server isn't answering."""
        import urllib.request
        url = base_url.rstrip("/") + "/models"
        try:
            urllib.request.urlopen(url, timeout=6).read(1)
            return True, ""
        except Exception as exc:
            return False, str(exc)

    def onConnect(self):
        self._saveSettings()
        model_spec = self.modelEdit.text.strip()
        server_url = self.serverEdit.text.strip()
        if model_spec.startswith("openai:") and not server_url:
            slicer.util.errorDisplay(
                "Model '%s' uses the OpenAI-compatible API but the Server URL is blank, so it "
                "would call the real OpenAI cloud and fail for a local model. Set the Server URL "
                "to your local endpoint, e.g. http://127.0.0.1:11441/v1." % model_spec)
            return
        if server_url:
            reachable, why = self._model_reachable(server_url)
            if not reachable:
                slicer.util.errorDisplay(
                    "Can't reach the model server at %s\n(%s).\n\nThe server isn't answering. "
                    "Check it's running AND on this exact port, then confirm by opening\n"
                    "    %s/models\nin a browser - it should return JSON instantly. "
                    "(Your last server came up on port 11440.)" % (server_url, why, server_url.rstrip("/")))
                return
        if not self._ensure_deps():
            return
        try:
            from radassistant_lib.tools import ToolRegistry
            from radassistant_lib.skills import SkillLibrary
            from radassistant_lib.bridge import MainThreadBridge
            from radassistant_deep.agent import AgentConfig
            from radassistant_deep.inprocess import build_inprocess_agent
        except Exception as exc:
            import traceback
            slicer.util.errorDisplay("Failed to load the in-process agent:\n%s" % exc)
            slicer.app.logMessage("[RadAssistantDeep] " + traceback.format_exc())
            return

        try:
            self._registry = ToolRegistry(SkillLibrary(_SKILLS))
            self._bridge = MainThreadBridge()
            self._bridge.start(self._on_ui_event, self._registry.execute)
            config = AgentConfig(
                model=model_spec or None,
                base_url=server_url or None,
                api_key=self.apiKeyEdit.text.strip() or None,
                approval_mode=self.approvalCombo.currentText,
                vision=self.visionCheck.checked,
                skills_dir=_SKILLS,
                subagents_enabled=False,
            )
            self._built = build_inprocess_agent(config, self._registry, executor=self._bridge.run_tool_blocking)
            self._run_config = self._resume_run_config()
        except Exception as exc:
            import traceback
            slicer.util.errorDisplay("Failed to build the agent:\n%s" % exc)
            slicer.app.logMessage("[RadAssistantDeep] " + traceback.format_exc())
            if self._bridge:
                self._bridge.stop()
            self._bridge = None
            return

        self._appendSystem("Connected (in-process) | model %s | approvals %s"
                           % (model_spec, self.approvalCombo.currentText))
        scene = ""
        try:
            scene = (self._registry.execute("get_scene_overview", {}) or {}).get("text", "")
        except Exception:
            pass
        if scene:
            self._appendSystem("Scene: " + scene.splitlines()[0])
        self.connectButton.enabled = False
        self.disconnectButton.enabled = True
        self._set_busy(False)

    # -- thread config (resume last conversation across restarts) ---------------
    def _thread_file(self):
        from radassistant_deep.agent import default_home
        return os.path.join(str(default_home()), "last_thread.txt")

    def _new_thread(self):
        tid = str(uuid.uuid4())
        try:
            p = self._thread_file()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(tid)
        except Exception:
            pass
        return {"configurable": {"thread_id": tid}}

    def _resume_run_config(self):
        try:
            tid = open(self._thread_file(), encoding="utf-8").read().strip()
            if tid:
                return {"configurable": {"thread_id": tid}}
        except Exception:
            pass
        return self._new_thread()

    # -- run a turn on a worker thread -----------------------------------------
    def onSend(self):
        text = self.inputEdit.text.strip()
        if not text or self._built is None or (self._worker and self._worker.is_alive()):
            return
        self.inputEdit.clear()
        self._appendUser(text)
        self._set_busy(True)
        self._stop.clear()
        while not self._decision_q.empty():
            try:
                self._decision_q.get_nowait()
            except Exception:
                break
        from radassistant_deep.inprocess import run_turn
        built, run_config = self._built, self._run_config

        def _work():
            run_turn(built, text, run_config,
                     emit=lambda ev: self._bridge.emit("event", ev),
                     ask=self._ask_from_worker,
                     should_stop=self._stop.is_set)

        self._worker = threading.Thread(target=_work, daemon=True)
        self._worker.start()

    def _ask_from_worker(self, actions):
        """Called on the worker thread at an approval interrupt: show the dialog on
        the main thread and block until the user decides."""
        if not actions:
            return []
        self._bridge.emit("event", {"type": "approval", "actions": actions})
        try:
            return self._decision_q.get(timeout=3600)
        except Exception:
            return None

    # -- main-thread UI event handling -----------------------------------------
    def _on_ui_event(self, kind, payload):
        if kind == "event":
            self._handleEvent(payload)

    def _handleEvent(self, event):
        etype = event.get("type")
        if etype == "thinking_delta":
            if self.thinkingCheck.checked:
                self._stream_delta("thinking", event.get("id", "cur"), event.get("text", ""))
            return
        if etype == "assistant_delta":
            self._stream_delta("assistant", event.get("id", "cur"), event.get("text", ""))
            return
        self._finalize_stream()

        if etype == "tool_call":
            name = event.get("name", "tool")
            args = event.get("args", {})
            arg_hint = ", ".join(f"{k}={v}" for k, v in list(args.items())[:2])
            self._append("🔧 *Calling* `%s`(%s)…" % (name, arg_hint))
        if etype == "tool":
            self._appendTool(event.get("name", "tool"), event.get("text", ""), event.get("error", False))
        elif etype == "todos":
            lines = ["**Plan:**"]
            for t in event.get("todos", []):
                st = t.get("status")
                mark = "☑" if st == "completed" else "▶" if st == "in_progress" else "☐"
                lines.append("- %s %s" % (mark, t.get("content", "")))
            self._append("\n".join(lines))
        elif etype == "approval":
            self._handleApproval(event.get("actions", []))
        elif etype == "stopped":
            self._appendSystem("Stopped.")
        elif etype == "turn_done":
            self._set_busy(False)
        elif etype == "error":
            self._appendSystem("Error: " + event.get("text", ""))

    def _handleApproval(self, actions):
        import json
        decisions = []
        for action in actions:
            name = action.get("name", "?")
            args = json.dumps(action.get("args", {}), indent=2)
            why = action.get("description", "")
            text = ("The agent wants to run:\n\n%s\n\nArguments:\n%s\n\n%s\n\nApprove?"
                    % (name, args, why))
            reply = qt.QMessageBox.question(
                slicer.util.mainWindow(), "RadAssistantDeep - approval required",
                text, qt.QMessageBox.Yes | qt.QMessageBox.No)
            if reply == qt.QMessageBox.Yes:
                decisions.append({"type": "approve"})
                self._appendSystem("Approved: %s" % name)
            else:
                decisions.append({"type": "reject", "message": "User rejected %s." % name})
                self._appendSystem("Rejected: %s" % name)
        self._decision_q.put(decisions)

    def _set_busy(self, busy):
        connected = self._built is not None
        self.inputEdit.enabled = connected and not busy
        self.sendButton.enabled = connected and not busy
        self.stopButton.enabled = connected and busy
        self.newChatButton.enabled = connected and not busy
        if not busy and connected:
            self.inputEdit.setFocus()

    def onStop(self):
        self._stop.set()
        self._decision_q.put(None)  # unblock a pending approval
        self._appendSystem("Stopping...")
        self.stopButton.enabled = False

    def onNewChat(self):
        if self._built is None:
            return
        self._run_config = self._new_thread()
        self.transcript.clear()
        self._appendSystem("New chat. The scene is unchanged; the conversation was reset.")

    def onDisconnect(self):
        self._stop.set()
        self._decision_q.put(None)
        if self._bridge is not None:
            try:
                self._bridge.stop()
            except Exception:
                pass
        self._bridge = None
        self._built = None
        self.connectButton.enabled = True
        self.disconnectButton.enabled = False
        self._set_busy(False)
        self.inputEdit.enabled = False
        self.sendButton.enabled = False
        self.newChatButton.enabled = False
        self._appendSystem("Disconnected.")

    def cleanup(self):
        if getattr(self, "_render_timer", None) is not None:
            self._render_timer.stop()
        self.onDisconnect()
