"""Offline HTTP/chat orchestration checks. No SDK credentials or real DB calls."""

from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from google.api_core.exceptions import DeadlineExceeded
from google.api_core.datetime_helpers import DatetimeWithNanoseconds

from app.main import create_app
from app.security import require_access, limit_chat
from app.routers.chat import get_chat_service
from app.routers.conversations import get_conversation_service
from app.routers.data import get_data_service
from app.schemas.data import DataRecord
from app.services.chat import ChatService
from app.services.conversations import ConversationService
from app.services.data import DataServiceError
from app.services.openai_client import AIResult
from scripts import check_chat
from tests.test_data_api import FakeDataService
from tests.test_data_service import FakeClient


SENSITIVE = "offline-private-value-must-not-be-echoed"


def pairs(count, user_size=0, answer_size=0):
    result = []
    for index in range(count):
        result.extend([
            {"role": "user", "content": str(index) + ("가" * user_size or " 질문")},
            {"role": "assistant", "content": str(index) + ("나" * answer_size or " 답변")},
        ])
    return result


class FakeAI:
    def __init__(self):
        self.calls = []
        self.config_error = None
        self.generate_error = None
        self.hook = None
        self.reply = "요약에 저장된 월별 순이동을 기준으로 설명한 모의 답변입니다."
        self.usage = None

    def validate_configuration(self):
        if self.config_error:
            raise self.config_error

    def generate(self, instructions, messages):
        self.calls.append({"instructions": instructions, "messages": deepcopy(messages)})
        if self.hook:
            self.hook()
        if self.generate_error:
            raise self.generate_error
        return AIResult(reply=self.reply, model="fake-ai-no-network", usage=self.usage)


