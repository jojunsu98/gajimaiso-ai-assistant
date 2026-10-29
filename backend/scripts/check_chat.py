"""Explicit integration checks. Ordinary execution makes no SDK/network calls.

--live-firestore uses real Firestore and an explicitly fake AI in an isolated
collection. --live-openai / --live-gemini each permit at most one generation
attempt, guarded by separate durable exclusive local files; successful demo
conversations are retained. Providers are selected explicitly, never as fallback.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from uuid import uuid4


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
LOCAL = PROJECT_ROOT / ".local"
ATTEMPT_GUARD = LOCAL / "chat-openai-attempt.json"
GEMINI_ATTEMPT_GUARD = LOCAL / "chat-gemini-attempt.json"
REQUEST_TIMEOUT = 10
QUESTION = (
    "최신 저장 월 기준으로 최근 12개월과 직전 12개월의 월평균 순이동을 비교해줘. "
    "전체 인구 증감이나 이동 원인까지 이 자료로 확정할 수 있는지도 알려줘."
)
FAKE_REPLY = "모의 검증 응답입니다. 실제 OpenAI를 호출하지 않았습니다."
FAKE_MODEL = "fake-ai-no-network"
sys.path.insert(0, str(BACKEND_ROOT))

from scripts.check_data_api import _digest, _typed, independent_source_summary


class CheckError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise CheckError(code)


def safe_error(error):
    if isinstance(error, CheckError):
        return error.code
    # SDK messages, request bodies and credentials are intentionally omitted.
    from app.services.data import DataServiceError
    if isinstance(error, DataServiceError):
        return error.code
    return {
        "FirebaseError": "firebase_configuration_or_connection",
        "DeadlineExceeded": "database_timeout", "TimeoutError": "request_timeout",
        "PermissionDenied": "permission_denied", "Unauthenticated": "unauthenticated",
        "ServiceUnavailable": "database_unavailable", "TransportError": "database_unavailable",
        "FailedPrecondition": "write_condition_failed", "FileExistsError": "openai_attempt_already_recorded",
    }.get(type(error).__name__, "unexpected_error_details_suppressed")


def snapshot_collection(client, name):
    snapshots = client.collection(name).get(retry=None, timeout=REQUEST_TIMEOUT)
    return sorted([
        {"id": item.id, "data": _typed(item.to_dict()),
         "create_time": _typed(item.create_time), "update_time": _typed(item.update_time)}
        for item in snapshots
    ], key=lambda item: item["id"])


def ownership_typed(value):
    """Same persisted timestamp despite SDK datetime subclass; keep nanoseconds.

    Full production before/after snapshots deliberately retain concrete types
    via _typed. This separate comparison is only for our expected write payload.
    """
    if isinstance(value, datetime):
        return {"timestamp": {
            "utc_second": value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            # SDK to_dict/deepcopy can construct this subclass from microseconds,
            # leaving its optional nanosecond slot at zero.
            "nanosecond": getattr(value, "nanosecond", 0) or value.microsecond * 1000,
        }}
    if isinstance(value, dict):
        return {"dict": [[key, ownership_typed(value[key])] for key in sorted(value)]}
    if isinstance(value, (list, tuple)):
        return {type(value).__name__: [ownership_typed(item) for item in value]}
    return _typed(value)


class RecordingReference:
    """Record exact owned documents before writes, including lost-ack failures."""

    def __init__(self, owner, reference):
        self.owner = owner
        self.reference = reference
        self.id = reference.id

    def __getattr__(self, name):
        return getattr(self.reference, name)

    def create(self, payload, **kwargs):
        before = self.reference.get(retry=None, timeout=REQUEST_TIMEOUT)
        require(not before.exists, "generated_document_already_exists")
        require(self.id not in self.owner.owned, "duplicate_owned_id")
        self.owner.owned[self.id] = [deepcopy(payload)]
        return self.reference.create(payload, **kwargs)

    def update(self, payload, **kwargs):
        require(self.id in self.owner.owned, "refusing_update_of_unowned_document")
        before = self.reference.get(retry=None, timeout=REQUEST_TIMEOUT)
        require(before.exists and any(ownership_typed(before.to_dict()) == ownership_typed(allowed)
                for allowed in self.owner.owned[self.id]), "owned_document_changed")
        self.owner.owned[self.id].append({**before.to_dict(), **deepcopy(payload)})
        return self.reference.update(payload, **kwargs)

    def delete(self, **kwargs):
        require(self.id in self.owner.owned, "refusing_delete_of_unowned_document")
        before = self.reference.get(retry=None, timeout=REQUEST_TIMEOUT)
        require(before.exists and any(ownership_typed(before.to_dict()) == ownership_typed(allowed)
                for allowed in self.owner.owned[self.id]), "owned_document_changed")
        return self.reference.delete(**kwargs)


class RecordingCollection:
    def __init__(self, owner, collection):
        self.owner = owner
        self.collection = collection

    def __getattr__(self, name):
        return getattr(self.collection, name)

    def document(self, document_id):
        return RecordingReference(self.owner, self.collection.document(document_id))


class RecordingClient:
    """Internal test dependency only; collection cannot be selected over HTTP."""

    def __init__(self, client, collection_name):
        self.client = client
        self.collection_name = collection_name
        self.owned = {}

    def __getattr__(self, name):
        return getattr(self.client, name)

    def collection(self, name):
        require(name == self.collection_name, "unexpected_write_collection")
        return RecordingCollection(self, self.client.collection(name))


def cleanup_owned(recording, keep_ids=()):
    outcomes = []
    for document_id, allowed_payloads in recording.owned.items():
        if document_id in keep_ids:
            outcomes.append({"id": document_id, "ok": True, "retained_demo": True})
            continue
        reference = recording.client.collection(recording.collection_name).document(document_id)
        try:
            current = reference.get(retry=None, timeout=REQUEST_TIMEOUT)
            if current.exists:
                require(current.update_time is not None and any(
                    ownership_typed(current.to_dict()) == ownership_typed(payload) for payload in allowed_payloads
                ), "cleanup_ownership_not_confirmed")
                option = recording.client.write_option(last_update_time=current.update_time)
                reference.delete(option=option, retry=None, timeout=REQUEST_TIMEOUT)
            absent = not reference.get(retry=None, timeout=REQUEST_TIMEOUT).exists
            outcomes.append({"id": document_id, "ok": absent, "absent": absent})
        except Exception as error:
            outcomes.append({"id": document_id, "ok": False, "error": safe_error(error)})
    return {"ok": all(item["ok"] for item in outcomes), "documents": outcomes}


class FakeAI:
    """Named mock used only by this explicit integration tool and local tests."""

    def __init__(self):
        self.calls = []

    def validate_configuration(self):
        return None

    def generate(self, instructions, messages):
        from app.services.openai_client import AIResult
        self.calls.append({"instructions": instructions, "messages": deepcopy(messages)})
        return AIResult(reply=FAKE_REPLY, model=FAKE_MODEL, usage=None)


class OneAttemptAI:
    def __init__(self, service, model, guard=ATTEMPT_GUARD):
        self.service = service
        self.model = model
        self.guard = Path(guard)
        self.calls = 0
        self.instructions = None
        self.messages = None
        self.answer = None
        self.provider_error = {}

    def validate_configuration(self):
        self.service.validate_configuration()

    def generate(self, instructions, messages):
        require(self.calls == 0, "multiple_generation_attempts_blocked")
        self.guard.parent.mkdir(exist_ok=True)
        # This file is intentionally never removed on failure or success.
        with self.guard.open("x", encoding="utf-8") as output:
            json.dump({"started_at_utc": datetime.now(timezone.utc).isoformat(),
                       "model": self.model, "generation_attempt_reserved": 1,
                       "execution_id": self.guard.stem}, output)
            output.flush()
        self.calls = 1
        self.instructions = instructions
        self.messages = deepcopy(messages)
        try:
            self.answer = self.service.generate(instructions, messages)
            return self.answer
        except Exception as error:
            # The app suppresses SDK messages; retain only fixed diagnostic fields
            # from its original exception context, never bodies/headers/key text.
            import openai
            original = error.__context__
            if isinstance(original, openai.APIStatusError):
                status = original.status_code
                if type(status) is int and 100 <= status <= 599:
                    self.provider_error["provider_http_status"] = status
                allowed = {"insufficient_quota", "billing_hard_limit_reached", "billing_not_active",
                           "invalid_api_key", "model_not_found", "model_not_available",
                           "unsupported_model", "invalid_model", "rate_limit_exceeded",
                           "invalid_request_error", "unsupported_parameter", "unsupported_value",
                           "permission_denied", "access_denied"}
                code = getattr(original, "code", None)
                self.provider_error["provider_error_code"] = (
                    code if isinstance(code, str) and code in allowed else
                    None if code is None else "unrecognized_code_suppressed")
            raise


def _status(response, expected, code):
    require(response.status_code == expected, code)
    return response.json() if expected != 204 else None


def _check_detail(detail, messages, summary=None, model=None):
    require(detail["messages"] == messages, "retrieved_messages_differ")
    require(detail["message_count"] == len(messages), "retrieved_count_differ")
    require(detail["source"] == ("chat" if model else "manual"), "source_mismatch")
    if summary is not None:
        require(_typed(detail["last_summary"]) == _typed(summary), "stored_summary_mismatch")
        require(detail["last_model"] == model, "stored_model_mismatch")


def _preserved(before, after, excluded=()):
    filtered = [item for item in after if item["id"] not in excluded]
    return {"ok": before == filtered, "before_count": len(before), "after_count": len(after),
            "before_sha256_including_metadata": _digest(before),
            "after_sha256_including_metadata": _digest(filtered),
            "excluded_owned_demo_ids": list(excluded),
            "comparison": "all IDs, typed payloads, create_time and update_time"}


def _new_result(mode):
    return {"mode": mode, "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "ok": False, "responses_generation_requests": 0, "chat_completions_generation_requests": 0,
            "model": None, "usage": None,
            "cleanup": {"ok": True, "documents": []},
            "data_preserved": {"ok": False}, "existing_conversations_preserved": {"ok": False}}


def _build_test_app(client, collection_name, ai, title_prefix=""):
    from app.main import create_app
    from app.routers.chat import get_chat_service
    from app.routers.conversations import get_conversation_service
    from app.routers.data import get_data_service
    from app.services.chat import ChatService
    from app.services.conversations import ConversationService
    from app.services.data import DataService

    app = create_app()
    recording = RecordingClient(client, collection_name)
    conversations = ConversationService(recording, collection_name=collection_name)
    data = DataService(client)
    chat = ChatService(conversations, data, ai, title_prefix=title_prefix)
    app.dependency_overrides[get_conversation_service] = lambda: conversations
    app.dependency_overrides[get_data_service] = lambda: data
    app.dependency_overrides[get_chat_service] = lambda: chat
    return app, recording


def run_firestore():
    from fastapi.testclient import TestClient
    from app.services.firestore import get_firestore_client

    result = _new_result("live-firestore-fake-ai")
    client = recording = before_data = before_conversations = None
    ai = FakeAI()
    try:
        client = get_firestore_client()
        before_data = snapshot_collection(client, "data")
        before_conversations = snapshot_collection(client, "conversations")
        expected_records, _, source_hash = independent_source_summary()
        require(len(before_data) == len(expected_records) == 128, "original_128_count_mismatch")
        result["source_sha256"] = source_hash
        run_id = uuid4().hex
        collection = "_conversation_checks_" + run_id
        require(not snapshot_collection(client, collection), "isolated_collection_not_empty")
        app, recording = _build_test_app(client, collection, ai)
        result["isolated_collection"] = collection
        result["stages"] = []
        with TestClient(app, raise_server_exceptions=False) as http:
            actual_records = _status(http.get("/api/data"), 200, "data_read_failed")
            require(_typed(actual_records) == _typed({"items": expected_records, "count": 128}), "source_values_changed")
            summary = _status(http.get("/api/data/summary"), 200, "summary_read_failed")
            manual_messages = [{"role": "user", "content": run_id + " 수동 검증"},
                               {"role": "assistant", "content": "로컬 도구의 수동 대화 저장 검사입니다."}]
            manual = _status(http.post("/api/conversations", json={"messages": manual_messages}), 201, "manual_save_failed")
            manual_id = manual["id"]
            _check_detail(manual, manual_messages)
            require(not ai.calls, "manual_save_called_ai")
            result["stages"].append("manual_create_201_without_ai")
            question = run_id + " 첫 번째 모의 질문"
            first = _status(http.post("/api/chat", json={"message": question}), 200, "new_chat_failed")
            require(first["saved"] is True and first["usage"] is None and first["model"] == FAKE_MODEL, "new_chat_metadata_invalid")
            chat_id = first["conversation_id"]
            require(chat_id != manual_id, "server_id_collision")
            question2 = run_id + " 이어지는 모의 질문"
            continued = _status(http.post("/api/chat", json={"message": question2, "conversation_id": chat_id}), 200, "continued_chat_failed")
            require(continued["conversation_id"] == chat_id and continued["saved"] is True, "continued_id_changed")
            expected_messages = [{"role": "user", "content": question}, {"role": "assistant", "content": FAKE_REPLY},
                                 {"role": "user", "content": question2}, {"role": "assistant", "content": FAKE_REPLY}]
            detail = _status(http.get("/api/conversations/" + chat_id), 200, "chat_reload_failed")
            _check_detail(detail, expected_messages, summary, FAKE_MODEL)
            require(len(ai.calls) == 2 and ai.calls[1]["messages"] == expected_messages[:-1], "fake_ai_history_mismatch")
            require(all(json.loads(call["instructions"].split("현재 데이터 요약 JSON:\n", 1)[1]) == summary
                        for call in ai.calls), "model_summary_injection_mismatch")
            result["stages"].extend(["new_chat_200_saved", "continue_chat_200_saved", "detail_reload_200_all_four_messages"])
            listing = _status(http.get("/api/conversations"), 200, "conversation_list_failed")
            fields = {"id", "title", "created_at", "updated_at", "message_count"}
            require(listing["count"] == 2 and all(set(item) == fields for item in listing["items"]), "list_contract_invalid")
            require(listing["items"][0]["id"] == chat_id, "list_updated_order_invalid")
            result["stages"].append("list_200_metadata_only_latest_first")
            for document_id in (manual_id, chat_id):
                response = http.delete("/api/conversations/" + document_id)
                require(response.status_code == 204 and response.content == b"", "delete_failed")
                require(http.get("/api/conversations/" + document_id).status_code == 404, "deleted_detail_not_404")
            require(_status(http.get("/api/conversations"), 200, "empty_list_failed") == {"items": [], "count": 0}, "isolated_records_remain")
            result["stages"].append("both_delete_204_absence_404_empty_list")
            result["api_checks_passed"] = True
            result["fake_ai_calls"] = len(ai.calls)
            result["fake_ai_model_label"] = FAKE_MODEL
            result["fake_ai_usage"] = None
    except Exception as error:
        result["error"] = safe_error(error)
    finally:
        if recording is not None:
            result["cleanup"] = cleanup_owned(recording)
        if client is not None and before_data is not None and before_conversations is not None:
            try:
                result["data_preserved"] = _preserved(before_data, snapshot_collection(client, "data"))
                result["existing_conversations_preserved"] = _preserved(before_conversations, snapshot_collection(client, "conversations"))
            except Exception as error:
                result["preservation_error"] = safe_error(error)
    result["ok"] = bool(result.get("api_checks_passed")) and all(result[key]["ok"] for key in
        ("cleanup", "data_preserved", "existing_conversations_preserved")) and "error" not in result
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    return result


def _openai_run_paths(run_id):
    require(isinstance(run_id, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", run_id),
            "invalid_explicit_run_id")
    return (LOCAL / f"chat-openai-{run_id}-attempt.json",
            LOCAL / f"chat-openai-{run_id}-live.json")


def run_openai(run_id=None):
    from app.config import load_openai_settings
    from app.services.openai_client import OpenAIService

    guard = ATTEMPT_GUARD if run_id is None else _openai_run_paths(run_id)[0]
    return _run_live_provider("openai", load_openai_settings, OpenAIService, guard)


def run_gemini():
    from app.config import load_gemini_settings
    from app.services.gemini_client import GeminiService

    return _run_live_provider("gemini", load_gemini_settings, GeminiService, GEMINI_ATTEMPT_GUARD)


def _run_live_provider(provider, load_settings, service_factory, guard):
    """One explicit provider, sharing the existing API/storage verification path."""
    from fastapi.testclient import TestClient
    from app.services.firestore import get_firestore_client

    require(provider in {"openai", "gemini"}, "unsupported_live_provider")
    result = _new_result("live-" + provider)
    result.update({"provider": provider, "generation_requests": 0})
    client = recording = before_data = before_conversations = None
    ai = None
    retained = []
    try:
        if provider == "openai":
            from app.config import load_ai_provider
            require(load_ai_provider() == "openai", "configured_provider_is_not_openai")
        settings = load_settings()
        if not settings.api_key.strip():
            result.update({"status": "waiting_for_" + provider + "_key", "note": "실제 AI 연결 대기. backend/.env 또는 프로세스 환경변수에 해당 공급자의 키를 설정하세요."})
            return result
        service = service_factory(settings)
        service.validate_configuration()
        result["requested_model"] = settings.model
        if provider == "openai":
            result.update({"base_url": settings.base_url, "api": "chat.completions", "gateway": "codyssey"})
        require(not guard.exists(), provider + "_attempt_already_recorded")
        ai = OneAttemptAI(service, settings.model, guard=guard)
        client = get_firestore_client()
        before_data = snapshot_collection(client, "data")
        before_conversations = snapshot_collection(client, "conversations")
        require(len(before_data) == 128, "original_128_count_mismatch")
        title_prefix = "[코디세이 GPT 연결 검증] " if provider == "openai" else "[연결 검증] "
        app, recording = _build_test_app(client, "conversations", ai, title_prefix=title_prefix)
        with TestClient(app, raise_server_exceptions=False) as http:
            summary = _status(http.get("/api/data/summary"), 200, "summary_read_failed")
            result["summary"] = summary
            response = http.post("/api/chat", json={"message": QUESTION})
            result["http_status"] = response.status_code
            if response.status_code != 200:
                body = response.json()
                result["http_status"] = response.status_code
                result["chat_error_code"] = body.get("detail", {}).get("code", "unknown_chat_error")
                result["saved"] = body.get("saved", False)
                raise CheckError("live_chat_failed")
            body = response.json()
            require(ai.calls == 1 and body["saved"] is True, "generation_or_save_count_invalid")
            require(json.loads(ai.instructions.split("현재 데이터 요약 JSON:\n", 1)[1]) == summary,
                    "model_summary_injection_mismatch")
            document_id = body["conversation_id"]
            require(document_id in recording.owned, "demo_ownership_not_confirmed")
            # Successful saved demos are kept even if a later read check fails.
            retained.append(document_id)
            result["demo_conversation_id"] = document_id
            result["saved"] = True
            detail = _status(http.get("/api/conversations/" + document_id), 200, "demo_reload_failed")
            messages = [{"role": "user", "content": QUESTION}, {"role": "assistant", "content": body["reply"]}]
            _check_detail(detail, messages, summary, body["model"])
            require(detail["title"].startswith(title_prefix.strip()), "demo_title_missing_marker")
            listing = _status(http.get("/api/conversations"), 200, "demo_list_failed")
            require(sum(item["id"] == document_id for item in listing["items"]) == 1, "demo_missing_from_list")
            require(detail.get("last_usage") == body["usage"], "demo_usage_mismatch")
            result.update({"api_checks_passed": True, "question": QUESTION, "reply": body["reply"],
                           "model": body["model"], "usage": body["usage"], "summary": summary,
                           "title": detail["title"],
                           "reload_matches": True, "listed": True,
                           "answer_review_required": "수치·기간·전체 인구 증감 및 원인 해석 한계는 반환된 답변과 요약을 직접 대조하세요. 재호출하지 마세요."})
    except Exception as error:
        result["error"] = (provider + "_attempt_already_recorded"
                           if isinstance(error, FileExistsError) else safe_error(error))
    finally:
        if ai is not None:
            result["generation_requests"] = ai.calls
            result["chat_completions_generation_requests"] = ai.calls if provider == "openai" else 0
            result.update(ai.provider_error)
            if ai.instructions is not None:
                result["transmitted_summary"] = json.loads(ai.instructions.split("현재 데이터 요약 JSON:\n", 1)[1])
                result["question"] = QUESTION
            if ai.answer is not None:
                result.update({"reply": ai.answer.reply, "model": ai.answer.model, "usage": ai.answer.usage})
        if recording is not None:
            result["cleanup"] = cleanup_owned(recording, keep_ids=retained)
        if client is not None and before_data is not None and before_conversations is not None:
            try:
                result["data_preserved"] = _preserved(before_data, snapshot_collection(client, "data"))
                result["existing_conversations_preserved"] = _preserved(before_conversations, snapshot_collection(client, "conversations"), retained)
            except Exception as error:
                result["preservation_error"] = safe_error(error)
        result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["ok"] = bool(result.get("api_checks_passed")) and all(result[key]["ok"] for key in
        ("cleanup", "data_preserved", "existing_conversations_preserved")) and "error" not in result
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="실제 DB + 모의 AI / 최대 한 차례의 명시적 공급자별 실제 AI 검증을 분리합니다.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live-firestore", action="store_true")
    mode.add_argument("--live-openai", action="store_true")
    mode.add_argument("--live-gemini", action="store_true")
    parser.add_argument("--run-id", help="사용자가 별도로 승인한 OpenAI 1회 실행의 고유 식별자; 재사용·자동 생성 금지")
    args = parser.parse_args(argv)
    if args.run_id is not None:
        if not args.live_openai:
            parser.error("--run-id는 --live-openai에만 사용할 수 있습니다.")
        try:
            guard, separate_report = _openai_run_paths(args.run_id)
        except CheckError:
            parser.error("--run-id는 소문자·숫자·하이픈 1~64자로 지정하세요.")
        if guard.exists() or separate_report.exists():
            print(json.dumps({"ok": False, "error": "openai_run_already_recorded", "generation_requests": 0}))
            return 1
    if not (args.live_firestore or args.live_openai or args.live_gemini):
        print("--live-firestore, --live-openai 또는 --live-gemini를 명시하세요. 기본 실행은 DB·AI에 연결하지 않습니다.")
        return 2
    if args.live_firestore:
        result, report_name = run_firestore(), "chat-firestore-live.json"
    elif args.live_openai:
        if args.run_id is None:
            result, report_name = run_openai(), "chat-openai-live.json"
        else:
            result, report_name = run_openai(args.run_id), separate_report.name
            result["run_id"] = args.run_id
            result["authorization"] = "explicit_user_approval_for_one_codyssey_key_request"
    else:
        result, report_name = run_gemini(), "chat-gemini-live.json"
    report = LOCAL / report_name
    report.parent.mkdir(exist_ok=True)
    with report.open("x" if args.run_id is not None else "w", encoding="utf-8") as output:
        output.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["ok"] else 2 if result.get("status") in {"waiting_for_openai_key", "waiting_for_gemini_key"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
