"""Exercise SDK HTTP serialization against an in-memory transport only."""

import json
import os
import unittest
from unittest.mock import patch

import httpx2
import openai

from app.config import OpenAISettings
from app.services.data import DataServiceError
from app.services.openai_client import AIResult, OpenAIService


BASE_URL = "https://copa.codyssey.kr/v1"
CHAT_URL = BASE_URL + "/chat/completions"


def completion(*, content=" 월별 자료에 근거한 답변입니다. ", finish_reason="stop",
               refusal=None, usage=True):
    payload = {
        "id": "mock-completion",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-5.4-mini-mock-response",
        "choices": [{
            "index": 0,
            "finish_reason": finish_reason,
            "message": {"role": "assistant", "content": content, "refusal": refusal},
        }],
    }
    if usage:
        payload["usage"] = {"prompt_tokens": 233, "completion_tokens": 51, "total_tokens": 284}
    return payload


class CodysseyHTTPTests(unittest.TestCase):
    def setUp(self):
        self.settings = OpenAISettings(api_key="offline-test-key")
        self.instructions = '분석 규칙: 원인 확정 금지\n{"count":128,"latest_month":"2026-08"}'
        self.messages = [
            {"role": "user", "content": "이전 질문"},
            {"role": "assistant", "content": "이전 답변"},
            {"role": "user", "content": "최근 12개월과 직전 12개월을 비교해줘."},
        ]
        self.requests = []
        self.constructors = []

    def request(self, *, payload=None, status=200, transport_error=None, environment=None):
        """Patch construction only to inject transport; retain real SDK behavior."""
        real_openai = openai.OpenAI

        def handler(request):
            # Deliberately never collect or print request headers or credentials.
            self.requests.append({
                "method": request.method,
                "url": str(request.url),
                "body": json.loads(request.content.decode("utf-8")),
            })
            if transport_error:
                raise transport_error("offline simulated failure", request=request)
            return httpx2.Response(status, json=payload if payload is not None else completion())

        def construct(**kwargs):
            self.constructors.append({
                "base_url": kwargs.get("base_url"),
                "max_retries": kwargs.get("max_retries"),
                "timeout": kwargs.get("timeout"),
            })
            client = httpx2.Client(transport=httpx2.MockTransport(handler), trust_env=False)
            return real_openai(**kwargs, http_client=client)

        with patch.dict(os.environ, environment or {}, clear=True), \
                patch("socket.socket.connect", side_effect=AssertionError("network forbidden")), \
                patch("openai.OpenAI", side_effect=construct):
            return OpenAIService(self.settings).generate(self.instructions, self.messages)

    def assert_single_codyssey_request(self):
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0]["method"], "POST")
        self.assertEqual(self.requests[0]["url"], CHAT_URL)
        self.assertNotIn("/responses", self.requests[0]["url"])
        self.assertNotIn("api.openai.com", self.requests[0]["url"])
        self.assertEqual(self.constructors, [{
            "base_url": BASE_URL, "max_retries": 0, "timeout": 45,
        }])

    def test_real_sdk_serializes_exact_codyssey_url_messages_and_completion_limit(self):
        result = self.request()
        self.assert_single_codyssey_request()
        self.assertEqual(self.requests[0]["body"], {
            "model": "gpt-5.4-mini",
            "messages": [{"role": "system", "content": self.instructions}, *self.messages],
            "max_completion_tokens": 800,
        })
        self.assertEqual(result, AIResult(
            reply="월별 자료에 근거한 답변입니다.",
            model="gpt-5.4-mini-mock-response",
            usage={"input_tokens": 233, "output_tokens": 51},
        ))

    def test_explicit_service_url_overrides_sdk_environment_default(self):
        self.request(environment={"OPENAI_BASE_URL": "https://api.openai.com/v1"})
        self.assert_single_codyssey_request()

    def test_missing_usage_stays_unknown(self):
        result = self.request(payload=completion(usage=False))
        self.assertIsNone(result.usage)
        self.assert_single_codyssey_request()

    def test_reported_zero_token_counts_are_preserved(self):
        payload = completion()
        payload["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        result = self.request(payload=payload)
        self.assertEqual(result.usage, {"input_tokens": 0, "output_tokens": 0})
        self.assert_single_codyssey_request()

    def test_partial_token_usage_is_not_fabricated(self):
        payload = completion()
        payload["usage"] = {"prompt_tokens": 12}
        self.assertIsNone(self.request(payload=payload).usage)
        self.assert_single_codyssey_request()

    def test_incomplete_or_blocked_completions_cannot_return_success(self):
        for reason in ("length", "content_filter", "tool_calls", "function_call", None):
            with self.subTest(finish_reason=reason):
                self.requests.clear()
                self.constructors.clear()
                with self.assertRaises(DataServiceError):
                    self.request(payload=completion(finish_reason=reason))
                self.assert_single_codyssey_request()

    def test_empty_or_refused_answer_cannot_return_success(self):
        for payload in (
            completion(content=""), completion(content=" \n\t"), completion(content=None),
            completion(content="partial explanation", refusal="Cannot comply."),
        ):
            with self.subTest(case="empty-or-refused"):
                self.requests.clear()
                self.constructors.clear()
                with self.assertRaises(DataServiceError):
                    self.request(payload=payload)
                self.assert_single_codyssey_request()

    def test_missing_choices_cannot_return_success(self):
        payload = completion()
        payload["choices"] = []
        with self.assertRaises(DataServiceError):
            self.request(payload=payload)
        self.assert_single_codyssey_request()

    def test_http_failures_never_retry_or_switch_url(self):
        cases = (
            (401, "invalid_api_key", "openai_authentication_failed"),
            (403, "permission_denied", "openai_access_denied"),
            (404, "model_not_found", "openai_model_unavailable"),
            (429, "rate_limit_exceeded", "openai_rate_limited"),
            (429, "insufficient_quota", "openai_quota_unavailable"),
            (500, "server_error", "openai_request_failed"),
            (502, "server_error", "openai_request_failed"),
            (503, "server_error", "openai_request_failed"),
        )
        for status, provider_code, expected_code in cases:
            with self.subTest(status=status, code=provider_code):
                self.requests.clear()
                self.constructors.clear()
                payload = {"error": {
                    "message": "private provider text must stay private",
                    "type": provider_code, "code": provider_code,
                }}
                with self.assertRaises(DataServiceError) as caught:
                    self.request(payload=payload, status=status)
                self.assertEqual(caught.exception.code, expected_code)
                self.assertNotIn("private provider text", str(caught.exception))
                self.assert_single_codyssey_request()

    def test_transport_timeout_and_connection_errors_never_retry(self):
        for failure, expected_code in (
            (httpx2.ReadTimeout, "openai_timeout"),
            (httpx2.ConnectError, "openai_connection_failed"),
        ):
            with self.subTest(error=expected_code):
                self.requests.clear()
                self.constructors.clear()
                with self.assertRaises(DataServiceError) as caught:
                    self.request(transport_error=failure)
                self.assertEqual(caught.exception.code, expected_code)
                self.assert_single_codyssey_request()


if __name__ == "__main__":
    unittest.main()