class ChatAPITests(unittest.TestCase):
    def setUp(self):
        with patch("app.main.load_allowed_origins", return_value=[]):
            self.app = create_app()
        # Business contracts use explicit test overrides; security has its own tests.
        self.app.dependency_overrides[require_access] = lambda: None
        self.app.dependency_overrides[limit_chat] = lambda: None
        self.firebase = FakeClient()
        self.conversations = ConversationService(self.firebase)
        self.data = FakeDataService()
        self.data.records = {
            "changwon-net-2026-07": {"id": "changwon-net-2026-07", "date": "2026-07-01", "value": -10, "memo": SENSITIVE},
            "changwon-net-2026-08": {"id": "changwon-net-2026-08", "date": "2026-08-01", "value": 0, "memo": SENSITIVE},
        }
        self.ai = FakeAI()
        self.chat = ChatService(self.conversations, self.data, self.ai)
        self.app.dependency_overrides[get_conversation_service] = lambda: self.conversations
        self.app.dependency_overrides[get_data_service] = lambda: self.data
        self.app.dependency_overrides[get_chat_service] = lambda: self.chat
        self.http = TestClient(self.app, raise_server_exceptions=False)
        self.addCleanup(self.http.close)

    def manual(self, messages=None, **extra):
        response = self.http.post("/api/conversations", json={"messages": messages or pairs(1), **extra})
        self.assertEqual(201, response.status_code, response.text)
        return response.json()

    def ask(self, message="요약해줘", conversation_id=None):
        body = {"message": message}
        if conversation_id is not None:
            body["conversation_id"] = conversation_id
        return self.http.post("/api/chat", json=body)

    def test_manual_save_list_detail_delete_without_ai(self):
        saved = self.manual(title=" 수동 제목 ")
        self.assertEqual("manual", saved["source"])
        self.assertEqual("수동 제목", saved["title"])
        self.assertEqual(2, saved["message_count"])
        self.assertTrue(saved["created_at"].endswith(("Z", "+00:00")))
        self.assertEqual(saved, self.http.get("/api/conversations/" + saved["id"]).json())
        listing = self.http.get("/api/conversations").json()
        self.assertEqual(1, listing["count"])
        self.assertEqual({"id", "title", "created_at", "updated_at", "message_count"}, set(listing["items"][0]))
        response = self.http.delete("/api/conversations/" + saved["id"])
        self.assertEqual(204, response.status_code)
        self.assertEqual(b"", response.content)
        self.assertEqual(404, self.http.get("/api/conversations/" + saved["id"]).status_code)
        self.assertEqual({"items": [], "count": 0}, self.http.get("/api/conversations").json())
        self.assertEqual([], self.ai.calls)

    def test_new_chat_is_confirmed_saved_and_reloadable(self):
        response = self.ask("  현재 자료를 설명해줘  ")
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual({"conversation_id", "reply", "saved", "data_period", "model", "usage"}, set(body))
        self.assertIs(body["saved"], True)
        self.assertIsNone(body["usage"])
        self.assertEqual({"start": "2026-07", "end": "2026-08"}, body["data_period"])
        detail = self.http.get("/api/conversations/" + body["conversation_id"]).json()
        self.assertEqual("chat", detail["source"])
        self.assertEqual("현재 자료를 설명해줘", detail["title"])
        self.assertEqual([{"role": "user", "content": "현재 자료를 설명해줘"},
                          {"role": "assistant", "content": self.ai.reply}], detail["messages"])
        self.assertEqual(1, len(self.ai.calls))

    def test_continue_reuses_id_and_preserves_all_previous_messages(self):
        first = self.ask().json()
        before = self.http.get("/api/conversations/" + first["conversation_id"]).json()
        response = self.ask("음수의 의미는?", first["conversation_id"])
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(first["conversation_id"], response.json()["conversation_id"])
        detail = self.http.get("/api/conversations/" + first["conversation_id"]).json()
        self.assertEqual(before["messages"], detail["messages"][:2])
        self.assertEqual(before["created_at"], detail["created_at"])
        self.assertEqual(4, detail["message_count"])
        self.assertEqual(before["messages"] + [{"role": "user", "content": "음수의 의미는?"}], self.ai.calls[-1]["messages"])
        self.assertEqual(2, len(self.ai.calls))

    def test_each_question_injects_current_shared_summary_without_memos(self):
        summary1 = self.http.get("/api/data/summary").json()
        first = self.ask().json()
        sent1 = json.loads(self.ai.calls[0]["instructions"].split("현재 데이터 요약 JSON:\n", 1)[1])
        self.assertEqual(summary1, sent1)
        self.assertNotIn(SENSITIVE, self.ai.calls[0]["instructions"])
        self.assertNotIn('"memo"', self.ai.calls[0]["instructions"])
        self.data.records["changwon-net-2026-08"]["value"] = 9
        summary2 = self.http.get("/api/data/summary").json()
        self.assertNotEqual(summary1, summary2)
        self.assertEqual(200, self.ask("현재 값을 다시 설명해줘", first["conversation_id"]).status_code)
        sent2 = json.loads(self.ai.calls[1]["instructions"].split("현재 데이터 요약 JSON:\n", 1)[1])
        self.assertEqual(summary2, sent2)
        detail = self.http.get("/api/conversations/" + first["conversation_id"]).json()
        self.assertEqual(summary2, detail["last_summary"])
        self.assertEqual(4, self.data.reads)  # Two API summaries and two chat summaries.

    def test_fixed_rules_preserve_interpretation_boundaries(self):
        self.ask()
        instructions = self.ai.calls[0]["instructions"]
        for rule in ("한국어", "현재 달", "출생·사망", "순유입 전환", "통계적 유의성", "정책 효과",
                     "특정 월", "서버가 제공한 지표", "최신 데이터 요약", "시스템 명령", "3~6문장"):
            self.assertIn(rule, instructions)

    def test_latest_five_pairs_sent_full_history_still_saved(self):
        old = pairs(8)
        saved = self.manual(old)
        response = self.ask("마지막 질문", saved["id"])
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual(old[-10:] + [{"role": "user", "content": "마지막 질문"}], self.ai.calls[0]["messages"])
        detail = self.http.get("/api/conversations/" + saved["id"]).json()
        self.assertEqual(old, detail["messages"][:-2])
        self.assertEqual(18, detail["message_count"])

    def test_history_character_limit_keeps_complete_recent_pairs(self):
        old = pairs(4, user_size=1999, answer_size=3999)
        saved = self.manual(old)
        self.assertEqual(200, self.ask("질문", saved["id"]).status_code)
        sent = self.ai.calls[0]["messages"][:-1]
        self.assertEqual(old[-4:], sent)
        self.assertEqual(12000, sum(len(item["content"]) for item in sent))
        self.assertEqual(10, self.http.get("/api/conversations/" + saved["id"]).json()["message_count"])

    def test_twenty_pairs_block_before_summary_or_paid_call(self):
        saved = self.manual(pairs(20))
        before = deepcopy(self.firebase.storage.documents)
        response = self.ask("추가 질문", saved["id"])
        self.assertEqual(422, response.status_code)
        self.assertEqual([], self.ai.calls)
        self.assertEqual(0, self.data.reads)
        self.assertEqual(before, self.firebase.storage.documents)

    def test_invalid_chat_inputs_have_422_no_calls(self):
        cases = [{}, {"message": ""}, {"message": " \n\t "}, {"message": "가" * 2001},
                 {"message": 2}, {"message": True}, {"message": "질문", "messages": pairs(1)},
                 {"message": "질문", "system": SENSITIVE}, {"message": "질문", "conversation_id": "../other"}]
        for body in cases:
            with self.subTest(body=list(body)):
                response = self.http.post("/api/chat", json=body)
                self.assertEqual(422, response.status_code)
                self.assertNotIn(SENSITIVE, response.text)
        self.assertEqual([], self.ai.calls)
        self.assertEqual({}, self.firebase.storage.documents)

    def test_manual_rejects_roles_incomplete_pairs_extra_fields_and_limits(self):
        cases = [[], [{"role": "assistant", "content": "답변"}], [{"role": "user", "content": "질문"}],
                 [{"role": "system", "content": SENSITIVE}, {"role": "assistant", "content": "답변"}],
                 [{"role": "developer", "content": SENSITIVE}, {"role": "assistant", "content": "답변"}],
                 [{"role": "user", "content": " "}, {"role": "assistant", "content": "답변"}], pairs(21),
                 [{"role": "user", "content": "가" * 2001}, {"role": "assistant", "content": "답변"}],
                 [{"role": "user", "content": "질문"}, {"role": "assistant", "content": "가" * 4001}]]
        for messages in cases:
            self.assertEqual(422, self.http.post("/api/conversations", json={"messages": messages}).status_code)
        for field, value in (("title", "가" * 81), ("created_at", "2026-01-01T00:00:00Z"),
                             ("last_usage", {"input_tokens": 1, "output_tokens": 1}), ("source", "chat"),
                             ("last_model", SENSITIVE), ("verified", True)):
            response = self.http.post("/api/conversations", json={"messages": pairs(1), field: value})
            self.assertEqual(422, response.status_code)
            self.assertNotIn(SENSITIVE, response.text)
        self.assertEqual([], self.ai.calls)
        self.assertEqual({}, self.firebase.storage.documents)

    def test_missing_and_malformed_conversation_ids(self):
        missing = str(uuid4())
        for method in (self.http.get, self.http.delete):
            self.assertEqual(404, method("/api/conversations/" + missing).status_code)
            self.assertEqual(422, method("/api/conversations/not-a-uuid").status_code)
        self.assertEqual(404, self.ask("질문", missing).status_code)
        self.assertEqual([], self.ai.calls)

    def test_key_missing_does_not_break_manual_history_or_existing_routes(self):
        self.ai.config_error = DataServiceError(503, "openai_key_missing", "AI 키가 없습니다.")
        saved = self.manual()
        for path in ("/api/conversations", "/api/conversations/" + saved["id"], "/api/data", "/api/data/summary", "/health", "/docs", "/openapi.json"):
            self.assertEqual(200, self.http.get(path).status_code)
        response = self.ask()
        self.assertEqual(503, response.status_code)
        self.assertEqual("openai_key_missing", response.json()["detail"]["code"])
        self.assertEqual([], self.ai.calls)
        self.assertEqual(204, self.http.delete("/api/conversations/" + saved["id"]).status_code)

    def test_empty_data_and_summary_failure_do_not_call_ai(self):
        self.data.records.clear()
        response = self.ask()
        self.assertEqual(409, response.status_code)
        self.assertEqual("data_empty", response.json()["detail"]["code"])
        self.data.list_data = MagicMock(side_effect=DataServiceError(503, "database_unavailable", "요약 조회 실패"))
        self.assertEqual(503, self.ask().status_code)
        self.assertEqual([], self.ai.calls)
        self.assertEqual({}, self.firebase.storage.documents)

    def test_ai_failure_categories_propagate_without_retries_or_saves(self):
        cases = [(503, "openai_quota_exceeded"), (503, "openai_authentication_error"),
                 (503, "openai_model_unavailable"), (429, "openai_rate_limited"),
                 (504, "openai_timeout"), (502, "openai_empty_response"), (502, "openai_incomplete_response")]
        for status, code in cases:
            self.ai.generate_error = DataServiceError(status, code, "안전한 오류 안내")
            before = len(self.ai.calls)
            response = self.ask()
            self.assertEqual(status, response.status_code)
            self.assertEqual(code, response.json()["detail"]["code"])
            self.assertEqual(before + 1, len(self.ai.calls))
            self.assertEqual({}, self.firebase.storage.documents)

    def test_invalid_answer_is_not_saved(self):
        for reply in ("", " ", "가" * 4001):
            self.ai.reply = reply
            before = len(self.ai.calls)
            response = self.ask()
            self.assertEqual(502, response.status_code)
            self.assertEqual(before + 1, len(self.ai.calls))
            self.assertEqual({}, self.firebase.storage.documents)

    def test_actual_usage_and_missing_usage_are_not_fabricated(self):
        self.ai.usage = {"input_tokens": 21, "output_tokens": 7}
        first = self.ask().json()
        self.assertEqual(self.ai.usage, first["usage"])
        self.ai.usage = None
        second = self.ask("두 번째", first["conversation_id"]).json()
        self.assertIsNone(second["usage"])
        stored = self.http.get("/api/conversations/" + first["conversation_id"]).json()
        self.assertIsNone(stored["last_usage"])

    def test_save_failure_is_503_saved_false_and_single_generation(self):
        self.firebase.storage.failures["create"] = DeadlineExceeded(SENSITIVE)
        response = self.ask()
        self.assertEqual(503, response.status_code)
        self.assertIs(response.json()["saved"], False)
        self.assertEqual("chat_save_failed", response.json()["detail"]["code"])
        self.assertNotIn(SENSITIVE, response.text)
        self.assertEqual(1, len(self.ai.calls))
        self.assertEqual({}, self.firebase.storage.documents)

    def test_concurrent_update_is_409_no_overwrite_no_second_ai_call(self):
        saved = self.manual()
        before = deepcopy(self.firebase.storage.documents[saved["id"]])
        self.ai.hook = lambda: self.firebase.storage.versions.__setitem__(saved["id"], 2)
        response = self.ask("추가", saved["id"])
        self.assertEqual(409, response.status_code)
        self.assertIs(response.json()["saved"], False)
        self.assertEqual(before, self.firebase.storage.documents[saved["id"]])
        self.assertEqual(1, len(self.ai.calls))

    def test_concurrent_delete_is_409_and_not_recreated(self):
        saved = self.manual()
        def delete_during_generation():
            del self.firebase.storage.documents[saved["id"]]
            del self.firebase.storage.versions[saved["id"]]
        self.ai.hook = delete_during_generation
        response = self.ask("추가", saved["id"])
        self.assertEqual(409, response.status_code)
        self.assertIs(response.json()["saved"], False)
        self.assertEqual({}, self.firebase.storage.documents)
        self.assertEqual(1, len(self.ai.calls))

    def test_list_is_updated_latest_first_and_title_does_not_call_ai(self):
        first = self.manual(title="첫 제목")
        second = self.manual(title="둘째 제목")
        self.assertEqual(second["id"], self.http.get("/api/conversations").json()["items"][0]["id"])
        self.assertEqual([], self.ai.calls)
        self.assertEqual(200, self.ask("이어서", first["id"]).status_code)
        self.assertEqual(first["id"], self.http.get("/api/conversations").json()["items"][0]["id"])
        self.assertEqual("첫 제목", self.http.get("/api/conversations/" + first["id"]).json()["title"])

    def test_data_api_crud_and_health_docs_regression(self):
        original_conversations = deepcopy(self.firebase.storage.documents)
        response = self.http.post("/api/data", json={"date": "2026-09-01", "value": -5, "memo": "offline"})
        self.assertEqual(201, response.status_code)
        self.assertEqual(200, self.http.put("/api/data/changwon-net-2026-09", json={"date": "2026-09-01", "value": 0, "memo": "offline"}).status_code)
        self.assertEqual(204, self.http.delete("/api/data/changwon-net-2026-09").status_code)
        self.assertEqual({"status": "ok"}, self.http.get("/health").json())
        self.assertEqual(200, self.http.get("/docs").status_code)
        paths = self.http.get("/openapi.json").json()["paths"]
        for path in ("/health", "/api/data", "/api/data/summary", "/api/chat", "/api/conversations", "/api/conversations/{id}"):
            self.assertIn(path, paths)
        self.assertEqual(original_conversations, self.firebase.storage.documents)
        self.assertEqual([], self.ai.calls)


