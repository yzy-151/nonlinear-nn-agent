"""
Agent Harness 会话持久化 ============================================

解决一个问题：Agent 跑了一半崩溃了，重启后怎么接着跑？

ExperimentSession 是"一次实验的完整快照"——保存当前状态，随时可以恢复。
SessionStore 负责读写 JSON 文件，把 session 持久化到磁盘。

类比：
  ExperimentSession = 游戏存档（血量、位置、道具）
  SessionStore      = 存档管理器（存盘、读盘、新建存档）

和 trace 的区别：
  - trace（JSONL）= 录像回放，记录每一步事件（发生了什么）
  - session（JSON）= 游戏存档，记录当前状态（现在是什么样）
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# ============================================================
# ExperimentSession — 一次实验的完整状态快照
# ============================================================
@dataclass  # 不用 frozen——session 在运行过程中需要不断更新
class ExperimentSession:
    """保存一次 Agent 实验从开始到结束的所有关键信息。

    这个对象在 Runtime 执行过程中被持续更新：
      - 每完成一个工具步骤，追加 completed_steps
      - 每得到一个新指标，更新 metrics
      - 每遇到一个错误，追加 errors 和 error_types
      - 实验结束后，status 从 "initialized" → "running" → "succeeded"/"failed"
    """

    session_id: str    # 会话唯一标识，如 "exp001"、"planner-demo-001"
    goal: str          # 实验目标，如 "Find NMSE <= -35 dB under 4000 params"
    status: str = "initialized"  # 当前状态：initialized → running → succeeded / failed / cancelled

    # ── 运行时状态 ──
    current_step: str | None = None  # 当前正在执行哪个工具，如 "run_training"

    # ── 结果数据 ──
    metrics: dict[str, Any] = field(default_factory=dict)
    # 累积的指标，如 {"nmse_db": -37.42, "parameter_count": 3626}
    # 每个工具步骤的 metric 事件都会合并进来

    artifacts: list[str] = field(default_factory=list)
    # 产出的文件路径列表，如 ["reports/exp001/psd.png", "reports/exp001/metrics.json"]

    # ── 错误记录 ──
    errors: list[str] = field(default_factory=list)
    # 错误信息列表，如 ["NMSE -26 dB did not meet threshold -35 dB"]

    error_types: list[str] = field(default_factory=list)
    # 结构化错误类型，如 ["metric_threshold_error", "timeout_error"]
    # 和 errors 一一对应，用于后续统计分析

    completed_steps: list[int] = field(default_factory=list)
    # 已完成的步骤索引（1-based），如 [1, 2] 表示 step_1 和 step_2 已完成
    # 作用：支持断点续跑——如果 step_3 失败，下次可以从 step_3 开始而不是重跑 step_1,2

    context_summary: str = ""
    # 上下文摘要，工具可以写入的简短说明，比如 "Training finished in 30s with NMSE -37.42 dB"

    history: list[dict[str, Any]] = field(default_factory=list)
    # 完整事件历史，每个元素是一个 TraceEvent 的字典形式
    # 既保存在 trace JSONL 里（永久归档），也保留在 session 里（当前会话内快速查阅）


# ============================================================
# SessionStore — 会话的增删改查
# ============================================================
class SessionStore:
    """管理 ExperimentSession 的本地 JSON 文件存储。

    使用方式：
      store = SessionStore("sessions/")
      session = store.load_or_create(goal="...", session_id="exp001")
      # ... Runtime 执行工具，更新 session ...
      store.save(session)  # 持久化到 sessions/exp001.json
    """

    def __init__(self, directory: Path | str):
        """指定 session JSON 文件的存放目录"""
        self.directory = Path(directory)

    def create(self, goal: str, session_id: str) -> ExperimentSession:
        """创建一个全新的 session，状态为 "initialized" """
        return ExperimentSession(session_id=session_id, goal=goal)

    def path_for(self, session_id: str) -> Path:
        """根据 session_id 算出 JSON 文件路径，如 sessions/exp001.json"""
        return self.directory / f"{session_id}.json"

    def save(self, session: ExperimentSession) -> Path:
        """把 session 序列化为 JSON 写入磁盘。

        使用 asdict() 把 dataclass 转成普通字典，再 json.dumps() 写入文件。
        如果目录不存在会自动创建（mkdir parents=True）。
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(session.session_id)
        path.write_text(
            json.dumps(asdict(session), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def load(self, session_id: str) -> ExperimentSession:
        """从磁盘读取 JSON 并反序列化为 ExperimentSession 对象。

        ** 解包：json.loads() 返回 dict，然后用 **payload 展开传给构造函数。
        """
        payload = json.loads(self.path_for(session_id).read_text(encoding="utf-8"))
        return ExperimentSession(**payload)

    def load_or_create(self, goal: str, session_id: str) -> ExperimentSession:
        """加载已有 session 或创建新的。

        这是最常用的方法：
          - 文件存在 → 加载（恢复之前的运行状态，支持断点续跑）
          - 文件不存在 → 新建（第一次跑这个实验）
        """
        path = self.path_for(session_id)
        if path.exists():
            return self.load(session_id)
        return self.create(goal=goal, session_id=session_id)
