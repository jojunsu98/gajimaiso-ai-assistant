"""Offline safety checks for the explicit browser QA harness."""
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.schemas.chat import ChatRequest
from app.services.data import DataServiceError
from app.services.openai_client import AIResult
from scripts import check_frontend as check
from scripts.check_chat import OneAttemptAI
from tests.test_data_service import FakeCollection


class MultiClient:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection({}))

    def write_option(self, **kwargs):
        return kwargs


class FrontendCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(dir=check.LOCAL)
        self.addCleanup(temporary.cleanup)
        self.local = Path(temporary.name)

    def test_default_does_not_initialize_any_external_client(self):
        with patch("app.services.firestore.get_firestore_client") as db, \
             patch("app.services.openai_client.OpenAIService") as ai, \
             patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(2, check.main([]))
        db.assert_not_called()
        ai.assert_not_called()

    def test_run_ids_reject_path_traversal_and_keep_separate_guards(self):
        with patch.object(check, "LOCAL", self.local):
            for value in (None, "../a", "a/b", "A", "", "a" * 65):
                with self.subTest(value=value), self.assertRaises(check.CheckError):
                    check.run_paths(value)
            report, guard = check.run_paths("browser-approved-once")
            self.assertNotEqual(report, guard)
            self.assertEqual(report.parent, self.local)
            self.assertIn("browser-approved-once", guard.name)

    def test_all_production_mutations_except_new_chat_create_are_blocked(self):
        client = MagicMock()
        data, conversations = check.ReadOnlyData(client), check.DemoConversations(client)
        for target, names in ((data, ("create_data", "update_data", "delete_data")),
                              (conversations, ("create_manual", "append_chat", "delete_conversation", "read_for_chat"))):
            for name in names:
                with self.subTest(name=name), self.assertRaises(DataServiceError) as caught:
                    getattr(target, name)(None)
                self.assertEqual(409, caught.exception.status_code)
        self.assertEqual([], client.mock_calls)

    def test_live_wrong_question_and_existing_id_never_generate(self):
        service = MagicMock()
        state = SimpleNamespace(live=True, ai=SimpleNamespace(calls=0), guard=self.local / "guard")
        chat = check.ObservedChat(service, state)
        for payload in (ChatRequest(message="unapproved"),
                        ChatRequest(message=check.UI_QUESTION, conversation_id="4c156da4-ea02-429f-8d06-3e25a41dbabb")):
            with self.assertRaises(DataServiceError):
                chat.chat(payload)
        service.chat.assert_not_called()

    def test_live_guard_blocks_a_second_request_before_chat_service(self):
        service = MagicMock()
        guard = self.local / "guard"
        guard.write_text("retained", encoding="utf-8")
        state = SimpleNamespace(live=True, ai=SimpleNamespace(calls=0), guard=guard)
        with self.assertRaises(DataServiceError) as caught:
            check.ObservedChat(service, state).chat(ChatRequest(message=check.UI_QUESTION))
        self.assertEqual("qa_generation_already_attempted", caught.exception.code)
        service.chat.assert_not_called()
        self.assertEqual("retained", guard.read_text(encoding="utf-8"))

    def test_error_and_empty_modes_use_real_api_contract_without_sdk(self):
        with patch("app.services.firestore.get_firestore_client") as db, \
             patch("app.services.openai_client.OpenAIService") as ai, \
             patch("app.main.load_allowed_origins", return_value=["http://127.0.0.1:5500"]):
            for case in ("422", "409", "503", "non-json", "empty"):
                with self.subTest(case=case), TestClient(check.build_mock_app(case)) as http:
                    response = http.get("/api/data/summary", headers={"Origin": "http://127.0.0.1:5500"})
                    self.assertEqual("http://127.0.0.1:5500", response.headers["access-control-allow-origin"])
                    if case == "empty":
                        self.assertEqual(200, response.status_code)
                        self.assertEqual(0, response.json()["count"])
                    elif case == "non-json":
                        self.assertEqual(503, response.status_code)
                        self.assertIn("text/plain", response.headers["content-type"])
                    else:
                        self.assertEqual(int(case), response.status_code)
                    self.assertEqual(404, http.get("/api/qa-control").status_code)
        db.assert_not_called()
        ai.assert_not_called()

    def test_isolated_browser_crud_fake_chat_and_cleanup_preserve_production(self):
        client = MultiClient()
        baseline = [{"id": str(index)} for index in range(128)]
        def snapshots(client, name):
            if name == "data":
                return baseline
            return []
        state = check.QAState(client, "isolated-firestore", "offline-isolated",
            self.local / "report.json", self.local / "guard", check.FakeAI())
        with patch.object(check, "snapshot_collection", side_effect=snapshots), \
             patch("app.main.load_allowed_origins", return_value=[]):
            app = state.initialize()
            with TestClient(app) as http:
                payload = {"date": "2040-01-01", "value": -7, "memo": "<script>test</script>"}
                created = http.post("/api/data", json=payload)
                self.assertEqual(201, created.status_code)
                document_id = created.json()["id"]
                self.assertEqual(409, http.post("/api/data", json=payload).status_code)
                self.assertEqual(200, http.put("/api/data/" + document_id, json={**payload, "value": 0}).status_code)
                chat = http.post("/api/chat", json={"message": "isolated fake question"})
                self.assertEqual(200, chat.status_code)
                self.assertTrue(chat.json()["saved"])
                self.assertEqual(204, http.delete("/api/data/" + document_id).status_code)
            state.finalize()
        self.assertEqual(0, state.report["generation_requests"])
        self.assertEqual(1, state.report["fake_ai_calls"])
        self.assertTrue(state.report["cleanup"]["ok"])
        self.assertTrue(state.report["data_preserved"]["ok"])
        self.assertTrue(state.report["existing_conversations_preserved"]["ok"])
        self.assertTrue(state.report["finalized"])
        self.assertEqual({}, client.collection("data").documents)
        self.assertEqual({}, client.collection("conversations").documents)

    def test_live_api_flow_one_mock_generation_retains_demo_and_reads(self):
        client = MultiClient()
        client.collection("data").documents["changwon-net-2026-08"] = {
            "date": "2026-08-01", "value": -4, "memo": "local fake only"}
        client.collection("data").versions["changwon-net-2026-08"] = 1
        baseline = [{"id": str(index)} for index in range(128)]
        def snapshots(client, name):
            if name == "data":
                return baseline
            return [{"id": key} for key in client.collection(name).documents]
        service = MagicMock()
        service.generate.return_value = AIResult("offline response", "gpt-5.4-mini", {"input_tokens": 3, "output_tokens": 4})
        guard = self.local / "guard"
        ai = OneAttemptAI(service, "gpt-5.4-mini", guard)
        state = check.QAState(client, "live-openai", "offline-once", self.local / "report.json", guard, ai)
        with patch.object(check, "snapshot_collection", side_effect=snapshots), \
             patch("app.main.load_allowed_origins", return_value=[]):
            app = state.initialize()
            with TestClient(app) as http:
                response = http.post("/api/chat", json={"message": check.UI_QUESTION})
                self.assertEqual(200, response.status_code)
                document_id = response.json()["conversation_id"]
                self.assertEqual(200, http.get("/api/conversations").status_code)
                detail = http.get("/api/conversations/" + document_id)
                self.assertTrue(detail.json()["title"].startswith("[화면 연결 검증]"))
                self.assertEqual(409, http.post("/api/chat", json={"message": check.UI_QUESTION}).status_code)
                self.assertEqual(409, http.delete("/api/conversations/" + document_id).status_code)
            state.finalize()
        service.generate.assert_called_once()
        self.assertTrue(state.report["ok"])
        self.assertTrue(state.report["demo_listed"])
        self.assertTrue(state.report["demo_reload_matches"])
        self.assertEqual(1, state.report["generation_requests"])
        self.assertIn(document_id, client.collection("conversations").documents)
        self.assertTrue(guard.exists())

    def test_stdin_stop_only_marks_own_server_for_graceful_shutdown(self):
        server = SimpleNamespace(should_exit=False)
        with patch("sys.stdin", new=io.StringIO("other\nstop\n")):
            check.stop_from_stdin(server)
        self.assertTrue(server.should_exit)


if __name__ == "__main__":
    unittest.main()