class LiveChatToolSafetyTests(unittest.TestCase):
    def test_no_flag_calls_neither_live_path(self):
        with patch.object(check_chat, "run_firestore") as firestore, patch.object(check_chat, "run_openai") as openai, patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(2, check_chat.main([]))
        firestore.assert_not_called()
        openai.assert_not_called()

    def test_durable_guard_blocks_second_paid_generation(self):
        with TemporaryDirectory(dir=check_chat.LOCAL) as folder:
            guard = Path(folder) / "attempt.json"
            service = MagicMock()
            first = check_chat.OneAttemptAI(service, "gpt-5.4-mini", guard)
            first.generate("instructions", [{"role": "user", "content": "question"}])
            self.assertEqual(1, first.calls)
            self.assertTrue(guard.exists())
            with self.assertRaises(check_chat.CheckError):
                first.generate("instructions", [])
            second = check_chat.OneAttemptAI(service, "gpt-5.4-mini", guard)
            with self.assertRaises(FileExistsError):
                second.generate("instructions", [])
            self.assertEqual(1, service.generate.call_count)
            self.assertEqual(0, second.calls)

    def test_guard_persists_after_failed_generation_without_retry(self):
        with TemporaryDirectory(dir=check_chat.LOCAL) as folder:
            guard = Path(folder) / "attempt.json"
            service = MagicMock()
            service.generate.side_effect = RuntimeError(SENSITIVE)
            single = check_chat.OneAttemptAI(service, "gpt-5.4-mini", guard)
            with self.assertRaises(RuntimeError):
                single.generate("instructions", [])
            self.assertTrue(guard.exists())
            self.assertNotIn(SENSITIVE, guard.read_text())
            self.assertEqual(1, service.generate.call_count)

    def test_key_missing_does_not_initialize_db_or_reserve_paid_attempt(self):
        with patch("app.config.load_openai_settings", return_value=SimpleNamespace(api_key="")), \
             patch("app.services.firestore.get_firestore_client") as firestore, \
             patch.object(check_chat, "OneAttemptAI") as ai:
            result = check_chat.run_openai()
        self.assertEqual("waiting_for_openai_key", result["status"])
        self.assertEqual(0, result["responses_generation_requests"])
        firestore.assert_not_called()
        ai.assert_not_called()

    def test_cleanup_refuses_changed_or_unowned_payload_and_keeps_document(self):
        client = FakeClient({"own": {"value": "changed"}})
        recording = check_chat.RecordingClient(client, "isolated")
        recording.owned["own"] = [{"value": "expected"}]
        result = check_chat.cleanup_owned(recording)
        self.assertFalse(result["ok"])
        self.assertIn("own", client.storage.documents)
        self.assertFalse(any(call[0] == "delete" for call in client.storage.calls))

    def test_cleanup_only_owned_exact_payload_with_precondition_and_absence(self):
        client = FakeClient({"own": {"value": 1}, "other": {"value": 2}})
        recording = check_chat.RecordingClient(client, "isolated")
        recording.owned["own"] = [{"value": 1}]
        result = check_chat.cleanup_owned(recording)
        self.assertTrue(result["ok"])
        self.assertEqual({"other": {"value": 2}}, client.storage.documents)
        deletes = [call for call in client.storage.calls if call[0] == "delete"]
        self.assertEqual(1, len(deletes))
        self.assertEqual({"last_update_time": 1}, deletes[0][2]["option"])

    def test_recording_proxy_tracks_lost_ack_create_and_rejects_other_collection(self):
        client = FakeClient()
        recording = check_chat.RecordingClient(client, "isolated")
        reference = recording.collection("isolated").document("owned")
        reference.create({"value": 1}, retry=None, timeout=10)
        self.assertEqual({"owned": [{"value": 1}]}, recording.owned)
        with self.assertRaises(check_chat.CheckError):
            recording.collection("data")
        self.assertTrue(check_chat.cleanup_owned(recording)["ok"])

    def test_sdk_timestamp_subclass_matches_expected_write_for_update_cleanup(self):
        timestamp = datetime(2026, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
        sdk_timestamp = DatetimeWithNanoseconds(2026, 1, 1, 12, 0, 0,
                                                nanosecond=123456000, tzinfo=timezone.utc)
        client = FakeClient({"own": {"created_at": sdk_timestamp, "value": 1}})
        recording = check_chat.RecordingClient(client, "isolated")
        recording.owned["own"] = [{"created_at": timestamp, "value": 1}]
        reference = recording.collection("isolated").document("own")
        reference.update({"value": 2}, option={"last_update_time": 1}, retry=None, timeout=10)
        self.assertEqual(2, client.storage.documents["own"]["value"])
        self.assertTrue(check_chat.cleanup_owned(recording)["ok"])
        self.assertEqual({}, client.storage.documents)

    def test_ownership_keeps_nanosecond_and_integer_type_differences(self):
        timestamp = datetime(2026, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
        changed = DatetimeWithNanoseconds(2026, 1, 1, 12, 0, 0,
                                          nanosecond=123456001, tzinfo=timezone.utc)
        self.assertNotEqual(check_chat.ownership_typed(timestamp), check_chat.ownership_typed(changed))
        self.assertNotEqual(check_chat.ownership_typed(1), check_chat.ownership_typed(1.0))
        self.assertNotEqual(check_chat.ownership_typed(1), check_chat.ownership_typed(True))


if __name__ == "__main__":
    unittest.main()
