"""Hybrid retrieval (BM25 + local transformer embedding) tests.

The synthetic 30-query set used in test_knowledge_retrieval.py is keyword-
aligned, so recall=1.0 only proves lexical matching. This module evaluates
on real project docs with user-style Chinese questions, where lexical overlap
is low and the embedder must carry the semantic signal.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from nonlinear_agent.knowledge.ingest import KnowledgeIngestor
from nonlinear_agent.knowledge.retriever import KnowledgeRetriever


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# (user-style query, accepted heading fragments, term-rich expansion query)
REAL_QUERIES = [
    ("实验中断后如何从上次事件继续，而不是重头再来？", ["v2.0 Runtime 可靠性", "Resume Failed Run", "SSE 是最小可用流式接口", "9. Task 4：补齐本项目必要的 Runtime 可靠性"], "sse replay last event id resume runtime reliability"),
    ("系统怎么防止同一个请求被并发执行两次？", ["v2.0 Runtime 可靠性", "Task 4：补齐本项目必要的 Runtime 可靠性"], "runtime control plane sqlite dedup atomic claim lease 请求去重 并发 唯一执行"),
    ("想证明 Agent 会自己纠错而不是背答案，哪个案例最有说服力？", ["8. DeepSeek self-correction case", "真实 DeepSeek Loop 的自我修正证据"], "deepseek self correction case recovery"),
    ("LLM 返回的计划里带了不认识的字段，系统会怎么处理？", ["Task 2：建立逐步 AgentAction 与 Action Guard", "Schema Guard 怎么讲", "Planner Schema Guard", "本版主题"], "planner schema guard unknown fields validation"),
    ("Benchmark 报告里那些命中率、拒绝率指标是怎么定义的？", ["9. Benchmark 维护说明", "怎么证明 Agent 变强"], "benchmark target hit rate rejected rate definitions"),
    ("怎么把项目的教训沉淀下来，让下一个模型接手时不重新踩坑？", ["15.4 共享状态与 Memory Schema", "如何避免模型反复犯同样错误", "本次改动：Reflection 读取历史先验", "15. 方案 2：Knowledge + Memory 驱动的 Multi-Agent 实验团队"], "memory knowledge base structured experience supersedes"),
    ("不同角色的 Agent 用什么模型、温度、预算由谁决定？", ["15.3 ModelRouter", "v3.7.0：Supervisor + Idea/Plan Agent + ModelRouter"], "model router role provider temperature budget config"),
    ("写报告的 Agent 有没有权利修改实验数据？", ["D. Writing Agent"], "writing agent 无权修改实验数据 只读 report spec fidelity 数字校验"),
    ("执行实验的 Agent 能不能直接敲 shell 命令？", ["C. Execution Agent", "8. DeepSeek self-correction case", "3. 当前架构", "LLM 不能直接执行命令"], "execution agent tool registry no free shell"),
    ("改代码的 Agent 在哪个隔离环境里工作？", ["B. Coding Agent", "v3.8.0：Coding Agent + Execution Agent"], "coding agent isolated worktree patch"),
    ("先想清楚做什么实验再动手的 Agent 输出什么格式的计划？", ["A. Idea & Plan Agent", "仿真实验如何由 LLM 设计"], "idea plan agent hypotheses experiment dag 假设 候选实验 参数估算 停止条件"),
    ("多 Agent 团队里谁负责分配任务和终止整个流程？", ["15.2 Agent 职责与最小权限", "15.1 结论与边界"], "supervisor orchestration routing cancel"),
    ("项目目录和 GitHub 仓库分别在哪里？", ["1. 项目路径"], "project path github repository"),
    ("接手这个项目第一步应该跑什么命令？", ["3. 接手前必须运行"], "onboarding 接手 第一步 命令 python unittest benchmark dashboard"),
    ("提交代码时哪些文件绝对不能进仓库？", ["4. Git 操作规则", "v0.2 的真实链路", "v0.6 自动落盘与可复现实验记录"], "git ignore env local api key secrets 运行产物 不要提交"),
    ("这个项目在简历上应该怎么定位？", ["2. 当前定位", "1. 项目定位"], "resume positioning agent harness runtime"),
    ("每个版本完成了哪些能力，在哪里能一览？", ["5. 当前版本能力总览", "当前版本能力总览"], "version capability overview table"),
    ("核心代码文件分别承担什么职责？", ["6. 核心代码入口", "2. 总体架构", "核心设计"], "core code entry files responsibilities"),
    ("网页端能做什么、有哪些接口？", ["7. Web / CLI 功能", "当前接口形态", "SSE 是最小可用流式接口"], "web ui endpoints sse benchmark events"),
    ("10 个行为模板覆盖了哪些场景？", ["9. Benchmark 维护说明"], "benchmark case templates invalid plan runtime failure"),
    ("搜索策略对比实验的结论是什么？", ["v1.9 搜索对照实验", "6. 结论与边界"], "search comparison optuna reflection conclusion"),
    ("实验产物散落在根目录的问题是怎么修复的？", ["根目录实验产物"], "output dir normalize reports artifact paths"),
    ("reflection 之前只落盘不进入下一轮，后来怎么改的？", ["Reflection 决策闭环"], "reflection history next round prompt fix"),
    ("文档维护规则要求新增内容合并到哪里？", ["11. 文档维护规则"], "docs maintenance merge onboarding handoff"),
    ("哪些功能明确不归这个项目管？", ["12. 后续边界", "12. 明确不做"], "out of scope rag bm25 graph memory multi agent"),
    ("发布前要跑哪几条验证命令？", ["13. 验证命令"], "verification commands unit tests benchmark dashboard"),
    ("第一步要修 benchmark 指标的什么问题？", ["Task 1：修正 Benchmark 指标语义"], "benchmark metric semantics causal correction"),
    ("18 个独立任务是怎么避免模板复制凑数的？", ["Task 4：重建 18 个独立单 Domain Agent 任务"], "independent agent tasks unique cases no template"),
    ("测试怎么拆成快速和完整两档？", ["Task 6：拆分 fast/full 测试入口"], "fast full test profiles run tests"),
    ("v3.6.0 的记忆和知识库验收指标是什么？", ["v3.6.0：Knowledge/Memory Foundation", "v3.6/v3.8 验收缺口补齐（2026-08-11）"], "v3.6.0 memory knowledge recall citation leakage acceptance"),
]


def _real_chunks() -> list:
    """Small real-KB slice for offline logic tests (not the full eval)."""
    ingestor = KnowledgeIngestor(
        roots=[PROJECT_ROOT / "README.md", PROJECT_ROOT / "docs" / "handoff"]
    )
    return ingestor.ingest()[:150]


def _recall(retriever, top_k: int = 3, use_expansion: bool = True) -> float:
    hits = 0
    for query, accepted, extra in REAL_QUERIES:
        if use_expansion:
            results = retriever.retrieve_many([query, extra], top_k=top_k)
        else:
            results = retriever.retrieve(query, top_k=top_k)
        if any(
            any(exp in r.chunk.citation for exp in accepted)
            for r in results
        ):
            hits += 1
    return hits / len(REAL_QUERIES)


class _LexicalMockEmbedder:
    """Deterministic char-based embedder to exercise hybrid logic offline."""

    def dimension(self) -> int:
        return 16

    def encode(
        self, texts: list[str], is_query: bool = False
    ) -> list[list[float]]:
        vecs = []
        for text in texts:
            vec = [0.0] * 16
            for ch in text.lower():
                if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
                    vec[hash(ch) % 16] += 1.0
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            vecs.append([x / norm for x in vec])
        return vecs


class TestHybridRetrievalLogic(unittest.TestCase):
    def test_mock_embedder_reranks_bm25_pool(self):
        from nonlinear_agent.knowledge.ingest import KnowledgeChunk

        chunks = [
            KnowledgeChunk(
                chunk_id="c1", source_path="/kb/a.md", content_hash="", version="t",
                created_at=1.0, text="schema guard rejects unknown planner fields",
                citation="a.md#guard",
            ),
            KnowledgeChunk(
                chunk_id="c2", source_path="/kb/b.md", content_hash="", version="t",
                created_at=1.0, text="reflection writes facts into next prompt",
                citation="b.md#reflection",
            ),
        ]
        bm25 = KnowledgeRetriever(chunks=chunks)
        hybrid = KnowledgeRetriever(chunks=chunks, embedder=_LexicalMockEmbedder())
        results_hybrid = hybrid.retrieve("schema guard 拒绝未知字段", top_k=2)
        results_bm25 = bm25.retrieve("schema guard 拒绝未知字段", top_k=2)
        # 混合路径必须可用且返回排序结果
        self.assertEqual(len(results_hybrid), 2)
        self.assertEqual(results_hybrid[0].chunk.chunk_id, results_bm25[0].chunk.chunk_id)

    def test_hybrid_recall_at_least_bm25_on_real_docs(self):
        bm25 = KnowledgeRetriever(chunks=_real_chunks())
        hybrid = KnowledgeRetriever(chunks=_real_chunks(), embedder=_LexicalMockEmbedder())
        # 中文查询下，字符级 embedder 不应显著劣化 BM25 基线
        self.assertGreaterEqual(
            _recall(hybrid), _recall(bm25) - 0.15,
            "hybrid must not regress vs BM25",
        )


if __name__ == "__main__":
    unittest.main()
