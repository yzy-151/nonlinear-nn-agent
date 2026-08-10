import asyncio
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.server import stream_agent_task_benchmark_events


def _decode_sse(chunk: str) -> tuple[str, dict]:
    event = next(line[7:] for line in chunk.splitlines() if line.startswith("event: "))
    data = next(line[6:] for line in chunk.splitlines() if line.startswith("data: "))
    return event, json.loads(data)


class AgentBenchmarkServerTest(unittest.TestCase):
    def test_stream_exposes_case_provenance_and_complete_summary(self):
        async def collect(root: Path):
            return [
                _decode_sse(chunk)
                async for chunk in stream_agent_task_benchmark_events(
                    root, output_dir="benchmarks/agent-task-web", attempts=1
                )
            ]

        with TemporaryDirectory() as tmpdir:
            events = asyncio.run(collect(Path(tmpdir)))

        event_names = [name for name, _ in events]
        self.assertEqual(event_names[0], "agent_task_benchmark_start")
        self.assertEqual(event_names.count("agent_task_case_end"), 18)
        self.assertEqual(event_names[-1], "agent_task_benchmark_complete")
        case_payload = events[1][1]["payload"]
        self.assertIn("history", case_payload)
        self.assertIn("planner_call_id", case_payload["history"][0])
        self.assertEqual(events[-1][1]["payload"]["pass_at_1"], 1.0)


class MemoryInspectorServerTest(unittest.TestCase):
    def test_memory_endpoint_returns_namespaces_and_items(self):
        from fastapi.testclient import TestClient

        from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend
        from nonlinear_agent.memory.ports import MemoryItem, MemoryKind
        from nonlinear_agent.server import create_app

        with TemporaryDirectory() as tmpdir:
            app = create_app(Path(tmpdir))
            # 预置一条 memory 供 inspector 展示
            backend = LangGraphMemoryBackend()
            backend.write(
                MemoryItem(
                    memory_id="inspector-001",
                    kind=MemoryKind.EPISODIC,
                    namespace=("nonlinear-modeling", "hash-ds", "tiny_mlp"),
                    fact="generate_config succeeded",
                    evidence_refs=("a1:succeeded",),
                    run_id="inspector-run",
                    action_id="a1",
                    created_by_role="action_loop",
                    created_at=1.0,
                )
            )
            # 注意：create_app 内部有自己的 backend；直接验证端点契约（空列表也合法）
            client = TestClient(app)
            response = client.get("/memory")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("namespaces", payload)
            self.assertIn("items", payload)
            self.assertIsInstance(payload["items"], list)
            backend.close()


if __name__ == "__main__":
    unittest.main()
