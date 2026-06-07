"""
Agent Harness 工具调用系统 ============================================

整个文件解决一个问题：LLM 说"我要调工具 X，参数是 Y"，Runtime 怎么安全执行它？

核心流程：
  ToolCall(工具名, 参数) ──传入──▶ ToolRegistry.run() ──返回──▶ ToolResult(成功/失败)

ToolRegistry 负责：查字典找函数 → 异步执行 → 超时保护 → 失败重试 → 结构化返回

适用场景类比：
  你对着智能音箱说"放歌" → ToolCall(name="放歌")
  音箱的 ToolRegistry 找到"播放音乐"这个功能 → 执行 → 返回"播放成功"
  你不需要知道音箱怎么解码音频，只需要知道结果。Agent 也一样。
"""

from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from nonlinear_agent.runtime_errors import ErrorType, classify_exception

# 工具函数的类型注解：接受任意参数，返回任意值
ToolFunction = Callable[..., Any]


# ============================================================
# RetryPolicy — 失败重试策略
# ============================================================
class RetryPolicy(str, Enum):
    """工具执行失败后的重试策略"""
    ALWAYS = "always"           # 无论什么错都重试
    NEVER = "never"             # 从不重试，直接返回失败
    RETRY_TIMEOUT = "retry_timeout"  # 只有超时才重试，其他错误不重试


# ============================================================
# ToolCall — 一次工具调用请求（输入）
# ============================================================
@dataclass(frozen=True)  # frozen=True = 创建后不可修改，防止中途被篡改
class ToolCall:
    """描述一次工具调用的完整请求。

    frozen=True 的含义：ToolCall 是"请求单"，一旦写好就不该再改。
    如果你发现了拼写错误，应该新建一个 ToolCall，而不是修改现有对象。
    """

    name: str                          # 工具名，必须在 ToolRegistry 注册过
    args: dict[str, Any] = field(default_factory=dict)  # 传给工具的参数，比如 {"config_path": "configs/test.yaml"}
    timeout_seconds: float | None = None  # 超时时间，None 则用 Registry 默认值
    retries: int = 0                   # 失败重试次数，0 表示不重试（只执行一次）
    retry_policy: RetryPolicy | str = RetryPolicy.ALWAYS  # 重试策略


# ============================================================
# ToolResult — 一次工具调用的结果（输出）
# ============================================================
@dataclass(frozen=True)
class ToolResult:
    """描述工具执行后的统一返回格式。

    无论工具内部是训练模型还是生成配置，最终都套在这个结构里返回。
    Runtime 不关心工具内部怎么实现，只看 ToolResult 的 status 决定下一步。
    """

    name: str          # 工具名，方便日志追踪
    status: str        # "succeeded" 或 "failed"
    output: dict[str, Any]  # 工具输出，可能包含 metrics、artifacts 等
    attempts: int      # 实际尝试次数（1 = 一次成功，>1 = 重试过）
    latency_ms: float  # 从开始到结束的墙钟时间（无论成功失败），单位毫秒
    error: str | None = None       # 失败时的报错信息
    error_type: str | None = None  # 结构化错误分类，如 timeout_error、tool_error
    retryable: bool = False        # 这次失败还能不能重试


# ============================================================
# ToolSpec — 工具的"说明书"（给 LLM 看的）
# ============================================================
@dataclass(frozen=True)
class ToolSpec:
    """描述一个工具的能力边界。

    相当于家电说明书：名称、用途、需要什么参数、属于哪一类、出错怎么办。
    LLM Planner 读这个来决定"我要调用哪个工具，传什么参数"。
    MCP 协议层也用它来暴露工具列表给外部消费者。
    """

    name: str            # 工具名
    description: str = ""  # 一句话描述，会出现在 Planner prompt 里
    input_schema: dict[str, Any] = field(default_factory=dict)  # 输入参数 JSON Schema，告诉 LLM 要传什么
    category: str = "general"     # 类别，如 "experiment"、"io"，用于分组披露
    error_policy: str = "return_error"  # 失败策略，默认返回结构化错误，不抛异常


