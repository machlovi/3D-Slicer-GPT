"""End-to-end agent-loop tests with a scripted model and mock Slicer scene.

This is the deep-agent analog of RadAssistant's test_executor.py: the full
workflow — plan (todos), ground (scene reminder), execute (tools), verify
(measurements), report — driven deterministically.
"""

from conftest import run, tool_messages

from radassistant_deep.memory import DEFAULT_PERSONA
from radassistant_deep.testing import ai


def lung_script():
    return [
        ai(
            "Planning.",
            tool_calls=[{
                "name": "write_todos",
                "args": {"todos": [
                    {"content": "Threshold lungs; verify volume 1000-8000 mL", "status": "in_progress"},
                    {"content": "Report measured volume", "status": "pending"},
                ]},
            }],
        ),
        ai(tool_calls=[{"name": "get_scene_overview", "args": {}}]),
        ai(tool_calls=[{
            "name": "threshold_segmentation",
            "args": {"volume_name": "CTChest", "segment_name": "Lungs",
                     "lower_threshold": -1000, "upper_threshold": -400},
        }]),
        ai(tool_calls=[{"name": "measure_segment_volumes", "args": {}}]),
        ai("Lungs segmented; measured total volume 4600 mL (includes trachea)."),
    ]


class TestFullWorkflow:
    def test_plan_execute_verify_report(self, make_agent, session):
        built, model = make_agent(lung_script())
        result = run(built, "Segment both lungs and report the volume.")

        # planning: todos landed in state
        assert result["todos"][0]["content"].startswith("Threshold lungs")

        # execution: each scripted tool ran against the mock scene
        assert [c[0] for c in session.calls].count("threshold_segmentation") == 1
        assert "Lungs" in session.segmentations["Segmentation"]

        # verification: measurement result fed back to the model
        vols = tool_messages(result, "measure_segment_volumes")
        assert vols and "Lungs | 4600.0" in vols[0].content

        # report: final message is the scripted conclusion
        assert result["messages"][-1].content.startswith("Lungs segmented")

    def test_scene_reminder_grounds_the_turn(self, make_agent):
        built, model = make_agent(lung_script())
        run(built, "Segment both lungs.")
        first_call = model.calls[0]
        reminders = [m for m in first_call if "scene_context" in str(getattr(m, "content", ""))]
        assert reminders, "scene system-reminder missing from model input"
        assert "CTChest" in str(reminders[0].content)
        assert "<system-reminder>" in str(reminders[0].content)

    def test_system_prompt_composition(self, make_agent):
        built, model = make_agent(lung_script())
        run(built, "Segment both lungs.")
        system = str(model.calls[0][0].content)
        assert "Principle 0" in system                       # doctrine
        assert "YOU CANNOT SEE IMAGES" in system             # text verification variant
        assert "lung-segmentation" in system                 # skill metadata (progressive disclosure)
        assert DEFAULT_PERSONA.splitlines()[0].lstrip("# ") in system  # persona memory

    def test_vision_variant_swaps_verification_channel(self, make_agent):
        built, model = make_agent([ai("ok")], vision=True)
        run(built, "hello")
        system = str(model.calls[0][0].content)
        assert "YOU CAN SEE" in system and "YOU CANNOT SEE IMAGES" not in system

    def test_harness_tools_all_bound(self, make_agent):
        built, model = make_agent([ai("ok")])
        run(built, "hello")
        bound = set(model.bound_tools[0])
        # deepagents harness capabilities
        assert {"write_todos", "task", "ls", "read_file", "write_file"} <= bound
        # RadAssistant tool registry
        assert {"get_scene_overview", "threshold_segmentation", "execute_python", "record_learning"} <= bound

    def test_multi_turn_state_persists_on_thread(self, make_agent, session):
        script = [
            ai(tool_calls=[{"name": "threshold_segmentation",
                            "args": {"volume_name": "CTChest", "segment_name": "Lungs",
                                     "lower_threshold": -1000, "upper_threshold": -400}}]),
            ai("Created the Lungs segment."),
            ai(tool_calls=[{"name": "measure_segment_volumes", "args": {}}]),
            ai("Volume is 4600 mL."),
        ]
        built, model = make_agent(script)
        run(built, "Segment the lungs.", thread="chat")
        result2 = run(built, "Now measure it.", thread="chat")
        # second turn still sees the first turn's history
        human_texts = [str(m.content) for m in result2["messages"] if getattr(m, "type", "") == "human"]
        assert any("Segment the lungs." in t for t in human_texts)
        assert result2["messages"][-1].content == "Volume is 4600 mL."

    def test_agent_stops_when_script_exhausted(self, make_agent):
        built, model = make_agent([])  # model immediately returns exhausted_reply
        result = run(built, "hello")
        assert result["messages"][-1].content == "Done."
