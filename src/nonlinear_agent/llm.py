"""
LLM 客户端抽象层 ====================================================

解决一个问题：Agent 需要 LLM 来设计实验计划，但开发时不能每次都烧 API 钱。

提供两种实现，接口完全一样：
  FakeLLMClient         — 返回预设好的 JSON（离线开发/测试/benchmark）
  OpenAICompatibleClient — 真实调用 DeepSeek API（生产环境）

切换方式：
  if provider == "fake":      llm = FakeLLMClient(responses=["...", "..."])
  if provider == "deepseek":  llm = OpenAICompatibleClient.deepseek()

设计要点：
  - 两个 client 都实现 complete(prompt) → str 接口（鸭子类型，不需要显式继承）
  - FakeLLM 按队列依次返回预设回复，用完了抛异常
  - OpenAICompatible 用 urllib（标准库）而不是 requests/httpx，零额外依赖
  - system prompt 只写了一句："output concise JSON only" — 留给 planner.py 提供详细指令
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


# ============================================================
# LLMClient — 接口定义（Protocol，鸭子类型）
# ============================================================
class LLMClient(Protocol):
    """LLM 客户端的最小接口定义。

    Protocol 是 Python 的"鸭子类型注解"：
      不需要显式继承，只要有 complete(prompt) → str 这个方法，
      类型检查器就认为它满足 LLMClient 接口。

    为什么不是 ABC（抽象基类）？
      Protocol 更轻量——FakeLLMClient 和 OpenAICompatibleClient
      不需要 import 或继承任何东西，只要定义了 complete() 就行。
    """

    def complete(self, prompt: str) -> str:
        """发 prompt 给 LLM，返回模型回复的文本。

        本项目中，prompt 是 Planner 构造的"设计实验计划"指令，
        返回值是一个 JSON 字符串（ExperimentPlan 的结构）。
        """
        ...


# ============================================================
# FakeLLMClient — 假 LLM，离线用
# ============================================================
class FakeLLMClient:
    """返回预设好的固定回复，不调任何 API。

    工作方式：
      构造函数接收一个 JSON 字符串列表，按顺序排队。
      每次 complete() 从队首弹出一个返回，同时把 prompt 存下来（方便调试）。

    适用场景：
      - 开发阶段验证 Agent Loop 流程是否跑通
      - 单元测试
      - Benchmark（用固定回复评估 Agent 的行为质量）
      - 网页 Demo（给面试官现场演示，不依赖网络）

    失败处理：
      队列空了 → RuntimeError("no responses left")
      这意味着调用方预设的回复数量不够，需要加一轮。

    示例：
      llm = FakeLLMClient(responses=[
          '{"summary":"try lstsq", "stop":false, "experiments":[...]}',
          '{"summary":"done", "stop":true, "experiments":[]}',
      ])
      llm.complete("设计一个实验")  → 返回第一句
      llm.complete("设计下一个")    → 返回第二句
      llm.complete("再来一个")      → RuntimeError! 响应用完了
    """

    def __init__(self, responses: list[str]):
        # list() 做拷贝，防止外部修改原列表（避免意外）
        self.responses = list(responses)
        self.prompts: list[str] = []   # 记录每次调用的 prompt，方便调试
        self.last_prompt = ""           # 最近一次的 prompt
        self.total_prompt_tokens = 0    # Fake 模式无真实 token 消耗
        self.total_completion_tokens = 0

    def complete(self, prompt: str) -> str:
        """从预置队列里弹出一个回复返回。"""
        self.prompts.append(prompt)
        self.last_prompt = prompt
        if not self.responses:
            raise RuntimeError("FakeLLMClient has no responses left.")
        # pop(0) = 从队首取出，FIFO 队列
        return self.responses.pop(0)


# ============================================================
# OpenAICompatibleClient — 真实 LLM API（生产用）
# ============================================================
@dataclass
class OpenAICompatibleClient:
    """通用的 OpenAI-compatible API 客户端。

    支持任何兼容 OpenAI chat/completions 接口的服务（DeepSeek、OpenAI、本地 vLLM 等）。

    字段说明：
      api_key         — API 密钥，从环境变量或 .env.local 读取
      base_url        — API 地址，默认 DeepSeek
      model           — 模型名，如 deepseek-v4-pro
      temperature     — 创造性参数，0.2 是偏保守（稳定输出 JSON）
      timeout_seconds — HTTP 请求超时，默认 60s
    """

    api_key: str
    base_url: str
    model: str
    temperature: float = 0.2        # 低温度 → 输出更稳定、更少随机性
    timeout_seconds: float = 60.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0

    # ── 工厂方法：快速创建 DeepSeek 客户端 ──────────────────
    @classmethod
    def deepseek(
        cls,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        timeout_seconds: float = 60.0,
    ) -> "OpenAICompatibleClient":
        """创建 DeepSeek 客户端。

        如果不传 api_key，自动从环境变量 DEEPSEEK_API_KEY 读取
        （server.py 启动时已从 .env.local 加载到 os.environ）。
        """
        key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set.")
        return cls(
            api_key=key,
            base_url=base_url.rstrip("/"),  # 去掉末尾斜杠，后面拼接路径
            model=model,
            timeout_seconds=timeout_seconds,
        )

    # ── 核心方法：发请求，拿回复 ─────────────────────────────
    def complete(self, prompt: str) -> str:
        """发送 prompt 给 LLM，返回模型生成的文本。

        请求格式：OpenAI Chat Completions API
          POST {base_url}/chat/completions
          Body: {model, messages, temperature, response_format}

        response_format: {"type": "json_object"} 保证模型返回合法 JSON，
        这样 Planner 解析 ExperimentPlan 时不会遇到格式错误。
        """
        # ── 构造请求体 ──
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    # system prompt 只给最基本指令："输出简洁 JSON"
                    # 详细的实验设计指引由 planner.py 构造在 user prompt 里
                    "content": "You design concise JSON experiment plans. Return JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},  # 强制 JSON 输出
        }

        # ── 构造 HTTP 请求 ──
        # 用标准库 urllib 而不是 requests/httpx——零额外依赖
        request = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        # ── 发送请求 ──
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))

        except urllib.error.HTTPError as exc:
            # HTTP 错误（401 密钥无效、429 限流、500 服务端错误等）
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"LLM request failed with HTTP {exc.code}: {detail}"
            ) from exc

        except urllib.error.URLError as exc:
            # 网络错误（DNS 解析失败、连接超时、拒绝连接等）
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

        # ── 提取回复文本 ──
        # OpenAI 格式：choices[0].message.content
        content = str(body["choices"][0]["message"]["content"])

        # ── 累计 token 用量（用于 benchmark 成本统计）──
        usage = body.get("usage") or {}
        self.total_prompt_tokens += int(usage.get("prompt_tokens", 0))
        self.total_completion_tokens += int(usage.get("completion_tokens", 0))
        return content
