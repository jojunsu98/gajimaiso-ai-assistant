"""Loopback-only browser QA using the existing app/services and isolated writes.

No network is used by the default invocation. Explicit live mode permits exactly
one browser question; isolated mode uses real Firestore plus a named fake AI.
Stop with Ctrl+C or a line containing ``stop`` on stdin to finish preservation
checks and remove only documents owned by this run. No control HTTP API exists.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from threading import RLock, Thread
import time

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from scripts.check_chat import (
    CheckError, FakeAI, LOCAL, OneAttemptAI, RecordingClient, _preserved,
    cleanup_owned, require, safe_error, snapshot_collection,
)
from app.services.data import DataService, DataServiceError
from app.services.conversations import ConversationService

UI_QUESTION = "저장된 기간에서 월별 순이동 최댓값과 최솟값, 각각의 월을 알려주고 이 수치의 의미를 설명해줘."


def blocked():
    raise DataServiceError(409, "qa_original_write_blocked", "이번 화면 검증에서는 원본 변경이 차단되어 있습니다.")


class ReadOnlyData(DataService):
    def create_data(self, *args, **kwargs):
        blocked()

    def update_data(self, *args, **kwargs):
        blocked()

    def delete_data(self, *args, **kwargs):
        blocked()


class DemoConversations(ConversationService):
    """New auto-saved demo only; all existing conversation writes blocked."""
    def create_manual(self, *args, **kwargs):
        blocked()

    def append_chat(self, *args, **kwargs):
        blocked()

    def delete_conversation(self, *args, **kwargs):
        blocked()

    def read_for_chat(self, *args, **kwargs):
        blocked()


class DelayedFakeAI(FakeAI):
    def generate(self, instructions, messages):
        time.sleep(1)
        return super().generate(instructions, messages)


class ObservedConversations:
    def __init__(self, service, state):
        self.service, self.state = service, state

    def __getattr__(self, name):
        return getattr(self.service, name)

    def list_conversations(self):
        records = self.service.list_conversations()
        with self.state.lock:
            ids = [record.id for record in records]
            self.state.report["last_list_count"] = len(ids)
            if self.state.report.get("demo_conversation_id") in ids:
                self.state.report["demo_listed"] = True
            self.state.persist()
        return records

    def get_conversation(self, document_id):
        record = self.service.get_conversation(document_id)
        with self.state.lock:
            seen = self.state.report.setdefault("detail_ids_read", [])
            if document_id not in seen:
                seen.append(document_id)
            if document_id == self.state.report.get("demo_conversation_id"):
                expected = [{"role": "user", "content": UI_QUESTION},
                            {"role": "assistant", "content": self.state.report["reply"]}]
                self.state.report["demo_reload_matches"] = (
                    [message.model_dump() for message in record.messages] == expected
                    and record.last_model == self.state.report["model"]
                    and record.last_summary.model_dump(mode="json") == self.state.report["transmitted_summary"]
                )
            self.state.persist()
        return record


class ObservedChat:
    def __init__(self, service, state):
        self.service, self.state = service, state

    def chat(self, payload):
        if self.state.live:
            if payload.conversation_id is not None:
                blocked()
            if payload.message != UI_QUESTION:
                raise DataServiceError(422, "qa_question_mismatch", "승인된 화면 검증 질문과 일치하지 않습니다. AI를 호출하지 않았습니다.")
            if self.state.ai.calls or self.state.guard.exists():
                raise DataServiceError(409, "qa_generation_already_attempted", "이번 실행의 AI 요청은 이미 시도되었습니다. 자동 재요청하지 않습니다.")
        try:
            response = self.service.chat(payload)
            with self.state.lock:
                if self.state.live:
                    self.state.report.update({"saved": response.saved,
                        "demo_conversation_id": response.conversation_id,
                        "question": payload.message, "reply": response.reply,
                        "model": response.model,
                        "usage": response.usage.model_dump() if response.usage else None})
                else:
                    self.state.report["fake_chat_saved"] = response.saved
            return response
        except DataServiceError as error:
            self.state.report.update({"chat_error_code": error.code,
                                      "chat_http_status": error.status_code,
                                      "saved": False})
            raise
        finally:
            with self.state.lock:
                self.state.update_ai_evidence()
                self.state.persist()


class QAState:
    def __init__(self, client, mode, run_id, report_path, guard, ai):
        self.client, self.mode, self.run_id = client, mode, run_id
        self.live = mode == "live-openai"
        self.report_path, self.guard, self.ai = Path(report_path), Path(guard), ai
        self.lock = RLock()
        self.before_data = self.before_conversations = None
        self.recordings = []
        self.report = {"mode": mode, "run_id": run_id, "ok": False,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "generation_requests": 0, "saved": False,
            "demo_listed": False, "demo_reload_matches": False,
            "finalized": False, "api_requests": []}

    def persist(self):
        # Only fixed errors and this run's approved question/answer/summary.
        self.report_path.write_text(json.dumps(self.report, ensure_ascii=False,
            indent=2, allow_nan=False) + "\n", encoding="utf-8")

    def update_ai_evidence(self):
        if self.live:
            self.report["generation_requests"] = self.ai.calls
            self.report.update(self.ai.provider_error)
            if self.ai.instructions is not None:
                self.report["transmitted_summary"] = json.loads(
                    self.ai.instructions.split("현재 데이터 요약 JSON:\n", 1)[1])
            if self.ai.answer is not None:
                self.report.update({"reply": self.ai.answer.reply,
                    "model": self.ai.answer.model, "usage": self.ai.answer.usage})
        else:
            self.report["fake_ai_calls"] = len(self.ai.calls)

    def initialize(self):
        self.before_data = snapshot_collection(self.client, "data")
        self.before_conversations = snapshot_collection(self.client, "conversations")
        require(len(self.before_data) == 128, "original_128_count_mismatch")
        self.report["original_data_count"] = len(self.before_data)
        self.report["existing_conversations_count"] = len(self.before_conversations)
        if self.live:
            data_service = ReadOnlyData(self.client)
            conv_name = "conversations"
        else:
            data_name = "_frontend_data_checks_" + self.run_id.replace("-", "_")
            conv_name = "_frontend_conversation_checks_" + self.run_id.replace("-", "_")
            for name in (data_name, conv_name):
                require(not snapshot_collection(self.client, name), "isolated_collection_not_empty")
            recording_data = RecordingClient(self.client, data_name)
            self.recordings.append(recording_data)
            data_service = DataService(recording_data, collection_name=data_name)
            self.report["isolated_data_collection"] = data_name
            self.report["isolated_conversation_collection"] = conv_name
        recording_conversations = RecordingClient(self.client, conv_name)
        self.recordings.append(recording_conversations)
        cls = DemoConversations if self.live else ConversationService
        conversations = ObservedConversations(cls(recording_conversations, collection_name=conv_name), self)
        from app.services.chat import ChatService
        chat = ObservedChat(ChatService(conversations, data_service, self.ai,
            title_prefix="[화면 연결 검증] " if self.live else "[모의 화면 검증] "), self)
        self.persist()
        return build_app(data_service, conversations, chat, self)

    def finalize(self):
        with self.lock:
            if self.report["finalized"]:
                return
            self.update_ai_evidence()
            # A successful create can survive a lost acknowledgment; keep every
            # owned production demo instead of deleting an uncertain paid answer.
            retained = list(self.recordings[-1].owned) if self.live and self.recordings else []
            outcomes = [cleanup_owned(recording,
                keep_ids=retained if recording.collection_name == "conversations" else ())
                for recording in self.recordings]
            self.report["cleanup"] = {"ok": all(item["ok"] for item in outcomes), "collections": outcomes}
            self.report["retained_demo_ids"] = retained
            try:
                if self.before_data is not None:
                    self.report["data_preserved"] = _preserved(self.before_data, snapshot_collection(self.client, "data"))
                if self.before_conversations is not None:
                    self.report["existing_conversations_preserved"] = _preserved(self.before_conversations,
                        snapshot_collection(self.client, "conversations"), retained)
            except Exception as error:
                self.report["preservation_error"] = safe_error(error)
            preservation = all(self.report.get(key, {}).get("ok") for key in
                ("cleanup", "data_preserved", "existing_conversations_preserved"))
            live_checks = (self.report.get("saved") and self.report.get("demo_listed")
                           and self.report.get("demo_reload_matches") and self.ai.calls == 1)
            self.report["ok"] = bool(preservation and (live_checks if self.live else True))
            self.report["finalized"] = True
            self.report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
            self.persist()


def build_app(data, conversations, chat, state=None):
    from app.main import create_app
    from app.routers.data import get_data_service
    from app.routers.conversations import get_conversation_service
    from app.routers.chat import get_chat_service
    app = create_app()
    app.dependency_overrides[get_data_service] = lambda: data
    app.dependency_overrides[get_conversation_service] = lambda: conversations
    app.dependency_overrides[get_chat_service] = lambda: chat
    if state is not None:
        @app.middleware("http")
        async def record_status(request, call_next):
            response = await call_next(request)
            with state.lock:
                state.report["api_requests"].append({"method": request.method,
                    "path": request.url.path, "status": response.status_code})
                state.persist()
            return response
    return app


def build_mock_app(case):
    """Fixed, CLI-selected failures only; no client/credentials/network access."""
    from fastapi.responses import PlainTextResponse
    class Errors:
        def __getattr__(self, name):
            def error(*args, **kwargs):
                if case == "empty" and name in {"list_data", "list_conversations"}:
                    return []
                status = int(case) if case in {"422", "409", "503"} else 503
                codes = {422: "validation_error", 409: "duplicate_month", 503: "database_unavailable"}
                raise DataServiceError(status, codes[status], "명시적인 모의 화면 오류 검증입니다.")
            return error
    app = build_app(Errors(), Errors(), Errors())
    if case == "non-json":
        @app.exception_handler(DataServiceError)
        async def plain_failure(request, exc):
            return PlainTextResponse("Mock upstream failure", status_code=503)
    return app


def run_paths(run_id):
    require(isinstance(run_id, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", run_id), "invalid_run_id")
    return LOCAL / f"frontend-{run_id}-report.json", LOCAL / f"frontend-{run_id}-attempt.json"


def stop_from_stdin(server):
    for line in sys.stdin:
        if line.strip() == "stop":
            server.should_exit = True
            return


def main(argv=None):
    parser = argparse.ArgumentParser(description="127.0.0.1 전용 화면 검증; 기존 서버와 원본 데이터는 변경하지 않습니다.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--live-openai", action="store_true")
    modes.add_argument("--isolated-firestore", action="store_true")
    modes.add_argument("--mock-error", choices=["422", "409", "503", "non-json", "empty"])
    parser.add_argument("--run-id")
    parser.add_argument("--port", type=int, default=8012)
    args = parser.parse_args(argv)
    if not (args.live_openai or args.isolated_firestore or args.mock_error):
        print("검증 모드를 명시하세요. 기본 실행은 DB·AI·서버에 연결하지 않습니다.")
        return 2
    if not 1024 <= args.port <= 65535:
        parser.error("--port는 1024~65535 범위로 지정하세요.")
    state = None
    try:
        if args.mock_error:
            app = build_mock_app(args.mock_error)
        else:
            report_path, guard = run_paths(args.run_id)
            require(not guard.exists(), "generation_attempt_already_recorded")
            report_path.parent.mkdir(exist_ok=True)
            # Exclusive reservation prevents reusing a prior run/report.
            with report_path.open("x", encoding="utf-8") as output:
                output.write('{"initializing": true}\n')
            if args.live_openai:
                from app.config import load_ai_provider, load_openai_settings
                from app.services.openai_client import OpenAIService
                require(load_ai_provider() == "openai", "provider_is_not_openai")
                settings = load_openai_settings()
                service = OpenAIService(settings)
                service.validate_configuration()
                ai = OneAttemptAI(service, settings.model, guard=guard)
            else:
                ai = DelayedFakeAI()
            from app.services.firestore import get_firestore_client
            state = QAState(get_firestore_client(), "live-openai" if args.live_openai else "isolated-firestore",
                args.run_id, report_path, guard, ai)
            app = state.initialize()
        import uvicorn
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, access_log=False, log_level="warning"))
        Thread(target=stop_from_stdin, args=(server,), daemon=True).start()
        print(json.dumps({"ready_for_browser": True, "base_url": f"http://127.0.0.1:{args.port}",
            "mode": state.mode if state else "mock-" + args.mock_error}, ensure_ascii=False), flush=True)
        server.run()
    except KeyboardInterrupt:
        # Ctrl+C is the documented orderly stop, not a verification failure.
        pass
    except Exception as error:
        code = safe_error(error)
        print(json.dumps({"ok": False, "error": code}), flush=True)
        if state is not None:
            state.report["server_error"] = code
        return 1
    finally:
        if state is not None:
            state.finalize()
            print(json.dumps({"finalized": True, "ok": state.report["ok"],
                "generation_requests": state.report["generation_requests"],
                "report": str(state.report_path)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
