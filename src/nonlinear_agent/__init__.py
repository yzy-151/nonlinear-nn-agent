"""Utilities for the nonlinear neural-network experiment agent."""

from nonlinear_agent.experiment_tools import (
    build_experiment_tool_registry,
    generate_config_tool,
    run_training_tool,
    verify_artifacts_tool,
    write_report_tool,
)
from nonlinear_agent.hooks import HookManager
from nonlinear_agent.llm import FakeLLMClient, OpenAICompatibleClient
from nonlinear_agent.loop import ExperimentPlannerLoop, PlannerLoopResult
from nonlinear_agent.mcp_server import MCPToolBridge, build_mcp_tool_bridge, tool_spec_to_mcp_tool
from nonlinear_agent.planner import ExperimentPlan, ExperimentPlanner, PlannedExperiment
from nonlinear_agent.run_control import RunController
from nonlinear_agent.runtime_errors import ErrorType
from nonlinear_agent.replay import TraceSummary, build_replay_markdown, load_trace_events, summarize_trace, write_replay_report
from nonlinear_agent.runtime import ExperimentHarnessRuntime, HarnessRequest
from nonlinear_agent.server import HarnessRunSpec, build_harness_request, create_app, encode_sse_event, stream_sse_events
from nonlinear_agent.session import ExperimentSession, SessionStore
from nonlinear_agent.tools import RetryPolicy, ToolCall, ToolRegistry, ToolResult
from nonlinear_agent.trace import TraceEvent, TraceLogger

__all__ = [
    "ExperimentHarnessRuntime",
    "ExperimentSession",
    "ExperimentPlan",
    "ExperimentPlanner",
    "ExperimentPlannerLoop",
    "ErrorType",
    "FakeLLMClient",
    "HarnessRequest",
    "HarnessRunSpec",
    "HookManager",
    "OpenAICompatibleClient",
    "MCPToolBridge",
    "PlannedExperiment",
    "PlannerLoopResult",
    "RunController",
    "RetryPolicy",
    "SessionStore",
    "ToolCall",
    "ToolRegistry",
    "ToolResult",
    "TraceEvent",
    "TraceLogger",
    "TraceSummary",
    "build_experiment_tool_registry",
    "build_harness_request",
    "build_mcp_tool_bridge",
    "build_replay_markdown",
    "create_app",
    "encode_sse_event",
    "generate_config_tool",
    "load_trace_events",
    "run_training_tool",
    "stream_sse_events",
    "summarize_trace",
    "tool_spec_to_mcp_tool",
    "verify_artifacts_tool",
    "write_report_tool",
    "write_replay_report",
]


