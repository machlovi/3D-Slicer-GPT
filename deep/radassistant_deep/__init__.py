"""radassistant-deep: RadAssistant's workflow as a LangChain deep agent."""

from .agent import AgentConfig, BuiltAgent, build_agent
from .models import create_model, parse_model_spec
from .policy import (
    DiagnosisGuard,
    PHIScrubber,
    approval_tier,
    classify_tool,
    interrupt_config_for_mode,
    should_ask,
)
from .sessions import MockSlicerSession, ToolOutcome

__all__ = [
    "AgentConfig",
    "BuiltAgent",
    "build_agent",
    "create_model",
    "parse_model_spec",
    "classify_tool",
    "approval_tier",
    "should_ask",
    "interrupt_config_for_mode",
    "PHIScrubber",
    "DiagnosisGuard",
    "MockSlicerSession",
    "ToolOutcome",
]

__version__ = "0.1.0"
