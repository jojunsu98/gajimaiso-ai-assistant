"""Explicit per-approval run namespaces and sanitized diagnostics, offline only."""

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

import httpx2
import openai

from app.config import OpenAISettings
from app.services.data import DataServiceError
from app.services.openai_client import AIResult, OpenAIService
from scripts import check_chat


PRIVATE = "offline-private-error-and-key-placeholder"


class ChatLiveRunTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory(dir=check_chat.LOCAL)
        self.addCleanup(folder.cleanup)
        self.local = Path(folder.name)
        local_patch = patch.object(check_chat, "LOCAL", self.local)
        local_patch.start()
        self.addCleanup(local_patch.stop)

    def test_named_run_preserves_previous_provider_records_and_reserves_once(self):
        historical = {
            "chat-openai-attempt.json": b"previous-personal-key-attempt",
            "chat-openai-live.json": b"previous-personal-key-failure",
            "chat-gemini-attempt.json": b"previous-gemini-attempt",
            "chat-gemini-live.json": b"previous-gemini-result",
        }
        for name, content in historical.items():
            (self.local / name).write_bytes(content)
        service = MagicMock()
        service.generate.return_value = AIResult("offline reply", "gpt-5.4-mini", None)

        def run(run_id):
            guard, _ = check_chat._openai_run_paths(run_id)
            ai = check_chat.OneAttemptAI(service, "gpt-5.4-mini", guard)
            ai.generate("offline instructions", [])
            return {"ok": True, "provider": "openai", "generation_requests": ai.calls,
                    "chat_completions_generation_requests": ai.calls, "responses_generation_requests": 0}

        with patch.object(check_chat, "run_openai", side_effect=run) as runner, \
             patch.object(check_chat, "run_gemini") as gemini, \
             patch.object(check_chat, "run_firestore") as firestore, \
             patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(0, check_chat.main(["--live-openai", "--run-id", "approved-once"]))
        runner.assert_called_once_with("approved-once")
        service.generate.assert_called_once()
        gemini.assert_not_called()
        firestore.assert_not_called()
        guard, report = check_chat._openai_run_paths("approved-once")
        self.assertEqual(1, json.loads(guard.read_text(encoding="utf-8"))["generation_attempt_reserved"])
        saved = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual("approved-once", saved["run_id"])
        self.assertEqual(1, saved["generation_requests"])
        for name, content in historical.items():
            self.assertEqual(content, (self.local / name).read_bytes())

    def test_reusing_run_id_is_blocked_by_either_guard_or_report_before_runner(self):
        for index in (0, 1):
            with self.subTest(existing="guard" if index == 0 else "report"):
                run_id = "existing-" + str(index)
                paths = check_chat._openai_run_paths(run_id)
                paths[index].write_bytes(b"retained-existing-record")
                with patch.object(check_chat, "run_openai") as runner, \
                     patch.object(check_chat, "run_gemini") as gemini, \
                     patch.object(check_chat, "run_firestore") as firestore, \
                     patch("sys.stdout", new=io.StringIO()) as output:
                    self.assertEqual(1, check_chat.main(["--live-openai", "--run-id", run_id]))
                for method in (runner, gemini, firestore):
                    method.assert_not_called()
                self.assertEqual("openai_run_already_recorded", json.loads(output.getvalue())["error"])
                self.assertEqual(b"retained-existing-record", paths[index].read_bytes())
                self.assertFalse(paths[1 - index].exists())

    def test_invalid_or_traversal_run_ids_do_not_call_any_runner_or_create_files(self):
        for run_id in ("../escape", r"..\escape", "..", "a/b", "UPPER", "", "-lead", "a" * 65):
            with self.subTest(run_id=run_id), \
                 patch.object(check_chat, "run_openai") as runner, \
                 patch.object(check_chat, "run_gemini") as gemini, \
                 patch.object(check_chat, "run_firestore") as firestore, \
                 patch("sys.stderr", new=io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    check_chat.main(["--live-openai", "--run-id=" + run_id])
                self.assertEqual(2, caught.exception.code)
                for method in (runner, gemini, firestore):
                    method.assert_not_called()
        self.assertEqual([], list(self.local.iterdir()))

    def test_run_id_is_rejected_without_openai_mode(self):
        for flags in ([], ["--live-firestore"], ["--live-gemini"]):
            with self.subTest(flags=flags), \
                 patch.object(check_chat, "run_openai") as runner, \
                 patch.object(check_chat, "run_gemini") as gemini, \
                 patch.object(check_chat, "run_firestore") as firestore, \
                 patch("sys.stderr", new=io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    check_chat.main(flags + ["--run-id", "explicit-run"])
                self.assertEqual(2, caught.exception.code)
                for method in (runner, gemini, firestore):
                    method.assert_not_called()
        self.assertEqual([], list(self.local.iterdir()))

    def test_openai_wrapper_selects_named_guard_without_loading_credentials(self):
        from app.config import load_openai_settings

        with patch.object(check_chat, "_run_live_provider", return_value={"ok": True}) as runner:
            self.assertEqual({"ok": True}, check_chat.run_openai("explicit-run"))
        runner.assert_called_once_with(
            "openai", load_openai_settings, OpenAIService,
            self.local / "chat-openai-explicit-run-attempt.json",
        )

    def error_ai(self, code):
        request = httpx2.Request("POST", "https://copa.codyssey.kr/v1/chat/completions")
        response = httpx2.Response(429, request=request)
        client = MagicMock()
        client.chat.completions.create.side_effect = openai.RateLimitError(
            PRIVATE, response=response, body={"code": code, "message": PRIVATE},
        )
        service = OpenAIService(OpenAISettings(api_key=PRIVATE), client=client)
        ai = check_chat.OneAttemptAI(service, "gpt-5.4-mini", self.local / "attempt.json")
        return ai, client

    def test_real_service_error_context_retains_only_safe_quota_fields_once(self):
        ai, client = self.error_ai("insufficient_quota")
        with self.assertRaises(DataServiceError) as caught:
            ai.generate("offline instructions", [])
        self.assertEqual(503, caught.exception.status_code)
        self.assertEqual("openai_quota_unavailable", caught.exception.code)
        self.assertEqual({"provider_http_status": 429, "provider_error_code": "insufficient_quota"},
                         ai.provider_error)
        with self.assertRaises(check_chat.CheckError):
            ai.generate("offline instructions", [])
        another_process = check_chat.OneAttemptAI(ai.service, ai.model, ai.guard)
        with self.assertRaises(FileExistsError):
            another_process.generate("offline instructions", [])
        client.chat.completions.create.assert_called_once()
        self.assertEqual(1, ai.calls)
        self.assertEqual(0, another_process.calls)
        self.assertNotIn(PRIVATE, json.dumps(ai.provider_error))
        self.assertNotIn(PRIVATE, ai.guard.read_text(encoding="utf-8"))
        self.assertNotIn(PRIVATE, str(caught.exception))

    def test_unrecognized_provider_error_code_is_suppressed(self):
        ai, client = self.error_ai(PRIVATE)
        with self.assertRaises(DataServiceError):
            ai.generate("offline instructions", [])
        self.assertEqual({"provider_http_status": 429,
                          "provider_error_code": "unrecognized_code_suppressed"}, ai.provider_error)
        self.assertNotIn(PRIVATE, json.dumps(ai.provider_error))
        client.chat.completions.create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
