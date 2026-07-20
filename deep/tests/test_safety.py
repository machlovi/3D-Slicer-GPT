"""Safety rails end-to-end: approval interrupts, PHI denial, circuit breaker, output rail."""

from langchain_core.tools import tool
from langgraph.types import Command

from conftest import run, tool_messages

from radassistant_deep.middleware import CIRCUIT_BREAKER_MESSAGE, MAX_CONSECUTIVE_EXEC_FAILURES
from radassistant_deep.policy import DISCLAIMER
from radassistant_deep.testing import ai


def exec_call(code: str):
    return ai(tool_calls=[{"name": "execute_python", "args": {"code": code}}])


class TestApprovalInterrupts:
    def test_manual_mode_pauses_and_reject_reaches_model(self, make_agent, session):
        script = [exec_call("print('hi')"), ai("Understood, I will not run code.")]
        built, model = make_agent(script, approval_mode="manual")

        result = run(built, "Run some python.", thread="hitl")
        # paused before execution
        interrupts = result.get("__interrupt__")
        assert interrupts, "expected a human-in-the-loop interrupt"
        request = interrupts[0].value
        assert request["action_requests"][0]["name"] == "execute_python"
        assert session.exec_log == []  # nothing ran

        # human rejects with a reason
        resumed = built.agent.invoke(
            Command(resume={"decisions": [{"type": "reject", "message": "No code today, use dedicated tools."}]}),
            config={"configurable": {"thread_id": "hitl"}},
        )
        assert session.exec_log == []
        rejections = [m for m in tool_messages(resumed) if "No code today" in str(m.content)]
        assert rejections, "rejection message should be fed back as a tool result"
        assert resumed["messages"][-1].content == "Understood, I will not run code."

    def test_manual_mode_approve_executes(self, make_agent, session):
        script = [exec_call("print('hi')"), ai("Ran it.")]
        built, model = make_agent(script, approval_mode="manual")
        result = run(built, "Run some python.", thread="hitl2")
        assert result.get("__interrupt__")
        resumed = built.agent.invoke(
            Command(resume={"decisions": [{"type": "approve"}]}),
            config={"configurable": {"thread_id": "hitl2"}},
        )
        assert session.exec_log == ["print('hi')"]
        assert resumed["messages"][-1].content == "Ran it."

    def test_manual_mode_gates_heavy_tools_too(self, make_agent):
        script = [ai(tool_calls=[{"name": "run_total_segmentator", "args": {"volume_name": "CTChest"}}]), ai("done")]
        built, _ = make_agent(script, approval_mode="manual")
        result = run(built, "Segment everything.", thread="heavy")
        assert result.get("__interrupt__")
        assert result["__interrupt__"][0].value["action_requests"][0]["name"] == "run_total_segmentator"

    def test_accept_mode_runs_code_without_pause(self, make_agent, session):
        script = [exec_call("print('hi')"), ai("done")]
        built, _ = make_agent(script, approval_mode="accept")
        result = run(built, "Run some python.")
        assert not result.get("__interrupt__")
        assert session.exec_log == ["print('hi')"]

    def test_accept_mode_still_gates_irreversible(self, make_agent):
        @tool
        def delete_node(name: str) -> str:
            """Delete a node from the scene permanently."""
            return f"deleted {name}"

        script = [ai(tool_calls=[{"name": "delete_node", "args": {"name": "CTChest"}}]), ai("done")]
        built, _ = make_agent(script, approval_mode="accept", extra_tools=[delete_node])
        result = run(built, "Delete the volume.", thread="del")
        assert result.get("__interrupt__")
        assert result["__interrupt__"][0].value["action_requests"][0]["name"] == "delete_node"

    def test_auto_mode_never_pauses(self, make_agent, session):
        script = [
            exec_call("print('hi')"),
            ai(tool_calls=[{"name": "run_total_segmentator", "args": {"volume_name": "CTChest"}}]),
            ai("done"),
        ]
        built, _ = make_agent(script, approval_mode="auto")
        result = run(built, "Do it all.")
        assert not result.get("__interrupt__")
        assert session.exec_log == ["print('hi')"]
        assert "TotalSegmentator" in session.segmentations


