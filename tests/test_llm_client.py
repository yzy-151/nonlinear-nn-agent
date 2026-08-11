"""TDD tests for the hardened HTTP client and the optional official SDK adapter."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.llm import (
    OpenAICompatibleClient,
    OpenAISDKClient,
    create_llm_client,
)


class TestCompatibleClientRetry(unittest.TestCase):
    def test_coding_role_uses_role_specific_system_prompt(self):
        client = create_llm_client(
            kind="compat",
            api_key="k",
            base_url="https://example.com",
            model="coding-model",
            role="coding",
        )
        payload = client._build_payload("write candidate", stream=False)
        system = payload["messages"][0]["content"]
        self.assertIn("coding agent", system.lower())
        self.assertNotIn("listed model names", system.lower())

    def test_explicit_system_prompt_overrides_role_default(self):
        client = create_llm_client(
            kind="compat",
            api_key="k",
            base_url="https://example.com",
            model="m",
            role="coding",
            system_prompt="custom role contract",
        )
        payload = client._build_payload("hello", stream=False)
        self.assertEqual(
            payload["messages"][0]["content"], "custom role contract"
        )

    def test_retries_on_retryable_http_error_then_succeeds(self):
        client = OpenAICompatibleClient(
            api_key="k", base_url="https://example.com", model="m",
            max_retries=3, retry_backoff=0.0,
        )
        calls = {"n": 0}

        def fake_once(payload):
            calls["n"] += 1
            if calls["n"] < 3:
                from nonlinear_agent.llm import _RetryableRequestError

                raise _RetryableRequestError("HTTP 429")
            return {
                "choices": [{"message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            }

        with mock.patch.object(client, "_request_once", side_effect=fake_once):
            content = client.complete("hi")

        self.assertEqual(content, '{"ok": true}')
        self.assertEqual(calls["n"], 3)
        self.assertEqual(client.total_prompt_tokens, 5)

    def test_does_not_retry_non_retryable_error(self):
        client = OpenAICompatibleClient(
            api_key="k", base_url="https://example.com", model="m",
            max_retries=3, retry_backoff=0.0,
        )
        with mock.patch.object(
            client, "_request_once",
            side_effect=RuntimeError("HTTP 401 unauthorized"),
        ):
            with self.assertRaises(RuntimeError):
                client.complete("hi")


class TestStaleConnection(unittest.TestCase):
    """Pooled connections closed by the server must be recreated, not reused."""

    def _client(self):
        return OpenAICompatibleClient(
            api_key="k", base_url="https://example.com", model="m"
        )

    def test_no_sock_is_stale(self):
        conn = mock.Mock()
        conn.sock = None
        self.assertTrue(self._client()._is_stale_connection(conn))

    def test_readable_sock_is_stale(self):
        client = self._client()
        conn = mock.Mock()
        fake_sock = mock.Mock()
        conn.sock = fake_sock
        with mock.patch("select.select", return_value=([fake_sock], [], [])):
            self.assertTrue(client._is_stale_connection(conn))

    def test_fresh_connection_recreates_when_stale(self):
        client = self._client()
        client._conn = mock.Mock()
        with mock.patch.object(client, "_get_connection", return_value="new-conn") as get_conn:
            conn = client._fresh_connection()
        self.assertEqual(conn, "new-conn")
        self.assertIsNone(client._conn)
        get_conn.assert_called_once()

    def test_fresh_connection_keeps_healthy_conn(self):
        client = self._client()
        healthy = mock.Mock()
        client._conn = healthy
        with mock.patch.object(client, "_get_connection", return_value="fresh"):
            conn = client._fresh_connection()
        # 连接池全部弃用：即使旧连接看似健康也新建，避免 CLOSE_WAIT 挂死
        self.assertEqual(conn, "fresh")
        self.assertIsNone(client._conn)


class TestCompatibleClientStream(unittest.TestCase):
    def test_stream_accumulates_content_and_calls_callback(self):
        client = OpenAICompatibleClient(
            api_key="k", base_url="https://example.com", model="m",
        )
        chunks = [
            {"choices": [{"delta": {"content": '{"sum'}}]},
            {"choices": [{"delta": {"content": 'mary":"go"}'}}]},
        ]
        seen: list[str] = []

        with mock.patch.object(client, "_request_stream", return_value=chunks):
            content = client.complete("hi", stream=True, on_token=seen.append)

        self.assertEqual(content, '{"summary":"go"}')
        self.assertEqual(seen, ['{"sum', 'mary":"go"}'])


class TestSDKClient(unittest.TestCase):
    def test_sdk_client_complete_uses_openai(self):
        fake_completion = mock.MagicMock()
        fake_completion.choices = [
            mock.MagicMock(message=mock.MagicMock(content='{"ok": 1}'))
        ]
        fake_completion.usage.prompt_tokens = 7
        fake_completion.usage.completion_tokens = 2
        fake_client = mock.MagicMock()
        fake_client.chat.completions.create.return_value = fake_completion

        client = OpenAISDKClient(
            api_key="k", base_url="https://example.com", model="m",
        )
        with mock.patch("openai.OpenAI", return_value=fake_client):
            content = client.complete("hi")

        self.assertEqual(content, '{"ok": 1}')
        self.assertEqual(client.total_prompt_tokens, 7)
        self.assertEqual(client.total_completion_tokens, 2)

    def test_create_llm_client_factory(self):
        compat = create_llm_client(
            kind="compat", api_key="k", base_url="https://x", model="m"
        )
        sdk = create_llm_client(
            kind="sdk", api_key="k", base_url="https://x", model="m"
        )
        self.assertIsInstance(compat, OpenAICompatibleClient)
        self.assertIsInstance(sdk, OpenAISDKClient)


if __name__ == "__main__":
    unittest.main()
