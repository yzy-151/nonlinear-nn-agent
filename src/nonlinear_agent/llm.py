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

import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
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


_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class _RetryableRequestError(Exception):
    """可重试的 LLM 请求错误（限流 / 服务端瞬时错误 / 网络中断）。"""


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
    max_retries: int = 3            # 可重试错误（429/5xx/网络）的最大重试次数
    retry_backoff: float = 1.0      # 指数退避基数（秒）
    max_tokens: int | None = None   # 限制 completion 长度；None 表示不限制
    json_mode: bool = True          # response_format=json_object；推理模型下会吃掉 token，可关闭
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    _conn: Any = field(default=None, init=False, repr=False)  # http.client 连接池

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
    def complete(
        self, prompt: str, stream: bool = False, on_token: Any = None
    ) -> str:
        """发送 prompt 给 LLM，返回模型生成的文本。

        支持自动重试（429 / 5xx / 网络中断，指数退避）与可选流式输出：
        - stream=True 时逐 token 累积并通过 on_token 回调。
        - response_format: {"type": "json_object"} 保证 JSON 输出。
        """
        payload = self._build_payload(prompt, stream=stream)
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                if stream:
                    return self._complete_stream(payload, on_token)
                return self._complete_once(payload)
            except _RetryableRequestError as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(self.retry_backoff * (2 ** attempt))
        raise RuntimeError(
            f"LLM request failed after {self.max_retries + 1} attempts: {last_error}"
        ) from last_error

    def _build_payload(self, prompt: str, stream: bool) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an experiment-planning agent. You output ONLY a "
                        "valid JSON object matching the user-provided schema. "
                        "Never add prose, markdown, code fences, or nested "
                        "training/model objects. Every key inside 'overrides' "
                        "must be one of the keys the user marks as allowed; "
                        "'model_type' must be one of the listed model names."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
        }
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        if stream:
            payload["stream"] = True
        return payload

    def _get_connection(self):
        if self._conn is None:
            parsed = urllib.parse.urlparse(self.base_url)
            conn_cls = (
                http.client.HTTPSConnection
                if parsed.scheme == "https"
                else http.client.HTTPConnection
            )
            self._conn = conn_cls(parsed.netloc, timeout=self.timeout_seconds)
        return self._conn

    def _request_once(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        conn = self._get_connection()
        try:
            conn.request("POST", "/chat/completions", body=body, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
        except (http.client.HTTPException, OSError) as exc:
            self._conn = None  # 连接失效 → 重连
            raise _RetryableRequestError(f"connection error: {exc}") from exc

        if resp.status in _RETRYABLE_STATUS:
            self._conn = None
            raise _RetryableRequestError(f"HTTP {resp.status}: {raw[:200]!r}")
        if resp.status >= 400:
            raise RuntimeError(
                f"LLM request failed with HTTP {resp.status}: {raw[:300]!r}"
            )
        return json.loads(raw.decode("utf-8"))

    def _request_stream(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        conn = self._get_connection()
        try:
            conn.request("POST", "/chat/completions", body=body, headers=headers)
            resp = conn.getresponse()
            chunks: list[dict[str, Any]] = []
            while True:
                line = resp.readline()
                if not line:
                    break
                line = line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunks.append(json.loads(data))
                except json.JSONDecodeError:
                    continue
            return chunks
        except (http.client.HTTPException, OSError) as exc:
            self._conn = None
            raise _RetryableRequestError(f"stream error: {exc}") from exc

    def _complete_once(self, payload: dict[str, Any]) -> str:
        body = self._request_once(payload)
        content = str(body["choices"][0]["message"]["content"])
        usage = body.get("usage") or {}
        self.total_prompt_tokens += int(usage.get("prompt_tokens", 0))
        self.total_completion_tokens += int(usage.get("completion_tokens", 0))
        return content

    def _complete_stream(
        self, payload: dict[str, Any], on_token: Any = None
    ) -> str:
        content = ""
        for chunk in self._request_stream(payload):
            choices = chunk.get("choices") or []
            delta = ""
            if choices:
                delta = (choices[0].get("delta") or {}).get("content") or ""
            if delta:
                content += delta
                if on_token:
                    on_token(delta)
        return content


# ============================================================
# OpenAISDKClient — 官方 OpenAI SDK 适配层（可选）
# ============================================================
@dataclass
class OpenAISDKClient:
    """基于官方 openai SDK 的客户端（生产/流式路径）。

    与 OpenAICompatibleClient 提供相同的 complete(prompt) 接口，
    但由官方 SDK 管理重试、连接与流式，适合接入 OpenAI 官方模型
    或需要使用 SDK 特性的场景。默认路径仍是手写的
    OpenAICompatibleClient（零依赖）。
    """

    api_key: str
    base_url: str
    model: str
    temperature: float = 0.2
    timeout_seconds: float = 60.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    _client: Any = field(default=None, init=False, repr=False)

    @classmethod
    def deepseek_sdk(
        cls,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        timeout_seconds: float = 60.0,
    ) -> "OpenAISDKClient":
        key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set.")
        return cls(
            api_key=key,
            base_url=base_url.rstrip("/"),
            model=model,
            timeout_seconds=timeout_seconds,
        )

    def complete(
        self, prompt: str, stream: bool = False, on_token: Any = None
    ) -> str:
        from openai import OpenAI

        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an experiment-planning agent. You output ONLY a "
                    "valid JSON object matching the user-provided schema. "
                    "Never add prose, markdown, code fences, or nested objects."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            stream=stream,
        )

        if stream:
            content = ""
            for chunk in response:
                delta = ""
                if chunk.choices:
                    delta = chunk.choices[0].delta.content or ""
                if delta:
                    content += delta
                    if on_token:
                        on_token(delta)
            return content

        content = response.choices[0].message.content or ""
        if response.usage:
            self.total_prompt_tokens += response.usage.prompt_tokens or 0
            self.total_completion_tokens += response.usage.completion_tokens or 0
        return content


def create_llm_client(
    kind: str = "compat",
    api_key: str | None = None,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-v4-flash",
    timeout_seconds: float = 60.0,
):
    """LLM 客户端工厂：kind='compat'（手写，默认）或 'sdk'（官方 SDK）。"""
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set.")
    if kind == "sdk":
        return OpenAISDKClient(
            api_key=key,
            base_url=base_url.rstrip("/"),
            model=model,
            timeout_seconds=timeout_seconds,
        )
    return OpenAICompatibleClient(
        api_key=key,
        base_url=base_url.rstrip("/"),
        model=model,
        timeout_seconds=timeout_seconds,
    )
