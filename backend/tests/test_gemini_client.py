"""Offline Gemini boundary tests. All generation clients are mocks."""

from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from google.genai import errors, types
import httpx
import httpx2

from app.config import GeminiSettings
from app.services.data import DataServiceError
from app.services.gemini_client import GeminiService, OFFICIAL_BASE_URL
from app.services.openai_client import AIResult


SENSITIVE = "private response detail must not escape"


def completed(**changes):
    result = {
        "candidates": [{"finish_reason": "STOP", "content": {"role": "model", "parts": [{"text": " 답변입니다. "}]}}],
        "model_version": "gemini-3.5-flash-lite",
        "usage_metadata": {"prompt_token_count": 302, "candidates_token_count": 80, "thoughts_token_count": 7},
    }
    result.update(changes)
    return result


def sdk_error(code):
    return errors.APIError(code, {"error": {"message": SENSITIVE, "status": "UNSPECIFIED"}})


class GeminiClientTests(unittest.TestCase):
    def setUp(self):
        self.settings = GeminiSettings(api_key="offline-test-placeholder")
        self.client = Mock()
        self.client.models.generate_content.return_value = completed()
        self.service = GeminiService(self.settings, client=self.client)
        self.instructions = '분석 규칙\n{"count":128}'
        self.messages = [{"role": "user", "content": "최근 데이터를 설명해줘."}]

    def generate(self):
        return self.service.generate(self.instructions, self.messages)

    def assert_failure(self, status, code):
        with self.assertRaises(DataServiceError) as caught:
            self.generate()
        self.assertEqual(status, caught.exception.status_code)
        self.assertEqual(code, caught.exception.code)
        self.assertNotIn(SENSITIVE, str(caught.exception))
        self.assertNotIn(self.settings.api_key, str(caught.exception))
        self.client.models.generate_content.assert_called_once()

    def test_service_construction_is_lazy(self):
        with patch("google.genai.Client") as constructor:
            GeminiService(self.settings)
        constructor.assert_not_called()

    def test_missing_key_prevents_any_request(self):
        for key in ("", "   "):
            with self.subTest(key_present=bool(key.strip())):
                service = GeminiService(replace(self.settings, api_key=key), client=self.client)
                with self.assertRaises(DataServiceError) as caught:
                    service.generate(self.instructions, self.messages)
                self.assertEqual("gemini_key_missing", caught.exception.code)
        self.client.models.generate_content.assert_not_called()

    def test_unverified_model_prevents_request_and_fallback(self):
        service = GeminiService(replace(self.settings, model="unverified-model"), client=self.client)
        with self.assertRaises(DataServiceError) as caught:
            service.generate(self.instructions, self.messages)
        self.assertEqual("gemini_model_unverified", caught.exception.code)
        self.client.models.generate_content.assert_not_called()

    def test_sdk_timeout_official_endpoint_and_attempts_are_explicit(self):
        with patch("google.genai.Client", return_value=self.client) as constructor:
            GeminiService(replace(self.settings, timeout_seconds=17.5)).generate(self.instructions, self.messages)
        constructor.assert_called_once()
        args = constructor.call_args.kwargs
        self.assertEqual(self.settings.api_key, args["api_key"])
        self.assertIs(args["vertexai"], False)
        self.assertEqual(OFFICIAL_BASE_URL, args["http_options"].base_url)
        self.assertEqual(17500, args["http_options"].timeout)
        self.assertEqual(1, args["http_options"].retry_options.attempts)
        self.client.models.generate_content.assert_called_once()
        self.client.close.assert_called_once()

    def test_exact_generation_limits_and_no_tools_or_unsupported_sampling(self):
        self.generate()
        args = self.client.models.generate_content.call_args.kwargs
        self.assertEqual({"model", "contents", "config"}, set(args))
        self.assertEqual(self.settings.model, args["model"])
        config = args["config"].model_dump(exclude_none=True)
        self.assertEqual(self.instructions, config["system_instruction"])
        self.assertEqual(800, config["max_output_tokens"])
        self.assertEqual("MINIMAL", config["thinking_config"]["thinking_level"])
        self.assertIs(config["thinking_config"]["include_thoughts"], False)
        self.assertIs(config["automatic_function_calling"]["disable"], True)
        for field in ("temperature", "top_p", "top_k", "candidate_count", "tools", "tool_config"):
            self.assertNotIn(field, config)
        self.client.models.generate_content_stream.assert_not_called()

    def test_roles_are_mapped_without_changing_history_or_system_instruction(self):
        self.messages = [{"role": "user", "content": "첫 질문"}, {"role": "assistant", "content": "첫 답변"},
                         {"role": "user", "content": "새 질문"}]
        self.generate()
        contents = self.client.models.generate_content.call_args.kwargs["contents"]
        self.assertEqual(["user", "model", "user"], [item.role for item in contents])
        self.assertEqual([item["content"] for item in self.messages], [item.parts[0].text for item in contents])
        self.assertEqual("assistant", self.messages[1]["role"])

    def test_invalid_input_blocks_before_request(self):
        for messages in ([], [{"role": "system", "content": SENSITIVE}], [{"role": "user", "content": " "}]):
            with self.assertRaises(DataServiceError) as caught:
                self.service.generate(self.instructions, messages)
            self.assertEqual(422, caught.exception.status_code)
        self.client.models.generate_content.assert_not_called()

    def test_custom_output_tokens_are_used(self):
        GeminiService(replace(self.settings, max_output_tokens=500), self.client).generate(self.instructions, self.messages)
        self.assertEqual(500, self.client.models.generate_content.call_args.kwargs["config"].max_output_tokens)

    def test_actual_usage_includes_reported_thought_tokens(self):
        self.assertEqual(AIResult("답변입니다.", "gemini-3.5-flash-lite", {"input_tokens": 302, "output_tokens": 87}), self.generate())

    def test_missing_thoughts_uses_reported_candidates_only(self):
        self.client.models.generate_content.return_value = completed(usage_metadata={"prompt_token_count": 5, "candidates_token_count": 3})
        self.assertEqual({"input_tokens": 5, "output_tokens": 3}, self.generate().usage)

    def test_absent_or_invalid_usage_is_null_not_reconstructed(self):
        for usage in (None, {}, {"total_token_count": 10}, {"prompt_token_count": 1},
                      {"prompt_token_count": True, "candidates_token_count": 3},
                      {"prompt_token_count": 1, "candidates_token_count": -1},
                      {"prompt_token_count": 1.0, "candidates_token_count": 3},
                      {"prompt_token_count": 1, "candidates_token_count": 3, "thoughts_token_count": "2"},
                      {"prompt_token_count": 1, "candidates_token_count": 2**63 - 1, "thoughts_token_count": 1}):
            with self.subTest(usage=usage):
                self.client.models.generate_content.return_value = completed(usage_metadata=usage)
                self.assertIsNone(self.generate().usage)

    def test_actual_zero_counts_are_kept(self):
        self.client.models.generate_content.return_value = completed(usage_metadata={"prompt_token_count": 0, "candidates_token_count": 0, "thoughts_token_count": 0})
        self.assertEqual({"input_tokens": 0, "output_tokens": 0}, self.generate().usage)

    def test_sdk_response_models_are_supported(self):
        self.client.models.generate_content.return_value = types.GenerateContentResponse.model_validate(completed())
        self.assertEqual("답변입니다.", self.generate().reply)

    def test_thought_text_is_not_exposed_in_reply(self):
        response = completed()
        response["candidates"][0]["content"]["parts"] = [{"text": SENSITIVE, "thought": True}, {"text": "답변", "thought_signature": b"opaque"}]
        self.client.models.generate_content.return_value = response
        self.assertEqual("답변", self.generate().reply)

    def test_nontext_part_is_rejected_even_with_text_also_present(self):
        response = completed()
        response["candidates"][0]["content"]["parts"].append({"function_call": {"name": "ignored"}})
        self.client.models.generate_content.return_value = response
        self.assert_failure(502, "gemini_response_nontext")

    def test_malformed_parts_fail_with_safe_response_error(self):
        for parts, code in (("not-parts", "gemini_response_invalid"), ([None], "gemini_response_nontext"),
                            ([5], "gemini_response_nontext")):
            self.client.reset_mock()
            response = completed()
            response["candidates"][0]["content"]["parts"] = parts
            self.client.models.generate_content.return_value = response
            self.assert_failure(502, code)

    def test_truncated_and_other_nonstop_reasons_are_not_saved(self):
        for reason in ("MAX_TOKENS", "SAFETY", "RECITATION", "OTHER", None):
            self.client.reset_mock()
            response = completed()
            response["candidates"][0]["finish_reason"] = reason
            self.client.models.generate_content.return_value = response
            self.assert_failure(502, "gemini_response_incomplete")

    def test_prompt_block_is_rejected(self):
        self.client.models.generate_content.return_value = completed(prompt_feedback={"block_reason": "SAFETY"})
        self.assert_failure(502, "gemini_response_blocked")

    def test_candidate_safety_block_is_rejected(self):
        response = completed()
        response["candidates"][0]["safety_ratings"] = [{"blocked": True}]
        self.client.models.generate_content.return_value = response
        self.assert_failure(502, "gemini_response_blocked")

    def test_missing_or_multiple_candidates_are_rejected(self):
        for candidates in (None, [], [{}, {}]):
            self.client.reset_mock()
            self.client.models.generate_content.return_value = completed(candidates=candidates)
            self.assert_failure(502, "gemini_response_invalid")

    def test_empty_and_whitespace_reply_are_rejected(self):
        for text in ("", " \n "):
            self.client.reset_mock()
            response = completed()
            response["candidates"][0]["content"]["parts"] = [{"text": text}]
            self.client.models.generate_content.return_value = response
            self.assert_failure(502, "gemini_response_empty")

    def test_overlong_reply_is_rejected(self):
        response = completed()
        response["candidates"][0]["content"]["parts"] = [{"text": "가" * 4001}]
        self.client.models.generate_content.return_value = response
        self.assert_failure(502, "gemini_response_too_long")

    def test_missing_model_is_not_replaced_with_requested_model(self):
        for model in (None, "", " ", "m" * 201):
            self.client.reset_mock()
            self.client.models.generate_content.return_value = completed(model_version=model)
            self.assert_failure(502, "gemini_response_invalid")

    def test_errors_are_safe_and_have_no_retry(self):
        for code, expected_status, expected in ((401, 503, "gemini_authentication_failed"), (403, 503, "gemini_access_denied"),
                                               (429, 429, "gemini_rate_or_quota_limited"), (404, 503, "gemini_model_unavailable"),
                                               (400, 503, "gemini_configuration_error"), (504, 504, "gemini_timeout"),
                                               (500, 502, "gemini_request_failed")):
            self.client.reset_mock()
            self.client.models.generate_content.side_effect = sdk_error(code)
            self.assert_failure(expected_status, expected)

    def test_http_timeout_types_are_safe(self):
        for error in (TimeoutError(SENSITIVE), httpx.ReadTimeout(SENSITIVE), httpx2.ReadTimeout(SENSITIVE)):
            self.client.reset_mock()
            self.client.models.generate_content.side_effect = error
            self.assert_failure(504, "gemini_timeout")

    def test_transport_and_unknown_errors_are_safe(self):
        for error, code in ((httpx.ConnectError(SENSITIVE), "gemini_connection_failed"),
                            (httpx2.ConnectError(SENSITIVE), "gemini_connection_failed"),
                            (RuntimeError(SENSITIVE), "gemini_request_failed")):
            self.client.reset_mock()
            self.client.models.generate_content.side_effect = error
            self.assert_failure(502, code)

    def test_injected_client_is_not_closed(self):
        self.generate()
        self.client.close.assert_not_called()

    def test_owned_client_is_closed_on_success_and_error(self):
        with patch("google.genai.Client", return_value=self.client):
            GeminiService(self.settings).generate(self.instructions, self.messages)
            self.client.models.generate_content.side_effect = sdk_error(429)
            with self.assertRaises(DataServiceError):
                GeminiService(self.settings).generate(self.instructions, self.messages)
        self.assertEqual(2, self.client.close.call_count)
        self.assertEqual(2, self.client.models.generate_content.call_count)

    def test_cleanup_error_does_not_mask_generation_success_or_failure(self):
        self.client.close.side_effect = RuntimeError(SENSITIVE)
        with patch("google.genai.Client", return_value=self.client):
            result = GeminiService(self.settings).generate(self.instructions, self.messages)
            self.assertEqual("답변입니다.", result.reply)
            self.client.models.generate_content.side_effect = sdk_error(401)
            with self.assertRaises(DataServiceError) as caught:
                GeminiService(self.settings).generate(self.instructions, self.messages)
            self.assertEqual("gemini_authentication_failed", caught.exception.code)
            self.assertNotIn(SENSITIVE, str(caught.exception))
        self.assertEqual(2, self.client.models.generate_content.call_count)


if __name__ == "__main__":
    unittest.main()
