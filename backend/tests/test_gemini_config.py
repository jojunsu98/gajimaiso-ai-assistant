"""Provider selection and Gemini settings, with no real credentials or network."""
import os
import unittest
from dataclasses import replace
from unittest.mock import patch

from app.config import (
    ENV_FILE, GeminiSettings, load_ai_provider, load_gemini_settings,
    validate_gemini_settings,
)
from app.routers.chat import get_chat_service
from app.services.data import DataServiceError


class GeminiConfigurationTests(unittest.TestCase):
    def load(self, file_values=None, process_values=None):
        with patch.dict(os.environ, process_values or {}, clear=True), patch(
            "app.config.dotenv_values", return_value=file_values or {}
        ) as read:
            settings = load_gemini_settings()
        read.assert_called_once_with(ENV_FILE, interpolate=False, encoding="utf-8-sig")
        return settings

    def test_defaults_and_hidden_key_representation(self):
        settings = self.load()
        self.assertEqual(settings, GeminiSettings())
        self.assertNotIn("test-private-value", repr(GeminiSettings(api_key="test-private-value")))

    def test_env_overrides_file_without_modifying_environment(self):
        settings = self.load(
            {"GEMINI_API_KEY": "file-value", "GEMINI_MODEL": "file-model"},
            {"GEMINI_API_KEY": "process-value", "GEMINI_MODEL": "gemini-3.5-flash-lite",
             "GEMINI_MAX_OUTPUT_TOKENS": "700", "GEMINI_TIMEOUT_SECONDS": "12.5"},
        )
        self.assertEqual(settings.api_key, "process-value")
        self.assertEqual(settings.model, "gemini-3.5-flash-lite")
        self.assertEqual(settings.max_output_tokens, 700)
        self.assertEqual(settings.timeout_seconds, 12.5)

    def test_blank_process_key_blocks_file_key(self):
        settings = self.load({"GEMINI_API_KEY": "file-value"}, {"GEMINI_API_KEY": ""})
        with self.assertRaises(DataServiceError) as caught:
            validate_gemini_settings(settings)
        self.assertEqual(caught.exception.code, "gemini_key_missing")

    def test_google_or_openai_key_is_never_implicitly_used(self):
        settings = self.load({"OPENAI_API_KEY": "other-value"}, {"GOOGLE_API_KEY": "other-value"})
        self.assertFalse(bool(settings.api_key))

    def test_invalid_number_has_safe_error(self):
        for field in ("GEMINI_MAX_OUTPUT_TOKENS", "GEMINI_TIMEOUT_SECONDS"):
            with self.subTest(field=field), self.assertRaises(DataServiceError) as caught:
                self.load({field: "private-invalid-value"})
            self.assertEqual(caught.exception.code, "gemini_configuration_invalid")
            self.assertNotIn("private-invalid-value", str(caught.exception))

    def test_empty_process_numeric_value_does_not_fall_back(self):
        with self.assertRaises(DataServiceError):
            self.load({"GEMINI_MAX_OUTPUT_TOKENS": "800"}, {"GEMINI_MAX_OUTPUT_TOKENS": ""})

    def test_invalid_key_values(self):
        for value in (None, "", " \t", 42):
            with self.subTest(value=value), self.assertRaises(DataServiceError) as caught:
                validate_gemini_settings(GeminiSettings(api_key=value))
            self.assertEqual(caught.exception.code, "gemini_key_missing")

    def test_invalid_limits_or_unverified_model_are_rejected(self):
        for changes in (
            {"max_output_tokens": 0}, {"max_output_tokens": 4097}, {"max_output_tokens": True},
            {"timeout_seconds": 0}, {"timeout_seconds": 121}, {"timeout_seconds": float("nan")},
            {"timeout_seconds": float("inf")}, {"timeout_seconds": True},
            {"model": ""}, {"model": "unverified-model"},
        ):
            with self.subTest(changes=changes), self.assertRaises(DataServiceError):
                validate_gemini_settings(replace(GeminiSettings(api_key="test-value"), **changes))

    def test_valid_limits(self):
        validate_gemini_settings(GeminiSettings(api_key="test-value", max_output_tokens=4096, timeout_seconds=120))

    def test_file_read_failure_is_safe(self):
        with patch("app.config.dotenv_values", side_effect=OSError("private-value")):
            with self.assertRaises(DataServiceError) as caught:
                load_gemini_settings()
        self.assertEqual(caught.exception.code, "gemini_configuration_invalid")
        self.assertNotIn("private-value", str(caught.exception))

    def test_provider_default_preserves_openai_compatibility(self):
        with patch.dict(os.environ, {}, clear=True), patch("app.config.dotenv_values", return_value={}):
            self.assertEqual(load_ai_provider(), "openai")

    def test_explicit_provider_and_process_precedence(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "gemini"}, clear=True), patch(
            "app.config.dotenv_values", return_value={"AI_PROVIDER": "openai"}
        ):
            self.assertEqual(load_ai_provider(), "gemini")

    def test_invalid_provider_never_falls_back(self):
        for value in ("", "unknown", "Gemini", None):
            with self.subTest(value=value), patch.dict(os.environ, {}, clear=True), patch(
                "app.config.dotenv_values", return_value={"AI_PROVIDER": value}
            ), self.assertRaises(DataServiceError) as caught:
                load_ai_provider()
            self.assertEqual(caught.exception.code, "ai_provider_invalid")

    def test_router_selects_gemini_without_loading_openai(self):
        settings = GeminiSettings(api_key="test-value")
        with patch("app.routers.chat.load_ai_provider", return_value="gemini"), patch(
            "app.routers.chat.load_gemini_settings", return_value=settings
        ), patch("app.routers.chat.load_openai_settings") as openai_settings, patch(
            "app.services.gemini_client.GeminiService"
        ) as service:
            selected = get_chat_service(conversations=object(), data=object())
        service.assert_called_once_with(settings)
        openai_settings.assert_not_called()
        self.assertIs(selected.ai_service, service.return_value)

    def test_router_retains_explicit_openai(self):
        with patch("app.routers.chat.load_ai_provider", return_value="openai"), patch(
            "app.routers.chat.load_openai_settings"
        ) as settings, patch("app.services.openai_client.OpenAIService") as service, patch(
            "app.routers.chat.load_gemini_settings"
        ) as gemini_settings:
            selected = get_chat_service(conversations=object(), data=object())
        service.assert_called_once_with(settings.return_value)
        gemini_settings.assert_not_called()
        self.assertIs(selected.ai_service, service.return_value)

    def test_provider_error_does_not_construct_either_client(self):
        with patch("app.routers.chat.load_ai_provider", side_effect=DataServiceError(503, "ai_provider_invalid", "safe")), patch(
            "app.routers.chat.load_openai_settings"
        ) as openai_settings, patch("app.routers.chat.load_gemini_settings") as gemini_settings:
            with self.assertRaises(DataServiceError):
                get_chat_service(conversations=object(), data=object())
        openai_settings.assert_not_called()
        gemini_settings.assert_not_called()
