"""OpenAI configuration tests using only mocked files and process settings."""

import math
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app import config
from app.config import OpenAISettings, load_openai_settings, validate_openai_settings
from app.services.data import DataServiceError


class OpenAIConfigurationTests(unittest.TestCase):
    def load(self, file_values=None, process_values=None):
        with patch.dict(os.environ, process_values or {}, clear=True):
            with patch("app.config.dotenv_values", return_value=file_values or {}):
                return load_openai_settings()

    def assert_invalid(self, settings, expected_code="openai_configuration_invalid"):
        with self.assertRaises(DataServiceError) as caught:
            validate_openai_settings(settings)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.code, expected_code)
        self.assertNotIn("local-key-placeholder", str(caught.exception))

    def test_fixed_backend_env_path_does_not_depend_on_working_directory(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("os.getcwd", return_value="C:/unrelated-working-directory"):
                with patch("app.config.dotenv_values", return_value={}) as read:
                    load_openai_settings()
        expected = Path(config.__file__).resolve().parents[1] / ".env"
        self.assertEqual(config.ENV_FILE, expected)
        read.assert_called_once_with(expected, interpolate=False, encoding="utf-8-sig")

    def test_public_defaults_and_empty_key(self):
        settings = self.load()
        self.assertEqual(settings.api_key, "")
        self.assertEqual(settings.model, "gpt-5.4-mini")
        self.assertEqual(settings.max_output_tokens, 800)
        self.assertEqual(settings.timeout_seconds, 45.0)
        self.assertEqual(settings.base_url, "https://copa.codyssey.kr/v1")

    def test_configured_values_are_read_without_loading_process_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("app.config.dotenv_values", return_value={
                "OPENAI_API_KEY": "local-key-placeholder",
                "OPENAI_MAX_OUTPUT_TOKENS": "500",
                "OPENAI_TIMEOUT_SECONDS": "20.5",
            }):
                settings = load_openai_settings()
                self.assertNotIn("OPENAI_API_KEY", os.environ)
        self.assertEqual(settings.api_key, "local-key-placeholder")
        self.assertEqual(settings.max_output_tokens, 500)
        self.assertEqual(settings.timeout_seconds, 20.5)

    def test_process_values_override_env_file_values(self):
        settings = self.load(
            {"OPENAI_API_KEY": "file-placeholder", "OPENAI_MODEL": "file-model",
             "OPENAI_MAX_OUTPUT_TOKENS": "500", "OPENAI_TIMEOUT_SECONDS": "20"},
            {"OPENAI_API_KEY": "process-placeholder", "OPENAI_MODEL": "gpt-5.4-mini",
             "OPENAI_MAX_OUTPUT_TOKENS": "700", "OPENAI_TIMEOUT_SECONDS": "12.5"},
        )
        self.assertEqual(settings.api_key, "process-placeholder")
        self.assertEqual(settings.model, "gpt-5.4-mini")
        self.assertEqual(settings.max_output_tokens, 700)
        self.assertEqual(settings.timeout_seconds, 12.5)

    def test_blank_process_key_disables_env_file_key(self):
        settings = self.load(
            {"OPENAI_API_KEY": "file-placeholder"}, {"OPENAI_API_KEY": ""}
        )
        self.assertEqual(settings.api_key, "")
        self.assert_invalid(settings, "openai_key_missing")

    def test_blank_process_model_does_not_fall_back(self):
        settings = self.load(
            {"OPENAI_API_KEY": "local-key-placeholder", "OPENAI_MODEL": "gpt-5.4-mini"},
            {"OPENAI_MODEL": ""},
        )
        self.assertEqual(settings.model, "")
        self.assert_invalid(settings, "openai_model_unverified")

    def test_base_url_is_loaded_with_process_precedence(self):
        settings = self.load(
            {"OPENAI_BASE_URL": "unapproved-file-placeholder"},
            {"OPENAI_BASE_URL": "https://copa.codyssey.kr/v1"},
        )
        self.assertEqual(settings.base_url, "https://copa.codyssey.kr/v1")
        self.assertEqual(self.load({"OPENAI_BASE_URL": "https://copa.codyssey.kr/v1"}).base_url,
                         "https://copa.codyssey.kr/v1")

    def test_invalid_base_url_never_falls_back_to_another_server(self):
        for value in ("", "https://api.openai.com/v1", "https://copa.codyssey.kr",
                      "https://copa.codyssey.kr/v1/v1", "https://copa.codyssey.kr/v1/chat/completions",
                      "http://copa.codyssey.kr/v1", "https://unapproved.invalid/v1", None):
            with self.subTest(value=value):
                self.assert_invalid(OpenAISettings(api_key="local-key-placeholder", base_url=value),
                                    "openai_base_url_invalid")
        settings = self.load({"OPENAI_API_KEY": "local-key-placeholder",
                              "OPENAI_BASE_URL": "https://copa.codyssey.kr/v1"},
                             {"OPENAI_BASE_URL": ""})
        self.assertEqual(settings.base_url, "")
        self.assert_invalid(settings, "openai_base_url_invalid")

    def test_blank_process_number_does_not_fall_back(self):
        for field in ("OPENAI_MAX_OUTPUT_TOKENS", "OPENAI_TIMEOUT_SECONDS"):
            with self.subTest(field=field):
                with self.assertRaises(DataServiceError) as caught:
                    self.load({field: "20"}, {field: ""})
                self.assertEqual(caught.exception.status_code, 503)
                self.assertEqual(caught.exception.code, "openai_configuration_invalid")

    def test_missing_whitespace_or_nonstring_key_is_503(self):
        for value in ("", " \n\t", None, 42):
            with self.subTest(value=value):
                self.assert_invalid(OpenAISettings(api_key=value), "openai_key_missing")

    def test_invalid_numeric_file_values_are_safe_errors(self):
        for field, value in (
            ("OPENAI_MAX_OUTPUT_TOKENS", "1.5"),
            ("OPENAI_MAX_OUTPUT_TOKENS", "invalid-value"),
            ("OPENAI_MAX_OUTPUT_TOKENS", None),
            ("OPENAI_TIMEOUT_SECONDS", "invalid-value"),
            ("OPENAI_TIMEOUT_SECONDS", None),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(DataServiceError) as caught:
                    self.load({field: value})
                self.assertEqual(caught.exception.status_code, 503)
                self.assertEqual(caught.exception.code, "openai_configuration_invalid")
                self.assertNotIn("invalid-value", str(caught.exception))

    def test_nan_or_infinite_loaded_timeout_is_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                settings = self.load({"OPENAI_API_KEY": "local-key-placeholder", "OPENAI_TIMEOUT_SECONDS": value})
                self.assertFalse(math.isfinite(settings.timeout_seconds))
                self.assert_invalid(settings)

    def test_token_limit_bounds_and_types_are_validated(self):
        for value in (0, -1, 4097, True, 800.0, "800"):
            with self.subTest(value=value):
                self.assert_invalid(OpenAISettings(api_key="local-key-placeholder", max_output_tokens=value))
        for value in (1, 800, 4096):
            with self.subTest(value=value):
                validate_openai_settings(OpenAISettings(api_key="local-key-placeholder", max_output_tokens=value))

    def test_timeout_bounds_and_types_are_validated(self):
        for value in (0, -1, 120.1, True, "45", float("nan"), float("inf")):
            with self.subTest(value=value):
                self.assert_invalid(OpenAISettings(api_key="local-key-placeholder", timeout_seconds=value))
        for value in (0.1, 45, 120):
            with self.subTest(value=value):
                validate_openai_settings(OpenAISettings(api_key="local-key-placeholder", timeout_seconds=value))

    def test_unverified_model_is_not_silently_replaced(self):
        settings = self.load({"OPENAI_API_KEY": "local-key-placeholder", "OPENAI_MODEL": "unverified-model"})
        self.assertEqual(settings.model, "unverified-model")
        self.assert_invalid(settings, "openai_model_unverified")

    def test_settings_repr_never_contains_key(self):
        settings = OpenAISettings(api_key="local-key-placeholder")
        self.assertNotIn("local-key-placeholder", repr(settings))
        self.assertNotIn("api_key", repr(settings))
        self.assertIn("gpt-5.4-mini", repr(settings))

    def test_settings_are_immutable(self):
        from dataclasses import FrozenInstanceError

        settings = OpenAISettings(api_key="local-key-placeholder")
        with self.assertRaises(FrozenInstanceError):
            settings.api_key = "replacement-placeholder"

    def test_file_read_failure_is_safe_without_original_error_text(self):
        for error in (OSError("private-path-placeholder"), UnicodeError("private-placeholder")):
            with self.subTest(error_type=type(error).__name__):
                with patch.dict(os.environ, {}, clear=True):
                    with patch("app.config.dotenv_values", side_effect=error):
                        with self.assertRaises(DataServiceError) as caught:
                            load_openai_settings()
                self.assertEqual(caught.exception.status_code, 503)
                self.assertEqual(caught.exception.code, "openai_configuration_invalid")
                self.assertNotIn("private", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
