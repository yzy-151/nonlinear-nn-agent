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


class ReportDownloadServerTest(unittest.TestCase):
    def test_pdf_report_downloadable_via_artifacts_endpoint(self):
        from fastapi.testclient import TestClient

        from nonlinear_agent.reporting.pdf_renderer import render_pdf
        from nonlinear_agent.reporting.report_spec import ReportSpecBuilder
        from nonlinear_agent.server import create_app

        source = {
            "run_id": "download-001",
            "goal": "reach target",
            "baseline_nmse_db": -21.8,
            "nmse_db": -36.5,
            "parameter_count": 218,
            "cost_usd": 0.061,
            "psd_path": None,
            "trace_refs": ["traces/download-001.jsonl"],
            "reproduce_command": "python train.py --config x.yaml",
            "best_candidates": [
                {"model_type": "tiny_mlp", "nmse_db": -36.5, "parameter_count": 218}
            ],
            "failure_cases": [],
        }
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # 生成 1x1 PNG 作为 PSD
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            psd = root / "psd.png"
            fig, ax = plt.subplots()
            ax.plot([0, 1], [0, 1])
            fig.savefig(psd, dpi=72)
            plt.close(fig)
            source["psd_path"] = str(psd)

            reports = root / "reports"
            pdf_path = render_pdf(
                ReportSpecBuilder().build(source), output_dir=reports
            )
            app = create_app(root)
            client = TestClient(app)
            response = client.get(
                f"/artifacts/{pdf_path.relative_to(root).as_posix()}"
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("application/pdf", response.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
