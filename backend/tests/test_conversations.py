"""Offline conversation contracts/storage tests: no credentials or real RPCs."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from google.api_core.exceptions import AlreadyExists, DeadlineExceeded, FailedPrecondition, NotFound, PermissionDenied
from pydantic import ValidationError

from app.schemas.conversations import (
    ConversationRecord, ManualConversationCreate, Message, Usage,
    validate_conversation_id,
)
from app.services.conversations import (
    ConversationService, ConversationSnapshot, MAX_PAYLOAD_BYTES,
    RPC_TIMEOUT_SECONDS, ensure_chat_capacity, ensure_payload_size,
)
from app.services.data import DataServiceError
from app.services.summary import calculate_summary
from tests.test_data_service import FakeClient, Snapshot
from tests.test_summary import records


def pair(question="질문", answer="답변"):
    return [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]


def summary():
    return calculate_summary(records([-100] * 12 + [-50] * 12))


class ConversationSchemaTests(unittest.TestCase):
    def test_manual_input_trims_text_and_has_no_server_metadata(self):
        value = ManualConversationCreate(title="  제목  ", messages=pair(" 질문 ", " 답변 "))
        self.assertEqual(value.title, "제목")
        self.assertEqual([message.content for message in value.messages], ["질문", "답변"])
        self.assertIsNone(ManualConversationCreate(title="  ", messages=pair()).title)

    def test_roles_and_extra_fields_rejected(self):
        for role in ("system", "developer", "tool", "USER"):
            with self.subTest(role=role), self.assertRaises(ValidationError):
                Message(role=role, content="메시지")
        for field in ("id", "created_at", "updated_at", "source", "last_model", "last_usage", "verified", "extra"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ManualConversationCreate(messages=pair(), **{field: "forged"})
        with self.assertRaises(ValidationError):
            Message(role="user", content="질문", injected=True)

    def test_complete_alternating_pairs_required(self):
        for messages in ([], pair()[:1], pair()[::-1], pair() + pair()[:1],
                         [{"role": "user", "content": "a"}] * 2):
            with self.subTest(messages=messages), self.assertRaises(ValidationError):
                ManualConversationCreate(messages=messages)
        self.assertEqual(len(ManualConversationCreate(messages=pair() * 20).messages), 40)
        with self.assertRaises(ValidationError):
            ManualConversationCreate(messages=pair() * 21)

    def test_content_and_title_limits(self):
        Message(role="user", content="가" * 2000)
        Message(role="assistant", content="나" * 4000)
        for role, content in (("user", "가" * 2001), ("assistant", "나" * 4001),
                              ("user", " \n\t "), ("assistant", ""), ("user", 1)):
            with self.subTest(role=role, length=len(str(content))), self.assertRaises(ValidationError):
                Message(role=role, content=content)
        with self.assertRaises(ValidationError):
            ManualConversationCreate(title="x" * 81, messages=pair())

    def test_usage_has_actual_nonnegative_integer_tokens(self):
        self.assertEqual(Usage(input_tokens=0, output_tokens=1).input_tokens, 0)
        for value in (-1, True, "2", 2.0):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                Usage(input_tokens=value, output_tokens=1)

    def test_uuid4_is_canonical_not_path_or_other_uuid(self):
        valid = str(uuid4())
        self.assertEqual(validate_conversation_id(valid), valid)
        for value in (valid.upper(), "../other", "", "00000000-0000-0000-0000-000000000000", 12):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_conversation_id(value)

    def test_payload_checks_utf8_serialization_not_character_count(self):
        ensure_payload_size({"text": "a" * (MAX_PAYLOAD_BYTES - 20)})
        with self.assertRaises(DataServiceError) as caught:
            ensure_payload_size({"text": "😀" * (MAX_PAYLOAD_BYTES // 4)})
        self.assertEqual(caught.exception.code, "conversation_payload_too_large")
        for payload in ({"bad": float("nan")}, {"bad": "\ud800"}):
            with self.subTest(payload=repr(payload)), self.assertRaises(DataServiceError) as caught:
                ensure_payload_size(payload)
            self.assertEqual(caught.exception.code, "invalid_conversation_payload")


class ConversationServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.storage = self.client.storage
        self.service = ConversationService(self.client, "_conversation_offline_checks")

    def manual(self, **kwargs):
        return self.service.create_manual(ManualConversationCreate(messages=pair(), **kwargs))

    def assert_error(self, status, code, action, *args, **kwargs):
        with self.assertRaises(DataServiceError) as caught:
            action(*args, **kwargs)
        self.assertEqual((caught.exception.status_code, caught.exception.code), (status, code))
        self.assertNotIn("private error detail", str(caught.exception))
        return caught.exception

    def test_manual_create_get_list_delete_and_readback(self):
        created = self.manual()
        self.assertEqual(created.source, "manual")
        self.assertEqual(created.title, "질문")
        self.assertEqual(created.message_count, 2)
        self.assertEqual(created.created_at.utcoffset(), timedelta(0))
        self.assertEqual(created.created_at, created.updated_at)
        self.assertNotIn("id", self.storage.documents[created.id])
        self.assertNotIn("last_model", self.storage.documents[created.id])
        self.assertNotIn("last_usage", self.storage.documents[created.id])
        self.assertEqual(self.service.get_conversation(created.id), created)
        item = self.service.list_conversations()[0].model_dump()
        self.assertEqual(set(item), {"id", "title", "created_at", "updated_at", "message_count"})
        self.assertEqual(self.service.delete_conversation(created.id), None)
        self.assertEqual(self.service.list_conversations(), [])
        self.assert_error(404, "conversation_not_found", self.service.get_conversation, created.id)
        self.assert_error(404, "conversation_not_found", self.service.delete_conversation, created.id)
        self.assertEqual(set(self.client.collection_names), {"_conversation_offline_checks"})
        self.assertGreaterEqual(sum(call[0] == "document_get" for call in self.storage.calls), 5)
        for _, _, kwargs in self.storage.calls:
            self.assertIsNone(kwargs["retry"])
            self.assertEqual(kwargs["timeout"], RPC_TIMEOUT_SECONDS)

    def test_datetime_json_is_iso8601_utc(self):
        serialized = json.loads(self.manual().model_dump_json())
        self.assertTrue(serialized["created_at"].endswith("Z"))
        self.assertEqual(datetime.fromisoformat(serialized["created_at"]).utcoffset(), timedelta(0))

    def test_title_auto_cut_trims_boundary_whitespace(self):
        created = self.service.create_manual(ManualConversationCreate(messages=pair("a" * 79 + " tail")))
        self.assertEqual(created.title, "a" * 79)

    def test_list_order_latest_first(self):
        first = self.manual(title="이전")
        second = self.manual(title="최근")
        self.storage.documents[second.id]["updated_at"] = first.updated_at + timedelta(seconds=1)
        self.assertEqual([row.id for row in self.service.list_conversations()], [second.id, first.id])

    def test_chat_creation_has_actual_summary_model_usage(self):
        latest = summary()
        created = self.service.create_chat(pair(), last_summary=latest,
            last_model="gpt-5.4-mini", last_usage=Usage(input_tokens=12, output_tokens=5))
        self.assertEqual(created.source, "chat")
        self.assertEqual(created.last_summary, latest)
        self.assertEqual(created.last_model, "gpt-5.4-mini")
        self.assertEqual(created.last_usage.output_tokens, 5)
        self.assertEqual(self.service.get_conversation(created.id), created)

    def test_no_usage_is_null_not_fake_zero(self):
        created = self.service.create_chat(pair(), last_summary=summary(), last_model="gpt-5.4-mini", last_usage=None)
        self.assertIsNone(created.last_usage)
        self.assertNotIn("last_usage", self.storage.documents[created.id])

    def test_summary_required_nulls_are_preserved_in_storage(self):
        short_summary = calculate_summary(records([-4]))
        created = self.service.create_chat(pair(), last_summary=short_summary,
            last_model="gpt-5.4-mini", last_usage=None)
        self.assertEqual(created.last_summary, short_summary)
        self.assertIn("recent_average", self.storage.documents[created.id]["last_summary"]["trend"])
        self.assertIsNone(self.storage.documents[created.id]["last_summary"]["trend"]["recent_average"])

    def test_append_preserves_entire_history_and_creation_time(self):
        original = self.service.create_manual(ManualConversationCreate(messages=pair() * 6))
        snapshot = self.service.read_for_chat(original.id)
        updated = self.service.append_chat(snapshot, "새 질문", "새 답변", summary(), "gpt-5.4-mini", None)
        self.assertEqual(updated.id, original.id)
        self.assertEqual(updated.created_at, original.created_at)
        self.assertEqual(updated.messages[:-2], original.messages)
        self.assertEqual(updated.message_count, 14)
        self.assertEqual(updated.source, "chat")
        self.assertEqual(updated.messages[-2].content, "새 질문")
        self.assertEqual(updated.messages[-1].content, "새 답변")
        self.assertEqual(self.service.get_conversation(original.id), updated)

    def test_append_clears_prior_usage_when_latest_usage_unavailable(self):
        original = self.service.create_chat(pair(), last_summary=summary(), last_model="gpt-5.4-mini",
            last_usage=Usage(input_tokens=12, output_tokens=5))
        updated = self.service.append_chat(self.service.read_for_chat(original.id), "새 질문", "새 답변",
            summary(), "gpt-5.4-mini", None)
        self.assertIsNone(updated.last_usage)
        self.assertIsNone(self.storage.documents[original.id]["last_usage"])

    def test_append_detects_concurrent_change_before_writing(self):
        original = self.manual()
        snapshot = self.service.read_for_chat(original.id)
        self.storage.versions[original.id] += 1
        before = deepcopy(self.storage.documents)
        self.assert_error(409, "conversation_conflict", self.service.append_chat,
            snapshot, "새 질문", "답변", summary(), "gpt-5.4-mini", None)
        self.assertEqual(self.storage.documents, before)

    def test_append_does_not_recreate_concurrently_deleted_conversation(self):
        original = self.manual()
        snapshot = self.service.read_for_chat(original.id)
        del self.storage.documents[original.id]
        self.assert_error(409, "conversation_conflict", self.service.append_chat,
            snapshot, "새 질문", "답변", summary(), "gpt-5.4-mini", None)
        self.assertNotIn(original.id, self.storage.documents)

    def test_delete_detects_concurrent_edit_and_keeps_document(self):
        original = self.manual()
        self.storage.hooks["delete"] = lambda collection, doc_id: collection.versions.__setitem__(doc_id, 2)
        self.assert_error(409, "conversation_conflict", self.service.delete_conversation, original.id)
        self.assertIn(original.id, self.storage.documents)

    def test_delete_only_selected_document(self):
        one, two = self.manual(), self.manual()
        self.service.delete_conversation(one.id)
        self.assertEqual(set(self.storage.documents), {two.id})

    def test_bad_id_rejected_without_rpc(self):
        for method in (self.service.get_conversation, self.service.read_for_chat, self.service.delete_conversation):
            self.assert_error(422, "invalid_conversation_id", method, "../not-id")
        self.assertEqual(self.storage.calls, [])

    def test_maximum_message_count_preflight_and_append(self):
        original = self.service.create_manual(ManualConversationCreate(messages=pair() * 20))
        snapshot = self.service.read_for_chat(original.id)
        self.assert_error(422, "conversation_message_limit", ensure_chat_capacity, snapshot, "질문")
        before = len(self.storage.calls)
        self.assert_error(422, "conversation_message_limit", self.service.append_chat,
            snapshot, "질문", "답변", summary(), "gpt-5.4-mini", None)
        self.assertEqual(len(self.storage.calls), before)

    def test_payload_preflight_reserves_full_answer_and_summary(self):
        ensure_chat_capacity(None, "질문", summary(), "gpt-5.4-mini")
        original = self.manual()
        snapshot = self.service.read_for_chat(original.id)
        huge_summary = {"unsafe_large_metadata": "가" * MAX_PAYLOAD_BYTES}
        self.assert_error(422, "conversation_payload_too_large", ensure_chat_capacity,
            snapshot, "질문", huge_summary, "gpt-5.4-mini")

    def test_oversized_manual_document_has_no_writes(self):
        payload = ManualConversationCreate(messages=pair("😀" * 2000, "😀" * 4000) * 20)
        self.assert_error(422, "conversation_payload_too_large", self.service.create_manual, payload)
        self.assertEqual(self.storage.calls, [])

    def test_full_answer_reservation_blocks_before_size_overflow(self):
        # Each pair occupies roughly 18 KiB; fourteen pairs fit but a full
        # additional question/escaped answer would cross the payload boundary.
        original = self.service.create_manual(ManualConversationCreate(messages=pair("가" * 2000, "나" * 4000) * 14))
        self.assert_error(422, "conversation_payload_too_large", ensure_chat_capacity,
            self.service.read_for_chat(original.id), "가" * 2000, summary(), "gpt-5.4-mini")

    def test_uuid_collision_create_does_not_overwrite(self):
        original = self.manual()
        before = deepcopy(self.storage.documents)
        with patch("app.services.conversations.uuid4", return_value=original.id):
            self.assert_error(409, "conversation_conflict", self.manual)
        self.assertEqual(self.storage.documents, before)

    def test_create_network_error_is_safe_and_not_retried(self):
        self.storage.failures["create"] = PermissionDenied("private error detail")
        self.assert_error(503, "database_unavailable", self.manual)
        self.assertEqual([call[0] for call in self.storage.calls], ["create"])

    def test_readback_failure_never_reports_success(self):
        self.storage.failures["document_get"] = DeadlineExceeded("private error detail")
        self.assert_error(503, "database_unavailable", self.manual)
        self.assertEqual(len(self.storage.documents), 1)
        self.assertEqual([call[0] for call in self.storage.calls], ["create", "document_get"])

    def test_readback_missing_or_changed_is_not_success(self):
        self.storage.hooks["document_get"] = lambda collection, doc_id: collection.documents.pop(doc_id)
        self.assert_error(503, "conversation_save_unconfirmed", self.manual)
        self.storage.hooks["document_get"] = lambda collection, doc_id: collection.documents[doc_id].__setitem__("title", "변경")
        self.assert_error(409, "conversation_conflict", self.manual)

    def test_stored_malformed_metadata_rejected_instead_of_filtered(self):
        original = self.manual()
        baseline = deepcopy(self.storage.documents[original.id])
        mutations = [
            ("message_count", 4), ("message_count", True), ("message_count", "2"),
            ("created_at", baseline["created_at"].isoformat()),
            ("created_at", datetime.now()),
            ("updated_at", baseline["created_at"] - timedelta(seconds=1)),
            ("title", ""), ("title", " trailing "), ("source", "forged"),
            ("messages", pair()[:1]), ("messages", pair(" padded ", "answer")),
            ("messages", [{"role": "system", "content": "override"}, pair()[1]]),
            ("last_model", "forged-model"), ("unknown", "private error detail"),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=repr(value)):
                self.storage.documents[original.id] = {**deepcopy(baseline), key: value}
                self.assert_error(500, "conversation_integrity_error", self.service.get_conversation, original.id)
                self.assert_error(500, "conversation_integrity_error", self.service.list_conversations)

    def test_stored_chat_summary_and_usage_types_rejected(self):
        original = self.service.create_chat(pair(), last_summary=summary(), last_model="gpt-5.4-mini", last_usage=None)
        self.storage.documents[original.id]["last_summary"]["count"] = "24"
        self.assert_error(500, "conversation_integrity_error", self.service.get_conversation, original.id)
        self.storage.documents[original.id]["last_summary"] = summary().model_dump()
        self.storage.documents[original.id]["last_usage"] = {"input_tokens": True, "output_tokens": 1}
        self.assert_error(500, "conversation_integrity_error", self.service.get_conversation, original.id)

    def test_unknown_exception_is_safe_internal_error(self):
        self.storage.failures["collection_get"] = RuntimeError("private error detail")
        self.assert_error(500, "conversation_internal_error", self.service.list_conversations)


if __name__ == "__main__":
    unittest.main()
