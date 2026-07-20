"""Unit tests for the deterministic safety policy (port of RadAssistant v2 tests)."""

from radassistant_deep.policy import (
    APPROVAL_MODES,
    DISCLAIMER,
    DiagnosisGuard,
    PHIScrubber,
    approval_tier,
    classify_tool,
    interrupt_config_for_mode,
    scene_terms_from,
    should_ask,
)


class TestClassification:
    def test_read_only(self):
        for name in ("get_scene_overview", "list_segments", "measure_segment_volumes", "read_skill", "task"):
            assert classify_tool(name) == "read_only", name

    def test_reversible_default(self):
        for name in ("threshold_segmentation", "set_window_level", "filter_segment_islands", "place_point"):
            assert classify_tool(name) == "reversible", name

    def test_heavy(self):
        assert classify_tool("run_total_segmentator") == "heavy"
        assert classify_tool("extract_radiomics") == "heavy"
        assert classify_tool("nn_train_model") == "heavy"
        assert classify_tool("ensure_slicer_extension") == "heavy"

    def test_ensure_extension_auto_loads_in_accept_and_auto(self):
        # heavy tier: manual asks, accept/auto do not -> matches "load by itself"
        assert should_ask("manual", approval_tier("ensure_slicer_extension"))
        assert not should_ask("accept", approval_tier("ensure_slicer_extension"))
        assert not should_ask("auto", approval_tier("ensure_slicer_extension"))

    def test_destructive(self):
        assert classify_tool("execute_python") == "destructive"
        assert classify_tool("st_delete_node") == "destructive"  # connector-prefixed
        assert classify_tool("clear_scene") == "destructive"

    def test_phi_egress(self):
        assert classify_tool("web_fetch") == "phi_egress"
        assert classify_tool("web_search") == "phi_egress"
        assert classify_tool("idc_download_series") == "phi_egress"

    def test_tiers(self):
        assert approval_tier("execute_python") == "code"
        assert approval_tier("st_delete_node") == "irreversible"
        assert approval_tier("web_fetch") == "phi_egress"
        assert approval_tier("run_total_segmentator") == "heavy"
        assert approval_tier("get_scene_overview") == "read_only"
        assert approval_tier("threshold_segmentation") == "reversible"


class TestApprovalMatrix:
    def test_trivial_never_asks(self):
        for mode in APPROVAL_MODES:
            assert not should_ask(mode, "read_only")
            assert not should_ask(mode, "reversible")

    def test_auto_never_asks(self):
        for tier in ("heavy", "code", "irreversible", "phi_egress"):
            assert not should_ask("auto", tier)

    def test_accept_asks_only_worst(self):
        assert not should_ask("accept", "heavy")
        assert not should_ask("accept", "code")
        assert should_ask("accept", "irreversible")
        assert should_ask("accept", "phi_egress")

    def test_manual_asks_everything_nontrivial(self):
        for tier in ("heavy", "code", "irreversible", "phi_egress"):
            assert should_ask("manual", tier)

    def test_interrupt_config_compilation(self):
        tools = ["get_scene_overview", "execute_python", "run_total_segmentator", "st_delete_node"]
        manual = interrupt_config_for_mode("manual", tools)
        assert set(manual) == {"execute_python", "run_total_segmentator", "st_delete_node"}
        assert manual["execute_python"]["allowed_decisions"] == ["approve", "reject"]
        accept = interrupt_config_for_mode("accept", tools)
        assert set(accept) == {"st_delete_node"}
        assert interrupt_config_for_mode("auto", tools) == {}


class TestPHIScrubber:
    def test_clean_text_passes(self):
        s = PHIScrubber()
        assert s.is_clean("segment the lungs on CTChest with a -1000 to -400 band")

    def test_mrn_flagged(self):
        findings = PHIScrubber().findings("patient MRN 123456789 chest CT")
        assert any(f.kind == "mrn_like_number" for f in findings)

    def test_date_flagged(self):
        assert not PHIScrubber().is_clean("study from 2024-01-05")

    def test_path_flagged(self):
        assert not PHIScrubber().is_clean(r"load C:\data\patient_scan.nrrd")

    def test_accession_flagged(self):
        assert not PHIScrubber().is_clean("accession ACC20240105X")

    def test_scene_term_flagged(self):
        s = PHIScrubber(scene_terms=("Doe_John_Chest", "CTChest"))
        findings = s.findings("compare against Doe_John_Chest baseline")
        assert any(f.kind == "scene_node_name" for f in findings)
        # common dataset names are never treated as PHI
        assert s.is_clean("the CTChest sample volume")

    def test_scene_terms_extraction(self):
        terms = scene_terms_from("Volume 'CTChest': CT\nSegmentation 'Patient_A_Seg': segments ['Lungs']")
        assert "Patient_A_Seg" in terms and "CTChest" in terms


class TestDiagnosisGuard:
    def test_descriptive_text_untouched(self):
        g = DiagnosisGuard()
        text = "Segmented both lungs; total volume 4.6 L (measured)."
        assert g.enforce(text) == text

    def test_diagnostic_text_gets_disclaimer(self):
        g = DiagnosisGuard()
        for text in (
            "The nodule is malignant.",
            "Findings consistent with adenocarcinoma.",
            "This is stage III disease.",
            "I recommend a biopsy.",
        ):
            out = g.enforce(text)
            assert out.endswith(DISCLAIMER), text
            assert out.startswith(text)

    def test_enforce_idempotent(self):
        g = DiagnosisGuard()
        once = g.enforce("Possibly malignant lesion.")
        assert g.enforce(once) == once
