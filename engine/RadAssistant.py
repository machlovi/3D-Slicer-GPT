"""RadAssistant — an open, agentic natural-language assistant for 3D Slicer.

MIT licensed. Backend-agnostic: point it at a local model on your own HPC via
Ollama, any OpenAI-compatible server (vLLM/TGI/LM Studio), or the Anthropic
cloud. The agent runs a real tool-use loop against the *validated* Slicer tools
the radiologist already trusts — it orchestrates, it does not reimplement.

Install: Slicer → Edit ▸ Application Settings ▸ Modules ▸ Additional module
paths → add this folder → Restart. Appears under Modules ▸ Utilities.
"""

import os

import ctk
import qt
import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleWidget,
)

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

SYSTEM_PROMPT = """You are RadAssistant, an AI assistant embedded inside 3D Slicer, the open-source
medical imaging platform. You help clinicians — mostly radiologists — drive Slicer through natural
language, so they never have to hunt through menus.

CORE PRINCIPLE — ORCHESTRATE VALIDATED TOOLS, NEVER IMPROVISE CLINICAL LOGIC
- You act by calling tools that drive Slicer's real, validated modules and extensions (the Segment
  Editor effects, TotalSegmentator, SegmentStatistics, volume rendering). You are the hands that
  click the buttons a radiologist would click — you are NOT a segmentation algorithm.
- Prefer a validated automatic tool (e.g. TotalSegmentator) over a manual primitive whenever one
  exists. When you must use a primitive like thresholding, state the method and its limitations in
  the same sentence as the result.
- For accuracy-critical interaction, SET UP the real tool and hand the precise work to the human
  ("I've activated Grow-from-seeds — paint your seeds and say 'done'"). The clinician owns the
  pixels; you own the plumbing.
- Never state a measurement you did not compute with a tool. No invented numbers, ever.

HOW YOU WORK
- A `<scene_context>` block at the top of each user message says what is loaded. Trust it.
- {verification}
- Workflow skills are listed below. When a request matches one, call `read_skill` FIRST and follow it.
- Chain tools to finish a request end to end; don't stop mid-way to ask permission for reversible
  viewing actions.
- RENDER vs SEGMENT — do not confuse them. "show / render / visualize / display X" means a fast
  VOLUME RENDERING: ONE `enable_volume_rendering` call with a preset (CT-Bone, CT-Lung, CT-Cardiac,
  MR-Default) — a display effect, no labelmap, no islands, no measuring. Only SEGMENT
  (`threshold_segmentation` / `run_total_segmentator`) when the user says "segment", "measure",
  "quantify", or asks for a volume/number. NEVER start a segmentation workflow when the user only
  asked to SEE something.
- Extensions are installed by the USER, not by you. If a tool reports an extension (TotalSegmentator,
  PyRadiomics, …) is missing, tell the user to install it from Slicer's Extensions Manager and
  restart, then STOP. NEVER try to install an extension with execute_python.
- `take_screenshot` is SLOW (the model must encode the image). Use it to verify a genuinely VISUAL
  result or to answer "what do you see" — NOT after every step. Prefer structured tools
  (`list_segments`, `measure_segment_volumes`) for verification.
- Prefer a dedicated tool over `execute_python` (which requires the user to approve the code).
  NEVER hand-write VTK/Slicer segmentation code — use threshold_segmentation, filter_segment_islands,
  run_total_segmentator, show_segmentation_3d, measure_segment_volumes. If a task needs an extension
  that isn't installed, say so and stop; do not reimplement it in Python. If an execute_python call
  errors, do not keep trying variants — switch to a dedicated tool or ask the user.
- NEVER use execute_python to move the 3D camera, rebuild a surface, or fix how something LOOKS. Use
  center_views / rotate_3d_view / show_segmentation_3d. If the 3D STILL looks wrong (blocky, inside-out,
  empty) after those, it is a DATA problem (e.g. external air in the segment), NOT a rendering bug —
  stop and report it; do not hand-roll VTK to "rebuild" it.
- Sanity-check every measurement against physiology before reporting it. If a value is implausible
  (a "lung" > 7 L, a "kidney" > 500 mL, a "merge the two largest islands" lung > 10 L, etc.), do NOT
  state it as fact — flag it and explain the likely cause (usually the segment includes unintended
  tissue, most often air outside the patient), then offer the clean path (e.g. TotalSegmentator).

TALKING TO CLINICIANS
- Lead with the outcome ("Lungs segmented — 4.2 L total"), then the detail and any caveat.
- Use radiology vocabulary (HU, window/level, axial/coronal/sagittal, RAS), not software jargon.
- Be brief. State uncertainty plainly.

CLINICAL SAFETY — NON-NEGOTIABLE
- Research/visualization aid, NOT a diagnostic device. Never diagnose, never suggest treatment,
  never call a finding benign or malignant. You may DESCRIBE what is visible and MEASURE it;
  interpretation belongs to the physician. If asked to diagnose, say so and offer to measure instead.
- Ask before anything destructive (deleting nodes, clearing the scene, overwriting files).

AVAILABLE SKILLS
{skills}
"""

