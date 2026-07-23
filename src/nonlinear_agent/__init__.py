"""Utilities for the nonlinear neural-network experiment agent.

The package root keeps exports lazy so lightweight helpers can be imported
without forcing PyTorch and CUDA DLLs to load.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "collect_diagnostics": ("nonlinear_agent.diagnostics", "collect_diagnostics"),
    "render_diagnostics_markdown": ("nonlinear_agent.diagnostics", "render_diagnostics_markdown"),
    "write_diagnostics_report": ("nonlinear_agent.diagnostics", "write_diagnostics_report"),
    "build_experiment_tool_registry": ("nonlinear_agent.experiment_tools", "build_experiment_tool_registry"),
    "generate_config_tool": ("nonlinear_agent.experiment_tools", "generate_config_tool"),
    "run_training_tool": ("nonlinear_agent.experiment_tools", "run_training_tool"),
    "verify_artifacts_tool": ("nonlinear_agent.experiment_tools", "verify_artifacts_tool"),
    "write_report_tool": ("nonlinear_agent.experiment_tools", "write_report_tool"),
    "HookManager": ("nonlinear_agent.hooks", "HookManager"),
    "FakeLLMClient": ("nonlinear_agent.llm", "FakeLLMClient"),
    "OpenAICompatibleClient": ("nonlinear_agent.llm", "OpenAICompatibleClient"),
    "ExperimentPlannerLoop": ("nonlinear_agent.loop", "ExperimentPlannerLoop"),
    "PlannerLoopResult": ("nonlinear_agent.loop", "PlannerLoopResult"),
    "MCPToolBridge": ("nonlinear_agent.mcp_server", "MCPToolBridge"),
    "build_mcp_tool_bridge": ("nonlinear_agent.mcp_server", "build_mcp_tool_bridge"),
    "tool_spec_to_mcp_tool": ("nonlinear_agent.mcp_server", "tool_spec_to_mcp_tool"),
    "ExperimentPlan": ("nonlinear_agent.planner", "ExperimentPlan"),
    "ExperimentPlanner": ("nonlinear_agent.planner", "ExperimentPlanner"),
    "PlannedExperiment": ("nonlinear_agent.planner", "PlannedExperiment"),
    "RunController": ("nonlinear_agent.run_control", "RunController"),
    "ErrorType": ("nonlinear_agent.runtime_errors", "ErrorType"),
    "TraceSummary": ("nonlinear_agent.replay", "TraceSummary"),
    "build_replay_markdown": ("nonlinear_agent.replay", "build_replay_markdown"),
    "load_trace_events": ("nonlinear_agent.replay", "load_trace_events"),
    "summarize_trace": ("nonlinear_agent.replay", "summarize_trace"),
    "write_replay_report": ("nonlinear_agent.replay", "write_replay_report"),
    "ExperimentHarnessRuntime": ("nonlinear_agent.runtime", "ExperimentHarnessRuntime"),
    "HarnessRequest": ("nonlinear_agent.runtime", "HarnessRequest"),
    "HarnessRunSpec": ("nonlinear_agent.server", "HarnessRunSpec"),
    "build_harness_request": ("nonlinear_agent.server", "build_harness_request"),
    "create_app": ("nonlinear_agent.server", "create_app"),
    "encode_sse_event": ("nonlinear_agent.server", "encode_sse_event"),
    "stream_sse_events": ("nonlinear_agent.server", "stream_sse_events"),
    "ExperimentSession": ("nonlinear_agent.session", "ExperimentSession"),
    "SessionStore": ("nonlinear_agent.session", "SessionStore"),
    "RetryPolicy": ("nonlinear_agent.tools", "RetryPolicy"),
    "ToolCall": ("nonlinear_agent.tools", "ToolCall"),
    "ToolRegistry": ("nonlinear_agent.tools", "ToolRegistry"),
    "ToolResult": ("nonlinear_agent.tools", "ToolResult"),
    "TraceEvent": ("nonlinear_agent.trace", "TraceEvent"),
    "TraceLogger": ("nonlinear_agent.trace", "TraceLogger"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