# ============================================================
# ToolRegistry — 工具注册中心（核心）
# ============================================================
class ToolRegistry:
    """工具系统的核心调度器。

    职责三件事：
      1. 注册工具：把函数名字和真实函数绑定
      2. 描述工具：给 LLM 看有哪些工具、每个需要什么参数
      3. 执行工具：收到 ToolCall → 找到函数 → 异步执行 → 超时控制 → 重试 → 返回 ToolResult

    架构价值：
      LLM 不能直接调 Python 函数，必须通过 ToolRegistry。
      这是 Agent 的安全边界——你不知道工具怎么实现，但你信任 Registry 会安全执行它们。
    """

    def __init__(self, default_timeout_seconds: float = 30.0, unknown_tool_policy: str = "raise"):
        """
        default_timeout_seconds: 工具默认超时时间（秒），单个 ToolCall 可覆盖
        unknown_tool_policy:
          "raise"         — 调用未注册工具时直接抛异常（严格模式）
          "return_error"  — 调用未注册工具时返回 ToolResult(status="failed")（宽容模式）
        """
        self.default_timeout_seconds = default_timeout_seconds
        self.unknown_tool_policy = unknown_tool_policy
        self._tools: dict[str, ToolFunction] = {}  # 工具名 → 真实函数
        self._specs: dict[str, ToolSpec] = {}       # 工具名 → 说明书

    # ── 注册工具 ──────────────────────────────────────────
    def register(self, name: str, func: ToolFunction, spec: ToolSpec | None = None) -> None:
        """注册一个工具。

        示例：
          registry.register("run_training", training_function,
                            ToolSpec(name="run_training", description="跑训练", ...))
        """
        if not name:
            raise ValueError("Tool name must not be empty.")
        self._tools[name] = func
        self._specs[name] = spec or ToolSpec(name=name)

    def tool_names(self) -> list[str]:
        """返回所有已注册工具的名字"""
        return sorted(self._tools)

    # ── 描述工具 ──────────────────────────────────────────
    def describe_tools(self, category: str | None = None) -> list[dict[str, Any]]:
        """返回工具列表的描述，给 LLM Planner 或 MCP Client 看。

        category=None 时返回所有工具，指定 category 时只返回该类别。
        渐进式披露：Agent 不需要一次看完所有工具，按场景逐步展示。
        """
        specs = [self._specs[name] for name in self.tool_names()]
        if category is not None:
            specs = [spec for spec in specs if spec.category == category]
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
                "category": spec.category,
                "error_policy": spec.error_policy,
            }
            for spec in specs
        ]

    # ── 执行工具（核心） ────────────────────────────────────
    async def run(self, call: ToolCall) -> ToolResult:
        """执行一次工具调用。

        流程：
          1. 查字典找到函数（未知工具 → 根据 unknown_tool_policy 返回错误或抛异常）
          2. 在循环中调用 _invoke()（支持重试）
          3. 每次调用包上 asyncio.wait_for()（超时保护）
          4. 成功 → 返回 ToolResult(status="succeeded", output=...)
          5. 失败 → 根据 RetryPolicy 决定是否重试
          6. 用完所有重试 → 返回 ToolResult(status="failed", error=...)
        """
        # 检查工具是否存在
        if call.name not in self._tools:
            if self.unknown_tool_policy == "return_error":
                return ToolResult(
                    name=call.name,
                    status="failed",
                    output={},
                    attempts=0,
                    latency_ms=0.0,
                    error=f"Unknown tool: {call.name}",
                    error_type=ErrorType.TOOL_ERROR.value,
                    retryable=False,
                )
            raise KeyError(f"Unknown tool: {call.name}")

        timeout = call.timeout_seconds or self.default_timeout_seconds
        attempts = 0
        started = time.perf_counter()  # 高精度计时器（不受系统时间调整影响）
        last_error: BaseException | None = None
        last_error_type: ErrorType | None = None

        # 重试循环：retries=0 → 只执行一次；retries=1 → 最多执行两次
        for attempts in range(1, call.retries + 2):
            try:
                # asyncio.wait_for() 包一层超时保护：
                # 如果 _invoke() 在 timeout 秒内没完成，自动抛 asyncio.TimeoutError
                output = await asyncio.wait_for(
                    self._invoke(self._tools[call.name], call.args),
                    timeout=timeout,
                )

                # 规范化输出：统一转成 dict，方便后续代码处理
                if output is None:
                    payload: dict[str, Any] = {}
                elif isinstance(output, dict):
                    payload = output
                else:
                    payload = {"value": output}

                return ToolResult(
                    name=call.name,
                    status="succeeded",
                    output=payload,
                    attempts=attempts,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )

            except Exception as exc:
                # 捕获所有异常（包含 TimeoutError 和工具内部错误）
                # 不吞掉——记录到 ToolResult 里作为可观测的失败
                last_error = exc
                last_error_type = classify_exception(exc)

                # 判断是否还需要重试：次数够了吗？策略允许吗？
                if attempts >= call.retries + 1 or not _should_retry(call.retry_policy, last_error_type):
                    break
                # 否则继续重试循环

        # 所有重试耗尽 → 返回结构化失败结果
        return ToolResult(
            name=call.name,
            status="failed",
            output={},
            attempts=attempts,
            latency_ms=(time.perf_counter() - started) * 1000,
            error=str(last_error),
            error_type=(last_error_type or ErrorType.TOOL_ERROR).value,
            retryable=False,
        )

    # ── 内部：异步执行函数 ──────────────────────────────────
    async def _invoke(self, func: ToolFunction, args: dict[str, Any]) -> Any:
        """真正执行工具函数的地方。

        分两种情况：
          - async def 函数 → 直接 await（本身就在事件循环里跑）
          - 普通 def 函数  → 丢到 asyncio.to_thread()（在独立线程里跑，不阻塞主线程）

        为什么要区分？
          普通函数（如训练脚本、子进程调用）会阻塞。
          直接调会卡死整个服务，其他请求全等。
          asyncio.to_thread() 把它丢到线程池，主线程继续处理 SSE 推送、health check 等。
        """
        if inspect.iscoroutinefunction(func):
            # async def → 直接 await，在事件循环里跑
            return await func(**args)
        # 普通 def → 丢到独立线程，不阻塞主线程
        return await asyncio.to_thread(func, **args)


# ============================================================
# _should_retry — 判断是否该重试
# ============================================================
def _should_retry(policy: RetryPolicy | str, error_type: ErrorType) -> bool:
    """根据重试策略和错误类型决定是否重试。

    三种策略：
      ALWAYS        → 什么错都重试
      NEVER         → 从不重试
      RETRY_TIMEOUT → 只有超时错误才重试（其他错误说明不是临时的）
    """
    policy_value = policy.value if isinstance(policy, RetryPolicy) else str(policy)
    if policy_value == RetryPolicy.NEVER.value:
        return False
    if policy_value == RetryPolicy.RETRY_TIMEOUT.value:
        return error_type == ErrorType.TIMEOUT_ERROR
    return True
