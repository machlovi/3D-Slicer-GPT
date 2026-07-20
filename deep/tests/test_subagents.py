"""Subagent delegation: the single deep agent deploys specialists on demand."""

from conftest import run, tool_messages

from radassistant_deep.testing import ai


class TestDelegation:
    def test_task_tool_runs_scene_explorer_in_isolation(self, make_agent, session):
        script = [
            # main agent delegates
            ai(tool_calls=[{
                "name": "task",
                "args": {
                    "description": "Inventory the scene and report exact volumes.",
                    "subagent_type": "scene-explorer",
                },
            }]),
            # scene-explorer subagent (same scripted model, isolated context)
            ai(tool_calls=[{"name": "get_scene_overview", "args": {}}]),
            ai("EXPLORER REPORT: one CT volume 'CTChest', no segmentations."),
            # main agent concludes with the subagent's report
            ai("Delegation complete: scene contains one CT volume."),
        ]
        built, model = make_agent(script)
        result = run(built, "What is in the scene? Use a subagent.")

        # the task tool returned the subagent's final report to the orchestrator
        reports = tool_messages(result, "task")
        assert reports and "EXPLORER REPORT" in str(reports[0].content)

        # the subagent actually exercised the shared Slicer session
        assert ("scene_overview", {}) in [(c, a) for c, a in session.calls]

        # isolation: the subagent got its own system prompt, not the main history
        sub_call = model.calls[1]
        sub_system = str(sub_call[0].content)
        assert "read-only reconnaissance" in sub_system
        assert all("Use a subagent" not in str(m.content) for m in sub_call)

        # the subagent's toolset is the read-only subset
        sub_bound = model.bound_tools[1]
        assert "get_scene_overview" in sub_bound
        assert "threshold_segmentation" not in sub_bound
        assert "execute_python" not in sub_bound

        assert result["messages"][-1].content.startswith("Delegation complete")

    def test_roster_advertised_to_orchestrator(self, make_agent):
        built, model = make_agent([ai("ok")])
        run(built, "hello")
        # the task tool's description enumerates the available specialists
        task_tool = next(
            t for t in model.bound_tool_objects[0] if getattr(t, "name", "") == "task"
        )
        desc = task_tool.description
        for name in ("scene-explorer", "segmentation-specialist", "verifier", "general-purpose"):
            assert name in desc, name

    def test_unknown_subagent_type_is_reported_not_fatal(self, make_agent):
        script = [
            ai(tool_calls=[{"name": "task", "args": {"description": "x", "subagent_type": "chef"}}]),
            ai("Recovered."),
        ]
        built, model = make_agent(script)
        result = run(built, "do something odd")
        msgs = tool_messages(result, "task")
        assert msgs and "cannot invoke subagent chef" in str(msgs[0].content)
        assert result["messages"][-1].content == "Recovered."

    def test_verifier_subagent_audits_with_read_only_tools(self, make_agent, session):
        session.threshold_segmentation("CTChest", "Lungs", -1000, -400)
        script = [
            ai(tool_calls=[{
                "name": "task",
                "args": {
                    "description": "Verify: segment 'Lungs' exists with volume 1000-8000 mL.",
                    "subagent_type": "verifier",
                },
            }]),
            ai(tool_calls=[{"name": "measure_segment_volumes", "args": {}}]),
            ai("Criterion: Lungs volume 4600 mL in [1000, 8000] -> PASS\nVERDICT: PASS"),
            ai("Verified: the segmentation meets the acceptance criteria."),
        ]
        built, model = make_agent(script)
        result = run(built, "Verify the finished segmentation.")
        reports = tool_messages(result, "task")
        assert "VERDICT: PASS" in str(reports[0].content)
        sub_system = str(model.calls[1][0].content)
        assert "The implementer is an LLM" in sub_system

    def test_specialist_roster_can_be_disabled(self, make_agent):
        built, model = make_agent([ai("ok")], subagents=False)
        run(built, "hello")
        # the harness keeps its built-in general-purpose subagent + task tool;
        # disabling removes only our specialist roster
        task_tool = next(
            t for t in model.bound_tool_objects[0] if getattr(t, "name", "") == "task"
        )
        assert "general-purpose" in task_tool.description
        for name in ("scene-explorer", "segmentation-specialist", "verifier"):
            assert name not in task_tool.description, name