VERIFY_VISION = (
    "YOU CAN SEE. After any visual change (segmentation, 3D render, window/level, layout), call "
    "`take_screenshot` and actually look at the result before telling the user it worked. If it "
    "looks wrong, fix it and look again.")
VERIFY_TEXT = (
    "YOU CANNOT SEE IMAGES with this model. Verify every change with STRUCTURED tools instead — "
    "`get_scene_overview`, `list_segments`, `measure_segment_volumes`, `get_cursor_info`. A result "
    "is only confirmed when a tool reports the expected node/segment/volume. Never claim a visual "
    "outcome you have not verified numerically.")


class RadAssistant(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "RadAssistant"
        # Hidden from the module selector on purpose (like Talk2View): RadAssistant lives in an
        # always-on right-side dock created at startup. Keeping it out of the selector stops
        # Slicer's module panel from "stealing" the chat widget into the LEFT panel when the
        # module is clicked. Reach it via the dock, the toolbar button, or View ▸ RadAssistant chat.
        self.parent.categories = []
        self.parent.dependencies = []
        self.parent.contributors = ["RadAssistant contributors"]
        self.parent.helpText = (
            "Natural-language agentic assistant for 3D Slicer. Bring your own model "
            "(local via Ollama / OpenAI-compatible, or Anthropic cloud). It drives Slicer's "
            "validated tools and shows its work.\n\nResearch/visualization aid — not a "
            "diagnostic device.")
        self.parent.acknowledgementText = "Built on 3D Slicer. MIT licensed."
        _icon = os.path.join(MODULE_DIR, "Resources", "Icons", "RadAssistant.png")
        if os.path.exists(_icon):
            self.parent.icon = qt.QIcon(_icon)

        # Make RadAssistant load on EVERY restart ("install once" behaviour): register its
        # own directory in Slicer's permanent module search paths the first time it runs, so
        # it never has to be re-added by hand — the same net effect as an installed extension.
        self._ensure_persistent_module_path()

        # Pop the chat up as a right-side dock panel on every launch, so RadAssistant
        # behaves like an always-available assistant rather than a module you must open.
        slicer.app.connect("startupCompleted()", self._auto_show_chat_dock)
        # If the module is loaded AFTER startup already finished (e.g. via the Extension
        # Wizard mid-session), startupCompleted() won't fire again — so also try on the
        # next event-loop turn. Dock creation is idempotent, so this never double-adds.
        qt.QTimer.singleShot(0, self._auto_show_chat_dock)

    def _ensure_persistent_module_path(self):
        """Add this module's own directory to Slicer's permanent additional module paths
        (idempotent). After the first load — however it happened (Extension Wizard, a manual
        path, etc.) — RadAssistant then loads automatically on every subsequent start.

        Dev-only: when RadAssistant is installed as a real extension (from the Extensions
        Manager) Slicer already manages its path, so we must NOT touch the user's
        AdditionalPaths — that would leave a stale entry behind after an uninstall. We detect
        that case and skip, so the same code is safe both locally and once published."""
        try:
            mine = os.path.normcase(os.path.normpath(MODULE_DIR))
            for base_attr in ("extensionsInstallPath", "slicerHome"):
                base = getattr(slicer.app, base_attr, "") or ""
                if base and mine.startswith(os.path.normcase(os.path.normpath(base))):
                    return  # installed extension / built-in location — leave settings alone
            settings = slicer.app.revisionUserSettings()
            key = "Modules/AdditionalPaths"
            raw = settings.value(key)
            if raw is None:
                raw_list = []
            elif isinstance(raw, str):
                raw_list = [raw]
            else:
                raw_list = [str(p) for p in raw]
            absolute = list(slicer.app.toSlicerHomeAbsolutePaths(raw_list))
            have = [os.path.normcase(os.path.normpath(p)) for p in absolute]
            mine = os.path.normcase(os.path.normpath(MODULE_DIR))
            if mine not in have:
                absolute.append(MODULE_DIR)
                settings.setValue(key, slicer.app.toSlicerHomeRelativePaths(absolute))
        except Exception as exc:  # never let this break module loading
            import logging
            logging.warning("RadAssistant: could not persist the module path: %s" % exc)

    def _auto_show_chat_dock(self):
        """Dock the RadAssistant chat on the right of the main window at startup.
        Mirrors Talk2View's approach. Safe no-op when running headless (no main window)."""
        try:
            main_window = slicer.util.mainWindow()
            if main_window is None:
                return  # headless / test run — nothing to show
            existing = main_window.findChild("QDockWidget", "RadAssistantDockWidget")
            if existing is not None:
                existing.setVisible(True)
                existing.raise_()
                return
            widget = slicer.modules.radassistant.widgetRepresentation()
            if widget is None:
                return
            dock = qt.QDockWidget("RadAssistant", main_window)
            dock.setObjectName("RadAssistantDockWidget")
            dock.setWidget(widget)
            dock.setMinimumWidth(380)
            dock.setFeatures(qt.QDockWidget.DockWidgetFloatable | qt.QDockWidget.DockWidgetMovable)
            main_window.addDockWidget(qt.Qt.RightDockWidgetArea, dock)

            # View-menu toggle so it can be reopened after being closed.
            action = dock.toggleViewAction()
            action.setText("RadAssistant chat")
            action.setToolTip("Show/hide the RadAssistant assistant panel")
            if self.parent.icon and not self.parent.icon.isNull():
                action.setIcon(self.parent.icon)
            view_menu = main_window.findChild("QMenu", "menuView")
            if view_menu:
                view_menu.addAction(action)
            # Toolbar button for a one-click toggle (parity with Talk2View).
            for toolbar in main_window.findChildren("QToolBar"):
                if toolbar.objectName == "MainToolBar":
                    toolbar.addAction(action)
                    break

            # Always show it on startup (Talk2View behaviour). We deliberately do NOT persist a
            # hidden state: on a normal shutdown/restore Slicer fires an involuntary hide, which
            # would otherwise be saved as "off" and make the panel vanish on the next launch
            # (the "shows once then disappears" bug). The user can still close it for the current
            # session or reopen it via View ▸ RadAssistant chat / the toolbar button.
            dock.setVisible(True)
            dock.raise_()
        except Exception as exc:  # never let this break Slicer startup
            import logging
            logging.warning("RadAssistant: could not create the chat dock panel: %s" % exc)


class RadAssistantLogic(ScriptedLoadableModuleLogic):
    """Settings persistence."""

    def s(self):
        return slicer.app.userSettings()

    def get(self, key, default):
        return self.s().value("RadAssistant/" + key, default)

    def set(self, key, value):
        self.s().setValue("RadAssistant/" + key, value)

    def api_key(self, provider=""):
        p = (provider or self.get("provider", "ollama")).lower()
        key_in_settings = self.get("apiKey", "").strip()
        if key_in_settings:
            return key_in_settings
        if p in ("openai_cloud", "openai_official", "openai"):
            return os.environ.get("OPENAI_API_KEY") or os.environ.get("UV_API_KEY", "")
        if p == "anthropic":
            return os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("UV_API_KEY", "")
        if p == "gemini":
            return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("UV_API_KEY", "")
        return (os.environ.get("OPENAI_API_KEY") or
                os.environ.get("UV_API_KEY") or
                os.environ.get("ANTHROPIC_API_KEY") or
                os.environ.get("GEMINI_API_KEY") or
                os.environ.get("GOOGLE_API_KEY", ""))

    def backend_config(self):
        provider = self.get("provider", "ollama")
        default_url = "https://api.openai.com/v1" if provider == "openai_cloud" else "http://localhost:8000/v1"
        return {
            "provider": provider,
            "model": self.get("model", "qwen2.5:14b"),
            "host": self.get("serverUrl", "http://localhost:11434"),
            "base_url": self.get("serverUrl", default_url),
            "api_key": self.api_key(provider),
            "effort": self.get("effort", "high"),
            "vision": self.get("vision", "false") == "true",
            "num_ctx": int(self.get("numCtx", 16384)),
        }


class RadAssistantWidget(ScriptedLoadableModuleWidget):

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        self.logic = RadAssistantLogic()

        from radassistant_lib.bridge import MainThreadBridge
        from radassistant_lib.skills import SkillLibrary
        from radassistant_lib.tools import ToolRegistry

        self.skills = SkillLibrary(os.path.join(MODULE_DIR, "skills"))
        self.tools = ToolRegistry(self.skills)
        self.bridge = MainThreadBridge()
        self.agent = None

        from radassistant_lib import logbook
        logbook.setup()   # start the detailed session log (tool timings, model latency, errors)
        self.recorder = None

        self._transcript = []
        self._streaming_text = ""
        self._thinking_text = ""
        self._render_pending = False
        self._busy = False

        self._build_setup_section()
        self._build_chat_section()

        self._render_timer = qt.QTimer()
        self._render_timer.setInterval(120)
        self._render_timer.connect("timeout()", self._render_if_needed)
        self._render_timer.start()

        self.bridge.start(self._on_agent_event, self.tools.execute)
        self._on_provider_changed(self.providerCombo.currentText)

        self._append("**RadAssistant** is ready. Pick a backend in Setup, then try:\n\n"
                     "- *Load a chest CT and set a lung window*\n"
                     "- *Segment the lungs, show them in 3D, and tell me the volumes*\n"
                     "- *What am I looking at?*\n\n"
                     "_Research/visualization aid — not for diagnosis._")

    # -- Setup UI ------------------------------------------------------------

    def _build_setup_section(self):
        box = ctk.ctkCollapsibleButton()
        box.text = "Setup — choose your model backend"
        box.collapsed = bool(self.logic.get("provider", ""))
        self.layout.addWidget(box)
        form = qt.QFormLayout(box)

        self.providerCombo = qt.QComboBox()
        self.providerCombo.addItem("Ollama (local / HPC)", "ollama")
        self.providerCombo.addItem("OpenAI Cloud (gpt-4o, etc.)", "openai_cloud")
        self.providerCombo.addItem("Gemini (free — Google cloud)", "gemini")
        self.providerCombo.addItem("OpenAI-compatible (vLLM / TGI / LM Studio)", "openai")
        self.providerCombo.addItem("Anthropic (cloud)", "anthropic")
        want = self.logic.get("provider", "ollama")
        for i in range(self.providerCombo.count):
            if self.providerCombo.itemData(i) == want:
                self.providerCombo.setCurrentIndex(i)
        self.providerCombo.connect("currentIndexChanged(int)", lambda _i: self._on_provider_changed())
        form.addRow("Backend:", self.providerCombo)

        self.serverEdit = qt.QLineEdit(self.logic.get("serverUrl", "http://localhost:11434"))
        self.serverEdit.connect("editingFinished()", self._save_and_rebuild)
        self.serverRow = form.rowCount()
        form.addRow("Server URL:", self.serverEdit)

        self.modelEdit = qt.QLineEdit(self.logic.get("model", "qwen2.5:14b"))
        self.modelEdit.setPlaceholderText("e.g. llama3.3, qwen2.5:32b, gpt-4o, claude-3-7-sonnet")
        self.modelEdit.connect("editingFinished()", self._save_and_rebuild)
        form.addRow("Model:", self.modelEdit)

        self.apiKeyEdit = qt.QLineEdit()
        self.apiKeyEdit.setEchoMode(qt.QLineEdit.Password)
        self.apiKeyEdit.setText(self.logic.get("apiKey", ""))
        self.apiKeyEdit.setPlaceholderText("sk-… or env var fallback")
        self.apiKeyEdit.connect("editingFinished()", self._save_and_rebuild)
        form.addRow("API key:", self.apiKeyEdit)

        self.effortCombo = qt.QComboBox()
        self.effortCombo.addItems(["low", "medium", "high", "xhigh"])
        self.effortCombo.setCurrentText(self.logic.get("effort", "high"))
        self.effortCombo.connect("currentTextChanged(QString)", lambda _s: self._save_and_rebuild())
        form.addRow("Reasoning effort:", self.effortCombo)

        self.visionCheck = qt.QCheckBox("This model can see images (vision)")
        self.visionCheck.setChecked(self.logic.get("vision", "false") == "true")
        self.visionCheck.toolTip = ("Most strong local tool-calling models are text-only. Leave "
                                    "OFF unless your model reads images (e.g. Qwen3-VL, Llama 4). "
                                    "When off, the agent verifies with structured scene-state.")
        self.visionCheck.connect("toggled(bool)", lambda _b: self._save_and_rebuild())
        form.addRow(self.visionCheck)

        self.installButton = qt.QPushButton("Install Python packages")
        self.installButton.toolTip = ("Ollama needs nothing extra. Anthropic needs 'anthropic'. "
                                      "Voice (optional) needs sounddevice + faster-whisper.")
        self.installButton.connect("clicked()", self._on_install_clicked)
        form.addRow(self.installButton)

        self.setupNote = qt.QLabel("")
        self.setupNote.setWordWrap(True)
        form.addRow(self.setupNote)

        self.capabilityNote = qt.QLabel("")
        self.capabilityNote.setWordWrap(True)
        form.addRow(self.capabilityNote)

    def _on_provider_changed(self, _text=None):
        provider = self.providerCombo.currentData
        is_ollama = provider == "ollama"
        is_openai_local = provider == "openai"
        is_openai_cloud = provider == "openai_cloud"
        is_anthropic = provider == "anthropic"
        is_gemini = provider == "gemini"

        self.serverEdit.setEnabled(is_ollama or is_openai_local or is_openai_cloud)
        self.apiKeyEdit.setEnabled(is_anthropic or is_openai_local or is_openai_cloud or is_gemini)
        self.effortCombo.setEnabled(is_anthropic)
        self.visionCheck.setEnabled(is_ollama or is_openai_local or is_openai_cloud or is_gemini)

        # Update API key placeholder based on provider
        if is_openai_cloud:
            self.apiKeyEdit.setPlaceholderText("sk-proj-… (or set OPENAI_API_KEY env var)")
        elif is_anthropic:
            self.apiKeyEdit.setPlaceholderText("sk-ant-… (or set ANTHROPIC_API_KEY env var)")
        elif is_gemini:
            self.apiKeyEdit.setPlaceholderText("AIzaSy… (or set GEMINI_API_KEY env var)")
        else:
            self.apiKeyEdit.setPlaceholderText("optional for local servers")

        # sensible default server URL when the field is empty or clearly wrong
        if is_ollama and (":8000" in self.serverEdit.text or "api.openai.com" in self.serverEdit.text or not self.serverEdit.text):
            self.serverEdit.setText("http://localhost:11434")
        elif is_openai_local and (":11434" in self.serverEdit.text or "api.openai.com" in self.serverEdit.text or not self.serverEdit.text):
            self.serverEdit.setText("http://localhost:8000/v1")
        elif is_openai_cloud and (":11434" in self.serverEdit.text or ":8000" in self.serverEdit.text or not self.serverEdit.text):
            self.serverEdit.setText("https://api.openai.com/v1")

        # sensible default model when switching providers
        model = self.modelEdit.text.strip()
        if is_ollama and (not model or model.startswith(("gemini", "claude", "gpt-4"))):
            self.modelEdit.setText("qwen2.5:14b")
        elif is_openai_cloud and (not model or not model.startswith("gpt-")):
            self.modelEdit.setText("gpt-4o")
        elif is_gemini and not model.startswith("gemini"):
            self.modelEdit.setText("gemini-2.0-flash")
        elif is_anthropic and not model.startswith("claude"):
            self.modelEdit.setText("claude-3-7-sonnet-20250219")

        notes = {
            "ollama": "Point Server URL at your Ollama host. On the HPC set OLLAMA_HOST=0.0.0.0 "
                      "and use http://&lt;hpc-address&gt;:11434. Use a tool-capable model "
                      "(qwen2.5, llama3.1/3.3, mistral-nemo, gpt-oss). No API key, no cloud, "
                      "data stays on your machine.",
            "openai_cloud": "Official OpenAI Cloud (gpt-4o, gpt-4o-mini, o3-mini). Enter your "
                            "OpenAI API key (sk-...) or export OPENAI_API_KEY before starting Slicer. "
                            "Multimodal, so vision can be enabled.",
            "openai": "For local vLLM / TGI / LM Studio. Server URL should end in /v1. API key only if "
                      "the server requires authentication.",
            "anthropic": "Best vision + reasoning. Needs the 'anthropic' package "
                         "(Install button) and a key (sk-ant-...) or ANTHROPIC_API_KEY env var.",
            "gemini": "Google Gemini via its OpenAI-compatible API. Enter your Gemini API key "
                      "(or GEMINI_API_KEY / GOOGLE_API_KEY env var); a good model is gemini-2.0-flash.",
        }
        self.setupNote.setText("<small>" + notes[provider] + "</small>")
        self._save_and_rebuild()

    def _save_and_rebuild(self):
        self.logic.set("provider", self.providerCombo.currentData)
        self.logic.set("serverUrl", self.serverEdit.text.strip())
        self.logic.set("model", self.modelEdit.text.strip())
        self.logic.set("apiKey", self.apiKeyEdit.text.strip())
        self.logic.set("effort", self.effortCombo.currentText)
        self.logic.set("vision", "true" if self.visionCheck.checked else "false")
        self.agent = None  # rebuilt on next send

        from radassistant_lib.backends import capability_warning
        warn = capability_warning(self.providerCombo.currentData, self.modelEdit.text.strip())
        self.capabilityNote.setText(f"<small style='color:#c60'>{warn}</small>" if warn else "")

    def _on_install_clicked(self):
        provider = self.providerCombo.currentData
        if provider == "anthropic":
            self.setupNote.setText("Installing 'anthropic'…")
            slicer.app.processEvents()
            try:
                slicer.util.pip_install("anthropic")
            except Exception as exc:
                slicer.util.errorDisplay(f"Failed to install 'anthropic': {exc}")
                return
        if slicer.util.confirmYesNoDisplay(
                "Install local voice input (sounddevice + faster-whisper)?\n\n"
                "Optional; downloads a few hundred MB; enables offline dictation."):
            slicer.app.processEvents()
            try:
                slicer.util.pip_install("sounddevice faster-whisper")
            except Exception as exc:
                slicer.util.errorDisplay(f"Voice packages failed: {exc}")
        from radassistant_lib import voice
        self.micButton.setVisible(voice.is_available())
        self.setupNote.setText("Packages installed. Ready.")

    # -- chat UI -------------------------------------------------------------

    def _build_chat_section(self):
        box = ctk.ctkCollapsibleButton()
        box.text = "Assistant"
        self.layout.addWidget(box)
        column = qt.QVBoxLayout(box)

        self.chatView = qt.QTextBrowser()
        self.chatView.setOpenExternalLinks(True)
        self.chatView.setMinimumHeight(420)
        column.addWidget(self.chatView)

        self.statusLabel = qt.QLabel("Ready.")
        self.statusLabel.setStyleSheet("color: gray;")
        column.addWidget(self.statusLabel)

        input_row = qt.QHBoxLayout()
        self.inputEdit = qt.QLineEdit()
        self.inputEdit.setPlaceholderText("Ask for anything — e.g. “segment the lungs and measure them”")
        self.inputEdit.connect("returnPressed()", self._on_send_clicked)
        input_row.addWidget(self.inputEdit)

        from radassistant_lib import voice
        self.micButton = qt.QPushButton("🎤")
        self.micButton.setCheckable(True)
        self.micButton.toolTip = "Hold to dictate (local, offline transcription)"
        self.micButton.setFixedWidth(40)
        self.micButton.setVisible(voice.is_available())
        self.micButton.connect("toggled(bool)", self._on_mic_toggled)
        input_row.addWidget(self.micButton)

        self.sendButton = qt.QPushButton("Send")
        self.sendButton.setStyleSheet("font-weight: bold;")
        self.sendButton.connect("clicked()", self._on_send_clicked)
        input_row.addWidget(self.sendButton)

        self.stopButton = qt.QPushButton("⏹ Stop")
        self.stopButton.toolTip = ("Interrupt the running response (thinking or between tool "
                                   "steps) so you can type a new prompt.")
        self.stopButton.setEnabled(False)
        self.stopButton.connect("clicked()", self._on_stop_clicked)
        input_row.addWidget(self.stopButton)
        column.addLayout(input_row)

        button_row = qt.QHBoxLayout()
        self.newChatButton = qt.QPushButton("New chat")
        self.newChatButton.connect("clicked()", self._on_new_chat_clicked)
        button_row.addWidget(self.newChatButton)

        self.selfTestButton = qt.QPushButton("Self-test")
        self.selfTestButton.toolTip = ("Run the Slicer-side tools directly (no model or HPC "
                                       "tunnel needed) and report which pass/fail. Run on a "
                                       "fresh scene.")
        self.selfTestButton.connect("clicked()", self._run_self_test)
        button_row.addWidget(self.selfTestButton)

        self.logsButton = qt.QPushButton("📁 Logs")
        self.logsButton.toolTip = ("Open the folder with detailed session logs — per-tool "
                                   "timings (find what's freezing the UI), model latency, and errors.")
        self.logsButton.connect("clicked()", self._on_open_logs)
        button_row.addWidget(self.logsButton)

        button_row.addWidget(qt.QLabel("Approvals:"))
        self.approvalCombo = qt.QComboBox()
        for label, val in (("Manual", "manual"), ("Accept", "accept"), ("Auto", "auto")):
            self.approvalCombo.addItem(label, val)
        saved_mode = self.logic.get("approvalMode", "manual")
        self.approvalCombo.setCurrentIndex(max(0, self.approvalCombo.findData(saved_mode)))
        self.approvalCombo.toolTip = (
            "Manual: confirm each risky action. Accept: auto-run code & long compute, "
            "still confirm deletes and web access. Auto: run everything without asking "
            "(patient data still never leaves the machine).")
        self.approvalCombo.connect("currentIndexChanged(int)", self._on_approval_changed)
        self.tools.approval_mode = saved_mode
        button_row.addWidget(self.approvalCombo)

        self.thinkingCheck = qt.QCheckBox("Show thinking")
        button_row.addWidget(self.thinkingCheck)
        button_row.addStretch()
        column.addLayout(button_row)

        self.layout.addStretch(1)

    # -- agent lifecycle -----------------------------------------------------

    def _ensure_agent(self):
        if self.agent is not None:
            return True
        config = self.logic.backend_config()
        if config["provider"] == "anthropic" and not config["api_key"]:
            slicer.util.errorDisplay("Set your Anthropic API key in Setup (or export "
                                     "ANTHROPIC_API_KEY before launching Slicer).")
            return False
        if config["provider"] in ("openai_cloud", "openai_official") and not config["api_key"]:
            slicer.util.errorDisplay("Set your OpenAI API key in Setup (or export "
                                     "OPENAI_API_KEY before launching Slicer).")
            return False
        if config["provider"] == "gemini" and not config["api_key"]:
            slicer.util.errorDisplay("Set your Gemini API key in Setup (or export "
                                     "GEMINI_API_KEY / GOOGLE_API_KEY before launching Slicer).")
            return False
        try:
            from radassistant_lib.backends import build_backend
            backend = build_backend(config)
        except Exception as exc:
            slicer.util.errorDisplay(f"Could not build backend: {exc}")
            return False

        from radassistant_lib.agent import AssistantAgent
        self.tools.vision_available = bool(backend.capabilities.vision)
        verification = VERIFY_VISION if backend.capabilities.vision else VERIFY_TEXT
        system = SYSTEM_PROMPT.format(verification=verification,
                                      skills=self.skills.list_for_prompt())
        self.agent = AssistantAgent(self.bridge, self.tools.definitions, system, backend)
        self.agent.start()
        self.statusLabel.setText(f"Backend: {backend.capabilities.name}")
        return True

    def _on_send_clicked(self):
        text = self.inputEdit.text.strip()
        if not text or self._busy:
            return
        if not self._ensure_agent():
            return
        self.inputEdit.clear()
        self._append(f"**You:** {text}")
        self._streaming_text = ""
        self._thinking_text = ""
        self.tools.begin_turn()   # reset per-turn safety counters (execute_python cap)
        self._set_busy(True)
        self.agent.send_user_message(text)

    def _on_stop_clicked(self):
        if self.agent is not None and self._busy:
            self.agent.interrupt()
            self.stopButton.setEnabled(False)
            self.statusLabel.setText("Stopping…")

    def _on_open_logs(self):
        from radassistant_lib import logbook
        target = logbook.log_dir() or ""
        try:
            qt.QDesktopServices.openUrl(qt.QUrl.fromLocalFile(target))
        except Exception:
            slicer.util.infoDisplay(f"Detailed logs are written to:\n{logbook.log_path()}")

    def _run_self_test(self):
        """Exercise the Slicer-side tools directly (bypassing the LLM) so a first
        run on a new machine shows exactly which tools work. No model/tunnel needed."""
        steps = [
            ("get_scene_overview", {}),
            ("load_sample_data", {"name": "MRHead"}),
            ("get_scene_overview", {}),
            ("set_window_level", {"window": 500, "level": 250}),
            ("set_layout", {"layout": "four_up"}),
            ("center_views", {}),
            ("take_screenshot", {"view": "full"}),
            ("place_point", {"r": 0, "a": 0, "s": 0, "label": "selftest"}),
            ("measure_distance", {"point1": [0, 0, 0], "point2": [10, 0, 0], "label": "selftest"}),
            ("threshold_segmentation", {"segment_name": "selftest_seg",
                                        "lower_threshold": 30, "upper_threshold": 100000}),
            ("measure_segment_volumes", {}),
            ("measure_segment_statistics", {}),
        ]
        self.statusLabel.setText("Running self-test…")
        slicer.app.processEvents()
        previous_vision = self.tools.vision_available
        self.tools.vision_available = True   # so the screenshot step actually captures

        lines = ["**Self-test** — Slicer tools run directly (no model needed):", ""]
        passed = 0
        for name, args in steps:
            try:
                result = self.tools.execute(name, args)
                ok = not result.get("is_error")
                summary = (result.get("text", "") or "").strip().replace("\n", " ")[:110]
            except Exception as exc:
                ok, summary = False, f"exception: {exc}"
            passed += 1 if ok else 0
            lines.append(f"{'✅' if ok else '❌'} `{name}` — {summary}")
            self.statusLabel.setText(f"Self-test… {name}")
            slicer.app.processEvents()

        self.tools.vision_available = previous_vision
        lines += ["", f"**{passed}/{len(steps)} passed.** TotalSegmentator and radiomics need "
                  "their extensions and aren't in this test. Re-run after **New chat** on a fresh "
                  "scene (the measure steps expect exactly one segmentation)."]
        self._append("\n".join(lines))
        self.statusLabel.setText(f"Self-test: {passed}/{len(steps)} passed.")

    def _on_new_chat_clicked(self):
        if self.agent is not None:
            self.agent.reset_conversation()
        self._transcript = []
        self._streaming_text = ""
        self._thinking_text = ""
        self._append("_New conversation started._")

    def _on_approval_changed(self, _idx):
        mode = self.approvalCombo.currentData
        self.logic.set("approvalMode", mode)
        self.tools.approval_mode = mode      # live: execute_python reads this on the next call
        self.statusLabel.setText(f"Approvals: {mode}")

    def _on_mic_toggled(self, checked):
        from radassistant_lib.voice import VoiceRecorder
        if self.recorder is None:
            self.recorder = VoiceRecorder(self.bridge)
        if checked:
            self.statusLabel.setText("🎤 Listening… click again to stop.")
            try:
                self.recorder.start()
            except Exception as exc:
                slicer.util.errorDisplay(f"Microphone error: {exc}")
                self.micButton.setChecked(False)
        else:
            self.statusLabel.setText("Transcribing…")
            self.recorder.stop()

    def _set_busy(self, busy):
        self._busy = busy
        self.sendButton.setEnabled(not busy)
        self.stopButton.setEnabled(busy)
        self.inputEdit.setEnabled(not busy)
        self.statusLabel.setText("Working…" if busy else "Ready.")

    # -- events (already on the main thread) ---------------------------------

    def _on_agent_event(self, kind, payload):
        if kind == "status":
            self.statusLabel.setText(str(payload))
        elif kind == "assistant_delta":
            self._streaming_text += payload
            self._render_pending = True
        elif kind == "thinking_delta":
            self._thinking_text += payload
            if self.thinkingCheck.checked:
                self._render_pending = True
        elif kind == "tool_start":
            self._flush_streaming()
            args = payload.get("input", {})
            # show ALL args (so a hidden one like volume_name can't cause confusion),
            # truncating any long value (e.g. execute_python code) to stay readable
            parts = []
            for k, v in args.items():
                r = repr(v)
                parts.append(f"{k}={r if len(r) <= 60 else r[:57] + '…'}")
            self._append(f"`⚙ {payload['name']}({', '.join(parts)})`")
            self.statusLabel.setText(f"Running {payload['name']}…")
        elif kind == "tool_end":
            dur = payload.get("duration_ms", 0)
            if not payload.get("ok"):
                self._append(f"`  ↳ ⚠ {payload.get('summary', '')}`")
            elif dur >= 1500:   # surface slow tools so a UI freeze is visible + explained
                self._append(f"`  ↳ took {dur / 1000:.1f}s`")
        elif kind == "turn_done":
            self._flush_streaming()
            self._set_busy(False)
            usage = payload or {}
            if usage:
                self.statusLabel.setText(
                    f"Ready.  ({usage.get('input', 0)} in / {usage.get('output', 0)} out"
                    + (f", {usage.get('cache_read', 0)} cached" if usage.get('cache_read') else "")
                    + " tokens)")
        elif kind == "error":
            self._flush_streaming()
            self._append(f"⚠️ **{payload}**")
            self._set_busy(False)
        elif kind == "interrupted":
            self._flush_streaming()
            self._append("⏹ _Stopped._")
        elif kind == "vision_failed":
            # Agent healed a "server can't read images" rejection: stop capturing
            # screenshots for this session and surface what happened in the chat.
            self.tools.vision_available = False
            self._flush_streaming()
            self._append(f"⚠️ *{payload}*")
        elif kind == "transcript":
            self.micButton.setChecked(False)
            self.statusLabel.setText("Ready.")
            if payload:
                self.inputEdit.setText(payload)
                self._on_send_clicked()

    # -- rendering -----------------------------------------------------------

    def _append(self, markdown):
        self._transcript.append(markdown)
        self._render_pending = True

    def _flush_streaming(self):
        if self._streaming_text.strip():
            self._transcript.append("**RadAssistant:** " + self._streaming_text.strip())
        self._streaming_text = ""
        self._thinking_text = ""
        self._render_pending = True

    def _render_if_needed(self):
        if not self._render_pending:
            return
        self._render_pending = False
        parts = list(self._transcript)
        if self.thinkingCheck.checked and self._thinking_text.strip():
            parts.append("> 💭 *" + self._thinking_text.strip().replace("\n", " ") + "*")
        if self._streaming_text.strip():
            parts.append("**RadAssistant:** " + self._streaming_text.strip())
        self.chatView.setMarkdown("\n\n".join(parts))
        scrollbar = self.chatView.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum)

    def cleanup(self):
        self._render_timer.stop()
        self.bridge.stop()
        if self.agent is not None:
            self.agent.request_stop()
            self.agent = None
