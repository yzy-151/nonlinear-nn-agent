"""Utilities for the nonlinear neural-network experiment agent."""

from nonlinear_agent.experiment_tools import (
    build_experiment_tool_registry,
    generate_config_tool,
    run_training_tool,
    verify_artifacts_tool,
    write_report_tool,
)
from nonlinear_agent.hooks import HookManager
from nonlinear_agent.replay import TraceSummary, build_replay_markdown, load_trace_events, summarize_trace, write_replay_report
from nonlinear_agent.runtime import ExperimentHarnessRuntime, HarnessRequest
from nonlinear_agent.session import ExperimentSession, SessionStore
from nonlinear_agent.tools import ToolCall, ToolRegistry, ToolResult
from nonlinear_agent.trace import TraceEvent, TraceLogger

__all__ = [
    "ExperimentHarnessRuntime",
    "ExperimentSession",
    "HarnessRequest",
    "HookManager",
    "SessionStore",
    "ToolCall",
    "ToolRegistry",
    "ToolResult",
    "TraceEvent",
    "TraceLogger",
    "TraceSummary",
    "build_experiment_tool_registry",
    "build_replay_markdown",
    "generate_config_tool",
    "load_trace_events",
    "run_training_tool",
    "summarize_trace",
    "verify_artifacts_tool",
    "write_report_tool",
    "write_replay_report",
]
