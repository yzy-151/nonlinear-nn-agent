"""
实验工具封装 =========================================================

把真实非线性拟合实验流程拆成 4 个可注册工具，接入 Agent 工具系统。

这 4 个工具构成了 Agent 视角下的"一次完整实验"：
  generate_config → run_training → verify_artifacts → write_report

===============================================================
直接调脚本 vs 封装成 Tool：核心区别
===============================================================

直接调脚本：
  subprocess.run(["python", "train.py", "--config", "xxx.yaml"])
  → 只有 stdout/stderr/returncode
  → 没有结构化错误分类
  → 没有超时控制
  → 没有重试策略
  → LLM 无法理解"这个脚本能干什么、需要什么参数"

封装成 Tool：
  ToolCall(name="run_training", args={"config_path": "xxx.yaml"})
    → ToolRegistry.run(call)
      → 真实函数执行
    → ToolResult(status, output, error_type, latency_ms)
  → 所有结果通过 ToolSpec 向 LLM 披露
  → 超时/重试由 ToolRegistry 统一管理
  → 错误被分类（timeout_error / tool_error / metric_threshold_error）
  → LLM 看到 ToolSpec 就知道能用什么工具、传什么参数

一句话：
  直接调脚本 = 你自己去厨房炒菜，每一步手动操作
  封装成 Tool = 菜单上的"宫保鸡丁"，你只需要点菜，厨房按标准流程出菜

对面试的价值：
  这展示了"把真实业务能力封装为 Agent 可调用工具"的能力——
  不是用 curl 调 API，而是理解工具系统的边界、schema、错误策略和可观测性。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from functools import partial
from pathlib import Path
from typing import Any

import yaml

from nonlinear_agent.agent_workflow import parse_metrics_stdout
from nonlinear_agent.tools import ToolRegistry, ToolSpec


# ============================================================
# 路径工具函数
# ============================================================

def _resolve(workspace: Path | str, path: Path | str) -> Path:
    """把相对路径转成绝对路径。

    例如：workspace="D:/project", path="configs/test.yaml"
         → "D:/project/configs/test.yaml"

    如果 path 已经是绝对路径 → 直接返回。
    """
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(workspace) / candidate


def _relative(path: Path, workspace: Path | str) -> str:
    """把绝对路径转成相对于 workspace 的路径。

    例如：workspace="D:/project", path="D:/project/configs/test.yaml"
         → "configs/test.yaml"

    用于 artifacts 列表和报告——相对路径更短、可移植。
    """
    root = Path(workspace)
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


# ============================================================
# 工具 1：generate_config — 生成实验配置文件
# ============================================================

def generate_config_tool(
    workspace: Path | str,
    base_config_path: Path | str,
    experiment_id: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """读取基础 YAML 配置 + 合并 Planner 参数覆写 → 写入新配置文件。

    流程：
      1. 读取 base YAML（如 lstsq-complexmp-o12-m150.yaml）
      2. 把 overrides 合并进去（如 model_type=complex_lstsq, memory_depth=220）
      3. 写入 configs/{experiment_id}.yaml

    为什么用 YAML 而不是 JSON？
      训练脚本（experiment.py）历史上就用 YAML 配置，保持兼容。

    返回：
      - config_path: 生成的配置文件路径
      - artifacts: 文件列表（供 trace 记录）
      - context_summary: 一句话说明（供 LLM 下一轮理解）
    """
    root = Path(workspace)
    base_path = _resolve(root, base_config_path)
    config = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
    config.update(overrides or {})

    config_dir = root / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{experiment_id}.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    return {
        "config_path": _relative(config_path, root),
        "artifacts": [_relative(config_path, root)],
        "context_summary": f"Generated config for {experiment_id}: {_relative(config_path, root)}",
    }


# ============================================================
# 工具 2：run_training — 执行训练
# ============================================================

def run_training_tool(
    workspace: Path | str,
    config_path: Path | str,
    command: list[str] | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """调用 train.py 执行训练，捕获所有输出。

    流程：
      1. 构造命令：python examples/nonlinear_fit/train.py --config <config_path>
      2. subprocess.run() 执行（同步阻塞，外层 ToolRegistry 会丢到线程池）
      3. 捕获 stdout / stderr / returncode / elapsed time
      4. 读取结果 metrics.json 和产物文件

    为什么不直接在进程里调 Python 函数，而要走 subprocess？
      - 进程隔离：训练崩溃不会拖垮 Agent 服务
      - 和 CLI 行为一致：保证"Agent 调的"和"手跑的"结果是同一个训练逻辑
      - 可替换：command 参数允许换不同的训练脚本

    返回：
      - metrics: 解析后的指标字典
      - artifacts: 产物文件列表
      - stdout_tail / stderr_tail: 输出尾部（太长会截断）
      - elapsed_seconds: 训练耗时
      - context_summary: 一行结论
    """
    root = Path(workspace)
    resolved_config = _resolve(root, config_path)

    # 默认命令：当前 Python 解释器 + 训练脚本 + 配置路径
    command_to_run = command or [
        sys.executable,                        # 当前 Python 解释器
        "examples/nonlinear_fit/train.py",     # 训练脚本
        "--config",
        _relative(resolved_config, root),      # 配置文件（相对路径）
    ]

    started = time.perf_counter()
    # subprocess.run() 是同步阻塞的——外层 ToolRegistry._invoke()
    # 会通过 asyncio.to_thread() 把它丢到独立线程，不阻塞主线程
    result = subprocess.run(
        command_to_run,
        cwd=root,              # 在项目根目录执行
        text=True,             # 以文本模式捕获输出（非 bytes）
        capture_output=True,   # 捕获 stdout 和 stderr
        check=False,           # 返回码非零不抛异常（我们自己处理）
        timeout=timeout_seconds,  # 超时保护（subprocess 层面）
    )
    elapsed = time.perf_counter() - started

    # 训练失败 → 抛异常，把 stdout/stderr 包含在错误信息里
    # 外层 ToolRegistry 会捕获并包装成 ToolResult(status="failed")
    if result.returncode != 0:
        raise RuntimeError(
            "Training command failed "
            f"with return code {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    # 训练成功 → 解析指标和产物
    config = yaml.safe_load(resolved_config.read_text(encoding="utf-8")) or {}
    output_dir = str(config.get("output_dir", ""))
    metrics = _load_metrics(root, output_dir, result.stdout)
    artifacts = _collect_artifacts(root, output_dir)

    return {
        "metrics": metrics,
        "artifacts": artifacts,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],   # 只保留最后 2000 字符
        "stderr_tail": result.stderr[-2000:],   # 同上
        "elapsed_seconds": elapsed,
        "context_summary": (
            f"Training finished in {elapsed:.2f}s "
            f"with NMSE {metrics.get('nmse_db', 'unknown')} dB."
        ),
    }


# ============================================================
# 工具 3：verify_artifacts — 验证实验结果
# ============================================================

def verify_artifacts_tool(
    workspace: Path | str,
    output_dir: Path | str,
    nmse_threshold_db: float,
) -> dict[str, Any]:
    """检查训练结果是否有效：metrics.json 存在？PSD 图存在？NMSE 达标？

    这是 Agent 的"质检环节"——不是训练跑完就完了，还要检查结果是否符合预期。

    失败情况：
      - metrics.json 或 psd.png 不存在 → FileNotFoundError
      - NMSE 不达标 → RuntimeError（Trigger: metric_threshold_error）
      → 这些异常会被 ToolRegistry 捕获并结构化记录

    对 Agent 的意义：
      如果 NMSE 不达标，这个工具返回失败。
      Runtime 记录 error event，Planner 下一轮能看到"上次阈值没达标"。
      这就是 plan-run-observe 闭环中的"observe"环节。
    """
    root = Path(workspace)
    resolved_output = _resolve(root, output_dir)

    metrics_path = resolved_output / "metrics.json"
    psd_path = resolved_output / "psd.png"

    if not metrics_path.exists():
        raise FileNotFoundError(f"Missing metrics file: {metrics_path}")
    if not psd_path.exists():
        raise FileNotFoundError(f"Missing PSD image: {psd_path}")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if "nmse_db" not in metrics:
        raise RuntimeError("metrics.json does not contain nmse_db.")

    nmse = float(metrics["nmse_db"])

    # NMSE 越小越好，如果 > 阈值 → 不达标 → 抛异常
    if nmse > nmse_threshold_db:
        raise RuntimeError(
            f"NMSE {nmse:.4f} dB did not meet threshold {nmse_threshold_db:.4f} dB."
        )

    artifacts = [_relative(metrics_path, root), _relative(psd_path, root)]
    return {
        "metrics": {"nmse_db": nmse},
        "artifacts": artifacts,
        "context_summary": (
            f"NMSE {nmse:.4f} dB meets threshold {nmse_threshold_db:.4f} dB; "
            f"PSD exists."
        ),
    }


# ============================================================
# 工具 4：write_report — 生成可读报告
# ============================================================

def write_report_tool(
    workspace: Path | str,
    session_id: str,
    metrics: dict[str, Any] | None = None,
    artifacts: list[str] | None = None,
) -> dict[str, Any]:
    """把实验结果写成 Markdown 报告。

    如果没传 metrics/artifacts，会从 session JSON 文件里自动读取。
    这让 Runtime 可以在工具链最后一步调用这个工具，而不需要手动传参数。

    产生的 agent-harness-report.md 可以给人看，也可以给面试官看。
    """
    root = Path(workspace)

    # 如果没有显式传入 metrics/artifacts，从 session 文件中读取
    if not metrics or not artifacts:
        session_path = root / "sessions" / f"{session_id}.json"
        if session_path.exists():
            session_payload = json.loads(session_path.read_text(encoding="utf-8"))
            metrics = metrics or session_payload.get("metrics", {})
            artifacts = artifacts or session_payload.get("artifacts", [])

    metrics = metrics or {}
    artifacts = artifacts or []

    report_dir = root / "reports" / session_id
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "agent-harness-report.md"

    nmse = metrics.get("nmse_db")
    nmse_line = f"{float(nmse):.4f} dB" if nmse is not None else "unknown"

    artifact_lines = (
        "\n".join(f"- `{artifact}`" for artifact in artifacts)
        if artifacts
        else "- No artifacts recorded"
    )

    report_path.write_text(
        "# Agent Harness Report\n\n"
        "## Result\n\n"
        f"- Session: `{session_id}`\n"
        f"- NMSE: {nmse_line}\n\n"
        "## Artifacts\n\n"
        f"{artifact_lines}\n\n"
        "## Runtime Evidence\n\n"
        "This report is generated by the Agent Harness tool chain. "
        "The important hiring evidence is not only the final NMSE, "
        "but the trace-backed execution path: config generation, "
        "training command execution, artifact verification, "
        "metric capture, and report generation.\n",
        encoding="utf-8",
    )

    return {
        "artifacts": [_relative(report_path, root)],
        "context_summary": f"Wrote Agent Harness report: {_relative(report_path, root)}",
    }


# ============================================================
# build_experiment_tool_registry — 装配工具注册中心
# ============================================================

def build_experiment_tool_registry(
    workspace: Path | str, default_timeout_seconds: float = 300.0
) -> ToolRegistry:
    """把 4 个实验工具注册到 ToolRegistry 并返回。

    这是"装配线"：所有工具函数用 partial 绑定 workspace，然后注册。

    partial 的作用：
      generate_config_tool 需要 workspace 参数，但 ToolRegistry 调用工具时
      只传 args 里的字段（如 base_config_path、experiment_id）。
      partial(generate_config_tool, workspace=root) 预填了 workspace，
      产生的函数只需要 base_config_path 和 experiment_id。

    调用链：
      ToolRegistry.run(ToolCall(name="generate_config", args={"base_config_path":..., "experiment_id":...}))
        → _invoke(partial(generate_config_tool, workspace=root), args)
          → generate_config_tool(workspace=root, base_config_path=..., experiment_id=...)
    """
    root = Path(workspace)
    registry = ToolRegistry(default_timeout_seconds=default_timeout_seconds)

    # 工具 1：生成配置
    registry.register(
        "generate_config",
        partial(generate_config_tool, workspace=root),
        spec=ToolSpec(
            name="generate_config",
            description="Generate an experiment YAML config from a base config and planner overrides.",
            input_schema={
                "type": "object",
                "required": ["base_config_path", "experiment_id"],
            },
            category="experiment",
            error_policy="fail_fast",  # 配置生成失败直接终止，不需要重试
        ),
    )

    # 工具 2：执行训练
    registry.register(
        "run_training",
        partial(run_training_tool, workspace=root),
        spec=ToolSpec(
            name="run_training",
            description="Run the nonlinear fitting training command for a generated config.",
            input_schema={"type": "object", "required": ["config_path"]},
            category="experiment",
            error_policy="return_error",  # 训练失败返回结构化错误，让 Agent 继续
        ),
    )

    # 工具 3：验证结果
    registry.register(
        "verify_artifacts",
        partial(verify_artifacts_tool, workspace=root),
        spec=ToolSpec(
            name="verify_artifacts",
            description="Verify metrics, PSD artifact, and NMSE threshold.",
            input_schema={
                "type": "object",
                "required": ["output_dir", "nmse_threshold_db"],
            },
            category="experiment",
            error_policy="return_error",  # 验证失败给 Agent 反馈，不崩溃
        ),
    )

    # 工具 4：写报告
    registry.register(
        "write_report",
        partial(write_report_tool, workspace=root),
        spec=ToolSpec(
            name="write_report",
            description="Write a Markdown Agent Harness report for a completed session.",
            input_schema={"type": "object", "required": ["session_id"]},
            category="reporting",
            error_policy="return_error",
        ),
    )

    return registry


# ============================================================
# 内部辅助函数
# ============================================================

def _load_metrics(workspace: Path, output_dir: str, stdout: str) -> dict[str, Any]:
    """从输出目录或 stdout 中提取指标。

    优先读 reports/{output_dir}/metrics.json（结构化的 JSON 文件），
    如果文件不存在，从 stdout 尾部解析 JSON（兼容训练脚本的把指标打印到标准输出）。
    """
    if output_dir:
        metrics_path = _resolve(workspace, output_dir) / "metrics.json"
        if metrics_path.exists():
            return json.loads(metrics_path.read_text(encoding="utf-8"))
    return parse_metrics_stdout(stdout)


def _collect_artifacts(workspace: Path, output_dir: str) -> list[str]:
    """收集训练产出的文件路径。

    固定查找 4 种产物：metrics.json、psd.png、summary.md、resolved_config.yaml。
    """
    if not output_dir:
        return []
    output_path = _resolve(workspace, output_dir)
    artifacts = []
    for name in ("metrics.json", "psd.png", "summary.md", "resolved_config.yaml"):
        path = output_path / name
        if path.exists():
            artifacts.append(_relative(path, workspace))
    return artifacts
