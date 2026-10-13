"""Throwaway manual end-to-end test script (NOT part of the pytest suite).

Exercises the offline build_agent() assembly path against a locally running
OpenAI-compatible model server (llama.cpp-style), using the deterministic
MockSlicerSession described in deep/README.md's "Offline tests / dev" section.

Run with the deep/ venv:
    .venv\\Scripts\\python.exe manual_test_run.py
"""

from __future__ import annotations

import sys
import traceback

from radassistant_deep.agent import AgentConfig, build_agent


def _print_message(msg) -> None:
    role = getattr(msg, "type", None) or msg.__class__.__name__
    content = getattr(msg, "content", None)
    tool_calls = getattr(msg, "tool_calls", None)
    tool_call_id = getattr(msg, "tool_call_id", None)
    additional_kwargs = getattr(msg, "additional_kwargs", None)
    response_metadata = getattr(msg, "response_metadata", None)
    usage_metadata = getattr(msg, "usage_metadata", None)

    print(f"--- role={role!r} ---")
    if tool_call_id:
        print(f"  tool_call_id: {tool_call_id}")
    if isinstance(content, list):
        for block in content:
            print(f"  content-block: {block}")
    else:
        print(f"  content: {content!r}")
    if tool_calls:
        for tc in tool_calls:
            print(f"  tool_call: name={tc.get('name')!r} args={tc.get('args')!r} id={tc.get('id')!r}")
    if additional_kwargs:
        print(f"  additional_kwargs: {additional_kwargs}")
    if response_metadata:
        print(f"  response_metadata: {response_metadata}")
    if usage_metadata:
        print(f"  usage_metadata: {usage_metadata}")
    print()


def main() -> int:
    config = AgentConfig(
        model="openai:qwen-vision",
        base_url="http://127.0.0.1:11441/v1",
        api_key="sk-no-auth",
        approval_mode="accept",
        subagents_enabled=False,
        # session left as None -> defaults to MockSlicerSession()
    )

    print("Building agent with config:", config)
    built = build_agent(config)
    print("Agent built OK. Session type:", type(built.session).__name__)
    print("Tools loaded:", [t.name for t in built.tools])
    print()

    query = "Load the CTChest sample and tell me what's loaded."
    print(f"Invoking agent with query: {query!r}\n")

    result = built.agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
        config={"configurable": {"thread_id": "test-1"}},
    )

    print("=" * 70)
    print("FULL MESSAGE LIST")
    print("=" * 70)
    messages = result.get("messages", [])
    for m in messages:
        _print_message(m)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
