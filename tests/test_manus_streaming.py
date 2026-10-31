import io
import json
import urllib.error
import unittest
from unittest import mock

from cx import api, config, connectors


class FakeResponse:
    def __init__(self, body, content_type="application/json"):
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body

    def __iter__(self):
        return iter(self.body.splitlines(keepends=True))


class ManusProxy(unittest.TestCase):
    BASE = "https://api.manus.im/api/llm-proxy/v1"

    def test_manus_catalog_never_fetches_models(self):
        with mock.patch.object(connectors, "_get", side_effect=AssertionError("network request not expected")):
            ids, style = connectors.list_models(self.BASE, "test-key")
            specs = api.list_model_specs({"base_url": self.BASE}, "test-key")
        self.assertEqual(style, "openai")
        self.assertIn("claude-opus-4-7", ids)
        self.assertEqual(next(m["name"] for m in specs if m["id"] == "claude-opus-4-7"), "/.GPT 5.6 Sol")
        self.assertEqual(next(m["name"] for m in specs if m["id"] == "claude-sonnet-4-6"), "/.GPT 5.6 TERRA")
        self.assertEqual(next(m["name"] for m in specs if m["id"] == "claude-haiku-4-5"), "/.GPT 5.6 LUNA")
        self.assertEqual(next(m["name"] for m in specs if m["id"] == "gemini-2.5-flash"), "/. Gemini 3.5 Flash Lite")

    def test_full_chat_completions_url_normalizes_to_api_root(self):
        self.assertEqual(
            config.normalize_url(self.BASE + "/chat/completions"),
            self.BASE,
        )

    def test_stream_unsupported_falls_back_to_json(self):
        seen = []

        def fake_open(cfg, key, path, payload, conv_id, timeout):
            seen.append(payload.copy())
            if payload.get("stream"):
                raise urllib.error.HTTPError(
                    "https://proxy.invalid/chat/completions", 400, "Bad Request", {},
                    io.BytesIO(b'{"error":"streaming is not supported"}'),
                )
            return FakeResponse(json.dumps({
                "choices": [{"message": {"role": "assistant", "content": "fallback works"}}],
                "usage": {"total_tokens": 4},
            }))

        with mock.patch.object(api, "_open", side_effect=fake_open):
            msg, usage, _ = api.chat(
                {"base_url": "https://proxy.invalid/v1", "model": "demo"},
                "key", [{"role": "user", "content": "hello"}],
            )
        self.assertEqual(msg["content"], "fallback works")
        self.assertEqual([p.get("stream") for p in seen], [True, False])


    def test_json_error_about_streaming_retries_non_stream(self):
        seen = []

        def fake_open(cfg, key, path, payload, conv_id, timeout):
            seen.append(payload.copy())
            if payload.get("stream"):
                return FakeResponse('{"error":"streaming is not supported"}')
            return FakeResponse('{"choices":[{"message":{"content":"json fallback"}}]}')

        with mock.patch.object(api, "_open", side_effect=fake_open):
            msg, _, _ = api.chat(
                {"base_url": "https://proxy.invalid/v1", "model": "demo"},
                "key", [{"role": "user", "content": "hello"}],
            )
        self.assertEqual(msg["content"], "json fallback")
        self.assertEqual([p.get("stream") for p in seen], [True, False])

    def test_openai_sse_stream(self):
        chunks = (
            'data: {"choices":[{"delta":{"content":"hello "}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"world"}}]}\n\n'
            'data: [DONE]\n\n'
        )
        streamed = []
        with mock.patch.object(api, "_open", return_value=FakeResponse(chunks, "text/event-stream")):
            msg, _, _ = api.chat(
                {"base_url": "https://proxy.invalid/v1", "model": "demo"},
                "key", [{"role": "user", "content": "hello"}], on_text=streamed.append,
            )
        self.assertEqual(msg["content"], "hello world")
        self.assertEqual("".join(streamed), "hello world")

    def test_anthropic_and_gemini_sse_text_shapes(self):
        samples = [
            ('event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"type":"text_delta","text":"anthropic"}}\n\n', "anthropic"),
            ('data: {"candidates":[{"content":{"parts":[{"text":"gemini"}]}}]}\n\n', "gemini"),
        ]
        for body, expected in samples:
            with self.subTest(expected=expected), mock.patch.object(
                api, "_open", return_value=FakeResponse(body, "text/event-stream")
            ):
                msg, _, _ = api.chat(
                    {"base_url": "https://proxy.invalid/v1", "model": "demo"},
                    "key", [{"role": "user", "content": "hello"}],
                )
                self.assertEqual(msg["content"], expected)


if __name__ == "__main__":
    unittest.main()