class TestPHIDenial:
    def make_egress_tool(self):
        seen = []

        @tool
        def web_fetch(url: str, query: str = "") -> str:
            """Fetch a documentation page from the web."""
            seen.append((url, query))
            return "fetched"

        return web_fetch, seen

    def test_phi_in_egress_args_is_hard_denied(self, make_agent):
        web_fetch, seen = self.make_egress_tool()
        script = [
            ai(tool_calls=[{
                "name": "web_fetch",
                "args": {"url": "https://radiopaedia.org", "query": "patient MRN 123456789 lung nodule"},
            }]),
            ai("I removed the identifier."),
        ]
        # even in auto mode: deny beats every approval mode
        built, _ = make_agent(script, approval_mode="auto", extra_tools=[web_fetch])
        result = run(built, "Look this up.")
        assert seen == [], "egress tool must never execute with PHI in args"
        denials = tool_messages(result, "web_fetch")
        assert denials and denials[0].status == "error"
        assert "PHI" in str(denials[0].content) and "mrn_like_number" in str(denials[0].content)
        assert built.policy.denials and built.policy.denials[0][0] == "web_fetch"

    def test_clean_egress_args_pass_policy(self, make_agent):
        web_fetch, seen = self.make_egress_tool()
        script = [
            ai(tool_calls=[{"name": "web_fetch", "args": {"url": "https://radiopaedia.org", "query": "hounsfield scale"}}]),
            ai("done"),
        ]
        built, _ = make_agent(script, approval_mode="auto", extra_tools=[web_fetch])
        run(built, "Look up the HU scale.")
        assert seen == [("https://radiopaedia.org", "hounsfield scale")]


class TestCircuitBreaker:
    def test_execute_python_blocked_after_three_consecutive_failures(self, make_agent, session):
        script = [exec_call("boom()") for _ in range(MAX_CONSECUTIVE_EXEC_FAILURES + 1)] + [ai("Switching to dedicated tools.")]
        built, _ = make_agent(script, approval_mode="auto")
        result = run(built, "Keep trying code.")
        # first three attempts executed (and failed); the fourth was blocked
        assert len(session.exec_log) == MAX_CONSECUTIVE_EXEC_FAILURES
        blocked = [m for m in tool_messages(result, "execute_python") if CIRCUIT_BREAKER_MESSAGE[:40] in str(m.content)]
        assert blocked, "fourth attempt should be blocked by the circuit breaker"
        assert built.policy.exec_fail_streak == MAX_CONSECUTIVE_EXEC_FAILURES

    def test_successful_dedicated_tool_resets_streak(self, make_agent, session):
        script = [
            exec_call("boom()"),
            exec_call("boom()"),
            ai(tool_calls=[{"name": "get_scene_overview", "args": {}}]),  # success resets
            exec_call("print('ok')"),
            ai("done"),
        ]
        built, _ = make_agent(script, approval_mode="auto")
        run(built, "Mixed attempts.")
        assert built.policy.exec_fail_streak == 0
        assert len(session.exec_log) == 3  # all three exec attempts ran (no block)


class TestDiagnosisRail:
    def test_disclaimer_appended_to_diagnostic_final_text(self, make_agent):
        script = [ai("The nodule is malignant and likely stage II.")]
        built, _ = make_agent(script)
        result = run(built, "What do you see?")
        final = result["messages"][-1].content
        assert final.startswith("The nodule is malignant")
        assert final.endswith(DISCLAIMER)

    def test_descriptive_text_untouched(self, make_agent):
        script = [ai("Measured lung volume is 4600 mL; segmentation shown in 3D.")]
        built, _ = make_agent(script)
        result = run(built, "Report.")
        assert DISCLAIMER not in result["messages"][-1].content
