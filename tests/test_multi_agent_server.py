from __future__ import annotations

import unittest

from tests.test_supervisor_e2e import _plan


class TestMultiAgentServer(unittest.TestCase):
    def test_role_client_limits_bound_long_coding_responses(self):
        from nonlinear_agent.server import _configure_multi_agent_client

        class Client:
            max_tokens = None
            max_retries = 3
            temperature = 0.2

        coding = _configure_multi_agent_client(
            Client(), "coding", temperature=0.0, payload={}
        )
        writing = _configure_multi_agent_client(
            Client(), "writing", temperature=0.1, payload={}
        )

        self.assertEqual(coding.max_tokens, 8000)
        self.assertEqual(writing.max_tokens, 5000)
        self.assertEqual(coding.max_retries, 1)
        self.assertEqual(coding.temperature, 0.0)

    def test_sse_endpoint_streams_each_role_and_one_terminal(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test dependencies unavailable")

        from nonlinear_agent.server import create_app
        from nonlinear_agent.supervisor_graph import MultiAgentWorkers, build_multi_agent_graph

        graph = build_multi_agent_graph(
            MultiAgentWorkers(
                idea_plan=lambda request: _plan(),
                coding=lambda request: {"passed": True},
                execution=lambda request: {
                    "status": "completed",
                    "classification": "ok",
                    "metrics": {"nmse_db": -37.5},
                    "artifacts": ["reports/e2e/psd.png"],
                },
                writing=lambda request: {"pdf_path": "reports/e2e/report.pdf"},
            )
        )
        client = TestClient(
            create_app(".", multi_agent_graph_factory=lambda payload: graph)
        )

        response = client.post(
            "/multi-agent/run-web/events",
            json={"goal": "stream a complete multi-agent run"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text.count("event: multi_agent_terminal"), 1)
        for role in ("idea_plan", "plan_gate", "coding", "execution", "writing"):
            self.assertIn(f'"role": "{role}"', response.text)
        self.assertIn('"status": "completed"', response.text)


if __name__ == "__main__":
    unittest.main()
