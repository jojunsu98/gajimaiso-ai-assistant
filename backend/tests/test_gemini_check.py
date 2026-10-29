"""Provider selection and single-attempt CLI safety, with no credentials/network."""

from contextlib import ExitStack
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from scripts import check_chat


class GeminiCheckTests(unittest.TestCase):
    def test_provider_wrappers_select_only_their_explicit_service_and_guard(self):
        from app.config import load_gemini_settings, load_openai_settings
        from app.services.gemini_client import GeminiService
        from app.services.openai_client import OpenAIService

        with patch.object(check_chat, "_run_live_provider", return_value={"ok": True}) as run:
            self.assertEqual({"ok": True}, check_chat.run_gemini())
            run.assert_called_once_with("gemini", load_gemini_settings, GeminiService, check_chat.GEMINI_ATTEMPT_GUARD)
            run.reset_mock()
            self.assertEqual({"ok": True}, check_chat.run_openai())
            run.assert_called_once_with("openai", load_openai_settings, OpenAIService, check_chat.ATTEMPT_GUARD)
        self.assertNotEqual(check_chat.ATTEMPT_GUARD, check_chat.GEMINI_ATTEMPT_GUARD)

    def test_gemini_wrapper_missing_key_does_not_construct_sdk_service(self):
        with patch("app.config.load_gemini_settings", return_value=SimpleNamespace(api_key="")), \
             patch("app.services.gemini_client.GeminiService") as gemini, \
             patch("app.services.firestore.get_firestore_client") as firestore, \
             patch.object(check_chat, "OneAttemptAI") as ai:
            result = check_chat.run_gemini()
        self.assertEqual("waiting_for_gemini_key", result["status"])
        self.assertEqual(0, result["generation_requests"])
        self.assertEqual(0, result["responses_generation_requests"])
        gemini.assert_not_called()
        firestore.assert_not_called()
        ai.assert_not_called()

    def test_no_flag_never_selects_any_provider(self):
        with patch.object(check_chat, "run_firestore") as firestore, \
             patch.object(check_chat, "run_openai") as openai, \
             patch.object(check_chat, "run_gemini") as gemini, \
             patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(2, check_chat.main([]))
        for runner in (firestore, openai, gemini):
            runner.assert_not_called()

    def test_mutually_exclusive_modes_do_not_call_provider(self):
        with patch.object(check_chat, "run_openai") as openai, \
             patch.object(check_chat, "run_gemini") as gemini, \
             patch("sys.stderr", new=io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                check_chat.main(["--live-openai", "--live-gemini"])
        self.assertEqual(2, raised.exception.code)
        openai.assert_not_called()
        gemini.assert_not_called()

    def test_gemini_report_does_not_overwrite_openai_report_or_guard(self):
        with TemporaryDirectory(dir=check_chat.LOCAL) as folder:
            local = Path(folder)
            old_report = local / "chat-openai-live.json"
            old_guard = local / "chat-openai-attempt.json"
            old_report.write_text("existing-openai-failure", encoding="utf-8")
            old_guard.write_text("existing-openai-attempt", encoding="utf-8")
            result = {"ok": True, "provider": "gemini", "generation_requests": 1,
                      "responses_generation_requests": 0}
            with patch.object(check_chat, "LOCAL", local), \
                 patch.object(check_chat, "run_gemini", return_value=result) as gemini, \
                 patch.object(check_chat, "run_openai") as openai, \
                 patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(0, check_chat.main(["--live-gemini"]))
            gemini.assert_called_once_with()
            openai.assert_not_called()
            self.assertEqual(result, json.loads((local / "chat-gemini-live.json").read_text(encoding="utf-8")))
            self.assertEqual("existing-openai-failure", old_report.read_text(encoding="utf-8"))
            self.assertEqual("existing-openai-attempt", old_guard.read_text(encoding="utf-8"))

    def test_gemini_missing_key_is_waiting_exit_code_without_fallback(self):
        with TemporaryDirectory(dir=check_chat.LOCAL) as folder, \
             patch.object(check_chat, "LOCAL", Path(folder)), \
             patch.object(check_chat, "run_gemini", return_value={"ok": False, "status": "waiting_for_gemini_key"}), \
             patch.object(check_chat, "run_openai") as openai, \
             patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(2, check_chat.main(["--live-gemini"]))
            openai.assert_not_called()

    def test_openai_cli_report_name_and_error_exit_are_preserved(self):
        with TemporaryDirectory(dir=check_chat.LOCAL) as folder:
            local = Path(folder)
            with patch.object(check_chat, "LOCAL", local), \
                 patch.object(check_chat, "run_openai", return_value={"ok": False, "error": "openai_attempt_already_recorded"}) as openai, \
                 patch.object(check_chat, "run_gemini") as gemini, \
                 patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(1, check_chat.main(["--live-openai"]))
            openai.assert_called_once_with()
            gemini.assert_not_called()
            self.assertTrue((local / "chat-openai-live.json").is_file())
            self.assertFalse((local / "chat-gemini-live.json").exists())

    def test_missing_key_never_initializes_service_database_or_guard(self):
        with TemporaryDirectory(dir=check_chat.LOCAL) as folder:
            guard = Path(folder) / "gemini.json"
            factory = MagicMock()
            with patch("app.services.firestore.get_firestore_client") as firestore:
                result = check_chat._run_live_provider(
                    "gemini", lambda: SimpleNamespace(api_key=""), factory, guard)
            self.assertEqual("waiting_for_gemini_key", result["status"])
            self.assertEqual(0, result["generation_requests"])
            self.assertEqual(0, result["responses_generation_requests"])
            self.assertFalse(guard.exists())
            factory.assert_not_called()
            firestore.assert_not_called()

    def test_existing_gemini_guard_blocks_before_database_or_generation(self):
        with TemporaryDirectory(dir=check_chat.LOCAL) as folder:
            guard = Path(folder) / "gemini.json"
            guard.write_text("existing-attempt", encoding="utf-8")
            factory = MagicMock()
            settings = SimpleNamespace(api_key="offline-fixture", model="gemini-3.5-flash-lite")
            with patch("app.services.firestore.get_firestore_client") as firestore:
                result = check_chat._run_live_provider("gemini", lambda: settings, factory, guard)
            self.assertEqual("gemini_attempt_already_recorded", result["error"])
            self.assertEqual(0, result["generation_requests"])
            self.assertEqual("existing-attempt", guard.read_text(encoding="utf-8"))
            factory.return_value.generate.assert_not_called()
            firestore.assert_not_called()

    def test_provider_guards_are_independent_and_never_reset(self):
        with TemporaryDirectory(dir=check_chat.LOCAL) as folder:
            openai_guard = Path(folder) / "openai.json"
            gemini_guard = Path(folder) / "gemini.json"
            openai_guard.write_text("existing-openai-attempt", encoding="utf-8")
            service = MagicMock()
            ai = check_chat.OneAttemptAI(service, "gemini-3.5-flash-lite", gemini_guard)
            ai.generate("instructions", [])
            self.assertEqual(1, service.generate.call_count)
            self.assertTrue(gemini_guard.is_file())
            self.assertEqual("existing-openai-attempt", openai_guard.read_text(encoding="utf-8"))
            next_process = check_chat.OneAttemptAI(service, "gemini-3.5-flash-lite", gemini_guard)
            with self.assertRaises(FileExistsError):
                next_process.generate("instructions", [])
            self.assertEqual(1, service.generate.call_count)
            self.assertEqual(0, next_process.calls)

    def test_failed_gemini_attempt_keeps_guard_and_does_not_retry(self):
        with TemporaryDirectory(dir=check_chat.LOCAL) as folder:
            guard = Path(folder) / "gemini.json"
            service = MagicMock()
            service.generate.side_effect = RuntimeError("offline-private-value")
            ai = check_chat.OneAttemptAI(service, "gemini-3.5-flash-lite", guard)
            with self.assertRaises(RuntimeError):
                ai.generate("instructions", [])
            with self.assertRaises(check_chat.CheckError):
                ai.generate("instructions", [])
            self.assertEqual(1, service.generate.call_count)
            self.assertTrue(guard.exists())
            self.assertNotIn("offline-private-value", guard.read_text(encoding="utf-8"))

    def test_gemini_success_uses_shared_flow_and_counts_no_responses_calls(self):
        """The tool orchestrates one POST and read-only restoration, without SDKs."""
        with TemporaryDirectory(dir=check_chat.LOCAL) as folder, ExitStack() as stack:
            guard = Path(folder) / "gemini.json"
            settings = SimpleNamespace(api_key="offline-fixture", model="gemini-3.5-flash-lite")
            service = MagicMock()
            service.generate.return_value = SimpleNamespace(
                reply="오프라인 응답", model=settings.model,
                usage={"input_tokens": 20, "output_tokens": 5},
            )
            factory = MagicMock(return_value=service)
            db = stack.enter_context(patch("app.services.firestore.get_firestore_client")).return_value
            recording = SimpleNamespace(owned={"demo-id": [{}]})
            capture = {}

            def build(client, collection, ai, title_prefix):
                self.assertIs(db, client)
                self.assertEqual("conversations", collection)
                self.assertEqual("[연결 검증] ", title_prefix)
                capture["ai"] = ai
                return object(), recording

            stack.enter_context(patch.object(check_chat, "_build_test_app", side_effect=build))
            summary = {"count": 128, "fixture": "summary"}
            summary_json = json.dumps(summary)
            usage = {"input_tokens": 20, "output_tokens": 5}
            messages = [{"role": "user", "content": check_chat.QUESTION},
                        {"role": "assistant", "content": "오프라인 응답"}]
            detail = {"messages": messages, "message_count": 2, "source": "chat",
                      "last_summary": summary, "last_model": settings.model,
                      "last_usage": usage, "title": "[연결 검증] 오프라인"}
            http = stack.enter_context(patch("fastapi.testclient.TestClient")).return_value.__enter__.return_value

            def get(path):
                payload = {"/api/data/summary": summary,
                           "/api/conversations/demo-id": detail,
                           "/api/conversations": {"items": [{"id": "demo-id"}]}}[path]
                return SimpleNamespace(status_code=200, json=lambda: payload)

            def post(path, json):
                self.assertEqual("/api/chat", path)
                self.assertEqual({"message": check_chat.QUESTION}, json)
                capture["ai"].generate("현재 데이터 요약 JSON:\n" + summary_json, messages[:1])
                payload = {"conversation_id": "demo-id", "saved": True, "reply": "오프라인 응답",
                           "model": settings.model, "usage": usage}
                return SimpleNamespace(status_code=200, json=lambda: payload)

            http.get.side_effect = get
            http.post.side_effect = post
            original = [{"id": str(index)} for index in range(128)]
            stack.enter_context(patch.object(check_chat, "snapshot_collection",
                                            side_effect=[original, [], original, [{"id": "demo-id"}]]))
            cleanup = stack.enter_context(patch.object(check_chat, "cleanup_owned",
                                                       return_value={"ok": True, "documents": []}))
            result = check_chat._run_live_provider("gemini", lambda: settings, factory, guard)
            self.assertTrue(result["ok"], result)
            self.assertEqual(1, result["generation_requests"])
            self.assertEqual(0, result["responses_generation_requests"])
            self.assertEqual("gemini", result["provider"])
            self.assertEqual("demo-id", result["demo_conversation_id"])
            self.assertTrue(result["listed"] and result["reload_matches"])
            self.assertEqual(usage, result["usage"])
            service.generate.assert_called_once()
            http.post.assert_called_once()
            cleanup.assert_called_once_with(recording, keep_ids=["demo-id"])


if __name__ == "__main__":
    unittest.main()
