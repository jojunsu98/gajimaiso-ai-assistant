"""Offline SDK-boundary tests; no real client sends an HTTP request."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx2
import openai

from app.config import OpenAISettings
from app.services.data import DataServiceError
from app.services.openai_client import AIResult, OpenAIService


def completed(content="최근 저장 월은 2026-08입니다.", finish_reason="stop", **changes):
    fields = {
        "choices": [SimpleNamespace(
            finish_reason=finish_reason,
            message=SimpleNamespace(role="assistant", content=content, refusal=None),
        )],
        "model": "gpt-5.4-mini-2026-03-17",
        "usage": SimpleNamespace(prompt_tokens=302, completion_tokens=80),
    }
    fields.update(changes)
    return SimpleNamespace(**fields)


def sdk_error(error_type, status_code, **body):
    request = httpx2.Request("POST", "https://copa.codyssey.kr/v1/chat/completions")
    response = httpx2.Response(status_code, request=request)
    return error_type("private error text must not escape", response=response, body=body)


class OpenAIClientTests(unittest.TestCase):
    def setUp(self):
        self.settings = OpenAISettings(api_key="local-test-placeholder")
        self.client = Mock()
        self.client.chat.completions.create.return_value = completed()
        self.service = OpenAIService(self.settings, client=self.client)
        self.instructions = '분석 규칙\n{"count":128,"period":{"start":"2016-01","end":"2026-08"}}'
        self.messages = [{"role": "user", "content": "최근 데이터를 설명해줘."}]

    def generate(self):
        return self.service.generate(self.instructions, self.messages)

    def assert_safe_failure(self, status, code):
        with self.assertRaises(DataServiceError) as caught:
            self.generate()
        self.assertEqual(caught.exception.status_code, status)
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn("private error text", str(caught.exception))
        self.assertNotIn(self.settings.api_key, str(caught.exception))
        self.client.chat.completions.create.assert_called_once()

    def test_constructing_service_does_not_initialize_sdk(self):
        with patch("openai.OpenAI") as constructor:
            OpenAIService(self.settings)
        constructor.assert_not_called()

    def test_missing_key_blocks_before_request(self):
        service = OpenAIService(OpenAISettings(api_key=""), client=self.client)
        with self.assertRaises(DataServiceError) as caught:
            service.generate(self.instructions, self.messages)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.code, "openai_key_missing")
        self.client.chat.completions.create.assert_not_called()

    def test_whitespace_key_blocks_before_request(self):
        service = OpenAIService(OpenAISettings(api_key="   "), client=self.client)
        with self.assertRaises(DataServiceError) as caught:
            service.generate(self.instructions, self.messages)
        self.assertEqual(caught.exception.status_code, 503)
        self.client.chat.completions.create.assert_not_called()

    def test_unverified_model_blocks_without_fallback(self):
        service = OpenAIService(
            OpenAISettings(api_key="local-test-placeholder", model="unverified-model"),
            client=self.client,
        )
        with self.assertRaises(DataServiceError) as caught:
            service.generate(self.instructions, self.messages)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.code, "openai_model_unverified")
        self.client.chat.completions.create.assert_not_called()

    def test_sdk_has_zero_retries_explicit_timeout_and_configured_endpoint(self):
        settings = OpenAISettings(api_key="local-test-placeholder", timeout_seconds=17.5)
        with patch("openai.OpenAI", return_value=self.client) as constructor:
            service = OpenAIService(settings)
            service.generate(self.instructions, self.messages)
        constructor.assert_called_once_with(
            api_key=settings.api_key, base_url=settings.base_url,
            max_retries=0, timeout=17.5,
        )
        self.client.chat.completions.create.assert_called_once()

    def test_owned_sdk_client_is_created_and_closed_for_each_request(self):
        with patch("openai.OpenAI", return_value=self.client) as constructor:
            service = OpenAIService(self.settings)
            service.generate(self.instructions, self.messages)
            service.generate(self.instructions, self.messages)
        self.assertEqual(constructor.call_count, 2)
        self.assertEqual(self.client.chat.completions.create.call_count, 2)
        self.assertEqual(self.client.close.call_count, 2)

    def test_injected_client_is_not_closed(self):
        self.generate()
        self.client.close.assert_not_called()

    def test_owned_client_is_closed_after_failed_request(self):
        self.client.chat.completions.create.side_effect = sdk_error(openai.RateLimitError, 429)
        with patch("openai.OpenAI", return_value=self.client):
            service = OpenAIService(self.settings)
            with self.assertRaises(DataServiceError) as caught:
                service.generate(self.instructions, self.messages)
        self.assertEqual(caught.exception.code, "openai_rate_limited")
        self.client.chat.completions.create.assert_called_once()
        self.client.close.assert_called_once()

    def test_cleanup_failure_does_not_replace_success(self):
        self.client.close.side_effect = RuntimeError("private cleanup error")
        with patch("openai.OpenAI", return_value=self.client):
            result = OpenAIService(self.settings).generate(self.instructions, self.messages)
        self.assertEqual(result.reply, completed().choices[0].message.content)
        self.client.chat.completions.create.assert_called_once()
        self.client.close.assert_called_once()

    def test_cleanup_failure_does_not_replace_original_request_error(self):
        self.client.close.side_effect = RuntimeError("private cleanup error")
        self.client.chat.completions.create.side_effect = sdk_error(openai.AuthenticationError, 401)
        with patch("openai.OpenAI", return_value=self.client):
            with self.assertRaises(DataServiceError) as caught:
                OpenAIService(self.settings).generate(self.instructions, self.messages)
        self.assertEqual(caught.exception.code, "openai_authentication_failed")
        self.assertNotIn("private", str(caught.exception))
        self.client.chat.completions.create.assert_called_once()
        self.client.close.assert_called_once()

    def test_exact_chat_parameters_include_system_summary_and_no_extra_options(self):
        self.generate()
        self.client.chat.completions.create.assert_called_once_with(
            model="gpt-5.4-mini",
            messages=[{"role": "system", "content": self.instructions}, *self.messages],
            max_completion_tokens=800,
        )
        self.client.responses.create.assert_not_called()
        self.assertEqual(self.messages, [{"role": "user", "content": "최근 데이터를 설명해줘."}])

    def test_previous_conversation_order_is_preserved_after_system_message(self):
        self.messages = [
            {"role": "user", "content": "이전 질문"},
            {"role": "assistant", "content": "이전 답변"},
            {"role": "user", "content": "현재 질문"},
        ]
        self.generate()
        sent = self.client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual(sent[0], {"role": "system", "content": self.instructions})
        self.assertEqual(sent[1:], self.messages)

    def test_custom_output_token_setting_is_used(self):
        service = OpenAIService(
            OpenAISettings(api_key="local-test-placeholder", max_output_tokens=500),
            client=self.client,
        )
        service.generate(self.instructions, self.messages)
        self.assertEqual(self.client.chat.completions.create.call_args.kwargs["max_completion_tokens"], 500)

    def test_completed_reply_returns_actual_model_and_usage(self):
        self.client.chat.completions.create.return_value = completed(content=" \n답변입니다.\n ")
        self.assertEqual(
            self.generate(),
            AIResult("답변입니다.", "gpt-5.4-mini-2026-03-17", {"input_tokens": 302, "output_tokens": 80}),
        )

    def test_missing_usage_is_null(self):
        self.client.chat.completions.create.return_value = completed(usage=None)
        self.assertIsNone(self.generate().usage)

    def test_only_actual_nonnegative_integer_usage_is_recorded(self):
        examples = [
            SimpleNamespace(prompt_tokens=3),
            SimpleNamespace(prompt_tokens=3, completion_tokens=None),
            SimpleNamespace(prompt_tokens=True, completion_tokens=5),
            SimpleNamespace(prompt_tokens=3, completion_tokens=-1),
            SimpleNamespace(prompt_tokens=3.0, completion_tokens=5),
            SimpleNamespace(prompt_tokens="3", completion_tokens=5),
        ]
        for usage in examples:
            with self.subTest(usage=usage):
                self.client.chat.completions.create.return_value = completed(usage=usage)
                self.assertIsNone(self.generate().usage)

    def test_actual_zero_usage_is_kept(self):
        self.client.chat.completions.create.return_value = completed(
            usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0)
        )
        self.assertEqual(self.generate().usage, {"input_tokens": 0, "output_tokens": 0})

    def test_missing_or_malformed_choices_are_rejected(self):
        for choices in (None, [], {}, "invalid", [None], [12]):
            with self.subTest(choices=choices):
                self.client.chat.completions.create.reset_mock()
                self.client.chat.completions.create.return_value = completed(choices=choices)
                expected = "openai_response_incomplete" if choices in ([None], [12]) else "openai_response_invalid"
                self.assert_safe_failure(502, expected)

    def test_token_limited_incomplete_response_is_rejected_once(self):
        self.client.chat.completions.create.return_value = completed(finish_reason="length")
        self.assert_safe_failure(502, "openai_response_incomplete")

    def test_response_with_error_is_rejected(self):
        self.client.chat.completions.create.return_value = completed(error={"code": "server_error"})
        self.assert_safe_failure(502, "openai_response_failed")

    def test_unknown_missing_or_tool_finish_reason_is_not_completed(self):
        for finish_reason in (None, "unknown", "tool_calls", "function_call"):
            with self.subTest(finish_reason=finish_reason):
                self.client.chat.completions.create.reset_mock()
                self.client.chat.completions.create.return_value = completed(finish_reason=finish_reason)
                self.assert_safe_failure(502, "openai_response_incomplete")

    def test_filtered_response_is_rejected_even_with_text(self):
        self.client.chat.completions.create.return_value = completed(finish_reason="content_filter")
        self.assert_safe_failure(502, "openai_response_refused")

    def test_missing_message_and_non_assistant_role_are_rejected(self):
        for message in (None, {}, SimpleNamespace(role="user", content="text")):
            with self.subTest(message=message):
                self.client.chat.completions.create.reset_mock()
                choice = SimpleNamespace(finish_reason="stop", message=message)
                self.client.chat.completions.create.return_value = completed(choices=[choice])
                self.assert_safe_failure(502, "openai_response_invalid")

    def test_tool_calls_are_rejected_even_with_stop_and_text(self):
        for name in ("tool_calls", "function_call"):
            with self.subTest(name=name):
                self.client.chat.completions.create.reset_mock()
                response = completed()
                setattr(response.choices[0].message, name, [{"name": "unexpected_tool"}])
                self.client.chat.completions.create.return_value = response
                self.assert_safe_failure(502, "openai_response_invalid")

    def test_empty_text_is_rejected_once(self):
        for text in ("", " \n\t", None, 12):
            with self.subTest(text=text):
                self.client.chat.completions.create.reset_mock()
                self.client.chat.completions.create.return_value = completed(content=text)
                self.assert_safe_failure(502, "openai_response_empty")

    def test_refusal_is_rejected_even_with_other_text(self):
        response = completed()
        response.choices[0].message.refusal = "Declined."
        self.client.chat.completions.create.return_value = response
        self.assert_safe_failure(502, "openai_response_refused")

    def test_overlong_output_is_not_silently_truncated(self):
        self.client.chat.completions.create.return_value = completed(content="가" * 4_001)
        self.assert_safe_failure(502, "openai_response_too_long")

    def test_missing_actual_model_is_not_filled_from_config(self):
        for model in (None, "", "  ", 12):
            with self.subTest(model=model):
                self.client.chat.completions.create.reset_mock()
                self.client.chat.completions.create.return_value = completed(model=model)
                self.assert_safe_failure(502, "openai_response_invalid")

    def test_model_over_storage_limit_is_rejected(self):
        self.client.chat.completions.create.return_value = completed(model="m" * 201)
        self.assert_safe_failure(502, "openai_response_invalid")

    def test_authentication_error_is_safe_503(self):
        self.client.chat.completions.create.side_effect = sdk_error(openai.AuthenticationError, 401)
        self.assert_safe_failure(503, "openai_authentication_failed")

    def test_permission_error_is_safe_503(self):
        self.client.chat.completions.create.side_effect = sdk_error(openai.PermissionDeniedError, 403)
        self.assert_safe_failure(503, "openai_access_denied")

    def test_unknown_model_error_stops_without_model_fallback(self):
        self.client.chat.completions.create.side_effect = sdk_error(openai.NotFoundError, 404, code="model_not_found")
        self.assert_safe_failure(503, "openai_model_unavailable")

    def test_model_parameter_error_is_safe_503(self):
        self.client.chat.completions.create.side_effect = sdk_error(openai.BadRequestError, 400, param="model")
        self.assert_safe_failure(503, "openai_model_unavailable")

    def test_unsupported_request_option_is_safe_503(self):
        self.client.chat.completions.create.side_effect = sdk_error(openai.BadRequestError, 400, code="unsupported_parameter")
        self.assert_safe_failure(503, "openai_configuration_error")

    def test_quota_error_is_503_and_never_retried(self):
        self.client.chat.completions.create.side_effect = sdk_error(openai.RateLimitError, 429, code="insufficient_quota")
        self.assert_safe_failure(503, "openai_quota_unavailable")

    def test_quota_type_is_also_recognized(self):
        self.client.chat.completions.create.side_effect = sdk_error(openai.RateLimitError, 429, type="insufficient_quota")
        self.assert_safe_failure(503, "openai_quota_unavailable")

    def test_call_frequency_limit_is_429_and_never_retried(self):
        self.client.chat.completions.create.side_effect = sdk_error(openai.RateLimitError, 429, code="rate_limit_exceeded")
        self.assert_safe_failure(429, "openai_rate_limited")

    def test_timeout_is_504_and_never_retried(self):
        request = httpx2.Request("POST", "https://copa.codyssey.kr/v1/chat/completions")
        self.client.chat.completions.create.side_effect = openai.APITimeoutError(request)
        self.assert_safe_failure(504, "openai_timeout")

    def test_network_failure_is_502_and_never_retried(self):
        request = httpx2.Request("POST", "https://copa.codyssey.kr/v1/chat/completions")
        self.client.chat.completions.create.side_effect = openai.APIConnectionError(request=request)
        self.assert_safe_failure(502, "openai_connection_failed")

    def test_upstream_failure_is_502_and_never_retried(self):
        self.client.chat.completions.create.side_effect = sdk_error(openai.InternalServerError, 500)
        self.assert_safe_failure(502, "openai_request_failed")

    def test_unexpected_sdk_error_is_sanitized(self):
        self.client.chat.completions.create.side_effect = RuntimeError("private error text must not escape")
        self.assert_safe_failure(502, "openai_request_failed")


if __name__ == "__main__":
    unittest.main()
