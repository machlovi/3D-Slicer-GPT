"""Tests for the tool layer, memory port, and the backend-agnostic model factory."""

import pytest

from radassistant_deep.memory import DEFAULT_PERSONA, LearningStore, ensure_persona
from radassistant_deep.models import create_model, parse_model_spec
from radassistant_deep.sessions import MockSlicerSession
from radassistant_deep.testing import ScriptedChatModel
from radassistant_deep.memory_tools import build_memory_tools
from radassistant_deep.slicer_tools import (
    READ_ONLY_TOOL_NAMES,
    SEGMENTATION_TOOL_NAMES,
    build_slicer_tools,
)

EXPECTED_TOOLS = {
    "get_scene_overview", "load_sample_data", "set_window_level", "take_screenshot",
    "list_segments", "threshold_segmentation", "filter_segment_islands",
    "show_segmentation_3d", "measure_segment_volumes", "segment_statistics",
    "run_total_segmentator", "ensure_slicer_extension", "execute_python",
}


class TestSlicerTools:
    def make(self, vision=False):
        session = MockSlicerSession()
        session.load_sample_data("CTChest")
        tools = {t.name: t for t in build_slicer_tools(session, vision=vision)}
        return session, tools

    def test_full_registry_with_descriptions_and_schemas(self):
        _, tools = self.make()
        assert set(tools) == EXPECTED_TOOLS
        for t in tools.values():
            assert t.description.strip(), t.name
            assert t.args_schema is not None, t.name

    def test_prescriptive_descriptions(self):
        _, tools = self.make()
        assert "approval" in tools["execute_python"].description.lower()
        assert "never estimate" in tools["measure_segment_volumes"].description.lower()

    def test_tool_execution_mutates_session(self):
        session, tools = self.make()
        out = tools["threshold_segmentation"].invoke(
            {"volume_name": "CTChest", "segment_name": "Lungs",
             "lower_threshold": -1000, "upper_threshold": -400}
        )
        assert "4600" in out
        assert "Lungs" in session.segmentations["Segmentation"]

    def test_errors_are_strings_with_prefix(self):
        _, tools = self.make()
        out = tools["threshold_segmentation"].invoke(
            {"volume_name": "Ghost", "segment_name": "X",
             "lower_threshold": -100, "upper_threshold": 100}
        )
        assert isinstance(out, str) and out.startswith("Error:") and "Ghost" in out

    def test_screenshot_text_mode(self):
        _, tools = self.make(vision=False)
        out = tools["take_screenshot"].invoke({"view": "3d"})
        assert isinstance(out, str) and "captured" in out

    def test_screenshot_vision_mode_attaches_image_block(self):
        _, tools = self.make(vision=True)
        out = tools["take_screenshot"].invoke({"view": "3d"})
        assert isinstance(out, list) and len(out) == 2
        assert out[0]["type"] == "text"
        assert out[1]["type"] == "image" and out[1]["source_type"] == "base64"
        assert out[1]["mime_type"] == "image/png" and out[1]["data"]

    def test_ensure_extension_tool(self):
        session, tools = self.make()
        out = tools["ensure_slicer_extension"].invoke({"extension_name": "TotalSegmentator"})
        assert "available" in out.lower() or "loaded" in out.lower()
        assert "TotalSegmentator" in getattr(session, "extensions_installed", set())
        bad = tools["ensure_slicer_extension"].invoke({"extension_name": "NopeExt"})
        assert bad.startswith("Error:") and "Known:" in bad

    def test_ensure_extension_description_steers_away_from_code(self):
        _, tools = self.make()
        desc = tools["ensure_slicer_extension"].description.lower()
        assert "execute_python" in desc and "never" in desc

    def test_subagent_tool_subsets_resolve(self):
        _, tools = self.make()
        assert set(READ_ONLY_TOOL_NAMES) <= set(tools)
        assert set(SEGMENTATION_TOOL_NAMES) <= set(tools)
        assert "execute_python" not in READ_ONLY_TOOL_NAMES
        assert "execute_python" not in SEGMENTATION_TOOL_NAMES


class TestMemory:
    def test_persona_created_once(self, tmp_path):
        p = ensure_persona(tmp_path)
        assert p.read_text(encoding="utf-8") == DEFAULT_PERSONA
        p.write_text("# custom rules", encoding="utf-8")
        ensure_persona(tmp_path)
        assert p.read_text(encoding="utf-8") == "# custom rules"

    def test_learning_store_appends_with_clock(self, tmp_path):
        store = LearningStore(workspace=tmp_path, clock=lambda: "2026-07-16 00:00 UTC")
        store.record("radiologist prefers volumes in mL", tag="pref")
        store.record("second\nlearning   collapsed")
        content = store.read_all()
        assert content.splitlines() == [
            "- [2026-07-16 00:00 UTC] pref: radiologist prefers volumes in mL",
            "- [2026-07-16 00:00 UTC] general: second learning collapsed",
        ]

    def test_empty_learning_rejected(self, tmp_path):
        store = LearningStore(workspace=tmp_path)
        assert "Nothing to record" in store.record("   ")
        assert store.read_all() == ""

    def test_record_learning_tool(self, tmp_path):
        store = LearningStore(workspace=tmp_path, clock=lambda: "T")
        (tool,) = build_memory_tools(store)
        out = tool.invoke({"text": "use lung preset for chest CT", "tag": "workflow"})
        assert "workflow" in out
        assert "- [T] workflow: use lung preset for chest CT" in store.read_all()


class TestModelFactory:
    def test_parse_specs(self):
        assert parse_model_spec("ollama:qwen3:14b") == ("ollama", "qwen3:14b")
        assert parse_model_spec("anthropic:claude-opus-4-8") == ("anthropic", "claude-opus-4-8")
        assert parse_model_spec("openai:gpt-5.2") == ("openai", "gpt-5.2")
        assert parse_model_spec("qwen3:14b") == ("ollama", "qwen3:14b")   # bare -> ollama
        assert parse_model_spec("anthropic:") == ("anthropic", "claude-opus-4-8")

    def test_fake_provider(self):
        model = create_model("fake:demo")
        assert isinstance(model, ScriptedChatModel) and len(model.script) == 5
        with pytest.raises(ValueError, match="Unknown fake script"):
            create_model("fake:nope")

    def test_ollama_provider(self):
        from langchain_ollama import ChatOllama

        model = create_model("ollama:testmodel", base_url="http://gpu-node:11434")
        assert isinstance(model, ChatOllama) and model.model == "testmodel"

    def test_openai_provider(self):
        from langchain_openai import ChatOpenAI

        model = create_model("openai:gpt-5.2", api_key="test-key")
        assert isinstance(model, ChatOpenAI)

    def test_anthropic_provider(self):
        from langchain_anthropic import ChatAnthropic

        model = create_model("anthropic:claude-opus-4-8", api_key="test-key")
        assert isinstance(model, ChatAnthropic)
        assert "claude-opus-4-8" in str(model.model)

    def test_env_default(self, monkeypatch):
        monkeypatch.setenv("RADASSISTANT_MODEL", "fake:demo")
        assert isinstance(create_model(), ScriptedChatModel)
