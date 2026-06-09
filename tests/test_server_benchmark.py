import asyncio
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.server import stream_benchmark_events


class ServerBenchmarkTest(unittest.TestCase):
    def test_stream_benchmark_events_runs_five_cases_and_writes_summary(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "configs" / "model-search").mkdir(parents=True)
            (root / "configs" / "model-search" / "lstsq-complexmp-o12-m150.yaml").write_text(
                "output_dir: reports/base\nepochs: 0\n",
                encoding="utf-8",
            )

            async def collect():
                chunks = []
                async for chunk in stream_benchmark_events(
                    root,
                    output_dir="benchmarks/check",
                    timeout_seconds=1,
                    nmse_threshold_db=-35.0,
                ):
                    chunks.append(chunk)
                return chunks

            chunks = asyncio.run(collect())
            payload = json.loads((root / "benchmarks" / "check" / "results.json").read_text(encoding="utf-8"))

        self.assertIn("benchmark_complete", "".join(chunks))
        self.assertEqual(payload["summary"]["case_count"], 5)
        self.assertEqual(
            [row["case_id"] for row in payload["results"]],
            [
                "target-under-budget",
                "invalid-plan-recovery",
                "runtime-failure-handling",
                "reflection-recovery",
                "budget-stop",
            ],
        )


if __name__ == "__main__":
    unittest.main()
