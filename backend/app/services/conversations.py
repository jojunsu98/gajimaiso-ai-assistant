"""Bounded, create-only/new and conditional-update/existing conversation storage."""

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
import json
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from app.schemas.conversations import (
    ConversationListItem, ConversationRecord, ManualConversationCreate, Message,
    Usage, validate_conversation_id,
)
from app.schemas.summary import SummaryResponse
from app.services.data import DataServiceError


RPC_TIMEOUT_SECONDS = 10
MAX_PAYLOAD_BYTES = 256 * 1024


def _error(status, code, message):
    return DataServiceError(status, code, message)


def _integrity():
    return _error(500, "conversation_integrity_error", "저장된 대화 형식에 오류가 있습니다.")


def _changed():
    return _error(409, "conversation_conflict", "다른 요청이 대화를 변경하거나 삭제했습니다. 현재 기록을 확인하세요.")


def _missing():
    return _error(404, "conversation_not_found", "해당 대화가 없습니다.")


def _safe_operation(method):
    @wraps(method)
    def guarded(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except DataServiceError:
            raise
        except Exception as error:
            from google.api_core.exceptions import GoogleAPICallError, RetryError
            from google.auth.exceptions import GoogleAuthError
            from grpc import RpcError
            from requests.exceptions import RequestException
            from app.config import FirebaseError

            if isinstance(error, (GoogleAPICallError, RetryError, GoogleAuthError,
                                  RpcError, RequestException, FirebaseError,
                                  TimeoutError, ConnectionError)):
                raise _error(503, "database_unavailable", "대화 데이터베이스에 연결할 수 없습니다.") from None
            raise _error(500, "conversation_internal_error", "대화 처리 중 오류가 발생했습니다.") from None
    return guarded


def _json_default(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError("unsupported payload type")


def ensure_payload_size(payload) -> None:
    """Bound the actual UTF-8 JSON payload, never expose submitted contents."""
    try:
        size = len(json.dumps(payload, default=_json_default, ensure_ascii=False,
                              allow_nan=False, separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError, UnicodeError):
        raise _error(422, "invalid_conversation_payload", "대화 내용을 저장할 수 있는 형식으로 입력하세요.") from None
    if size > MAX_PAYLOAD_BYTES:
        raise _error(422, "conversation_payload_too_large", "대화 저장 크기 한도에 도달했습니다. 새 대화를 시작하세요.")


@dataclass(frozen=True)
class ConversationSnapshot:
    record: ConversationRecord
    update_time: object


def ensure_chat_capacity(snapshot: ConversationSnapshot | None, newuser: str,
                         summary=None, model=None) -> None:
    """Reserve one full answer before a paid request; never discard old messages."""
    messages = list(snapshot.record.messages) if snapshot is not None else []
    if len(messages) + 2 > 40:
        raise _error(422, "conversation_message_limit", "최대 20번의 문답에 도달했습니다. 새 대화를 시작하세요.")
    try:
        user = Message(role="user", content=newuser)
    except ValidationError:
        raise _error(422, "invalid_chat_message", "질문은 공백을 제외하고 1~2,000자로 입력하세요.") from None
    now = datetime.now(timezone.utc)
    provisional = snapshot.record.model_dump(exclude_none=True) if snapshot else {
        "id": str(uuid4()), "title": user.content[:80].strip(), "created_at": now,
    }
    provisional.update({
        "updated_at": now, "source": "chat", "message_count": len(messages) + 2,
        "messages": [message.model_dump() for message in messages] + [user.model_dump(),
            {"role": "assistant", "content": "\x00" * 4000}],
        "last_usage": {"input_tokens": 2**63 - 1, "output_tokens": 2**63 - 1},
        "last_model": "x" * 200,
    })
    if summary is not None:
        provisional["last_summary"] = summary
    ensure_payload_size(provisional)


def _decode(snapshot) -> ConversationRecord:
    payload = snapshot.to_dict()
    if not isinstance(payload, dict) or "id" in payload:
        raise _integrity()
    try:
        record = ConversationRecord.model_validate({**payload, "id": snapshot.id}, strict=True)
        # Trimming is for external inputs only; never silently repair stored text.
        for stored, decoded in zip(payload["messages"], record.messages):
            if stored["content"] != decoded.content:
                raise _integrity()
        ensure_payload_size(payload)
    except (ValidationError, TypeError, ValueError, KeyError, DataServiceError):
        raise _integrity() from None
    return record


class ConversationService:
    """Collection selection is server-only and supports isolated integration tests."""

    def __init__(self, client, collection_name="conversations"):
        self.client = client
        self.collection_name = collection_name

    def _collection(self):
        return self.client.collection(self.collection_name)

    @staticmethod
    def _valid_id(document_id):
        try:
            return validate_conversation_id(document_id)
        except (ValueError, TypeError):
            raise _error(422, "invalid_conversation_id", "유효한 UUID4 대화 ID가 필요합니다.") from None

    def _read(self, document_id):
        self._valid_id(document_id)
        reference = self._collection().document(document_id)
        snapshot = reference.get(retry=None, timeout=RPC_TIMEOUT_SECONDS)
        if not snapshot.exists:
            raise _missing()
        record = _decode(snapshot)
        if snapshot.update_time is None or record.id != document_id:
            raise _integrity()
        return reference, ConversationSnapshot(record, snapshot.update_time)

    @staticmethod
    def _values(record):
        values = record.model_dump(exclude={"id"})
        # Preserve required nulls inside SummaryResponse (for example an
        # insufficient-data trend); omit only absent top-level AI metadata.
        for field in ("last_summary", "last_model", "last_usage"):
            if values[field] is None:
                values.pop(field)
        ensure_payload_size(values)
        return values

    def _confirmed(self, reference, expected):
        snapshot = reference.get(retry=None, timeout=RPC_TIMEOUT_SECONDS)
        if not snapshot.exists:
            raise _error(503, "conversation_save_unconfirmed", "대화 저장 결과를 확인하지 못했습니다. 다시 생성하기 전에 기록을 확인하세요.")
        saved = _decode(snapshot)
        if saved.model_dump() != expected.model_dump():
            raise _changed()
        return saved

    def _create(self, record):
        from google.api_core.exceptions import AlreadyExists
        reference = self._collection().document(record.id)
        try:
            reference.create(self._values(record), retry=None, timeout=RPC_TIMEOUT_SECONDS)
        except AlreadyExists:
            raise _changed() from None
        return self._confirmed(reference, record)

    @_safe_operation
    def create_manual(self, payload: ManualConversationCreate) -> ConversationRecord:
        now = datetime.now(timezone.utc)
        record = ConversationRecord(
            id=str(uuid4()), title=payload.title or payload.messages[0].content[:80].strip(),
            created_at=now, updated_at=now, messages=payload.messages,
            message_count=len(payload.messages), source="manual",
        )
        return self._create(record)

    @_safe_operation
    def list_conversations(self) -> list[ConversationListItem]:
        snapshots = self._collection().get(retry=None, timeout=RPC_TIMEOUT_SECONDS)
        records = [_decode(snapshot) for snapshot in snapshots]
        if len({record.id for record in records}) != len(records):
            raise _integrity()
        records.sort(key=lambda record: (record.updated_at, record.id), reverse=True)
        fields = set(ConversationListItem.model_fields)
        return [ConversationListItem.model_validate(record.model_dump(include=fields)) for record in records]

    @_safe_operation
    def get_conversation(self, document_id) -> ConversationRecord:
        return self._read(document_id)[1].record

    @_safe_operation
    def read_for_chat(self, document_id) -> ConversationSnapshot:
        return self._read(document_id)[1]

    @_safe_operation
    def create_chat(self, messages, title=None, last_summary=None,
                    last_model=None, last_usage=None) -> ConversationRecord:
        now = datetime.now(timezone.utc)
        parsed = [Message.model_validate(message) if not isinstance(message, Message) else message for message in messages]
        record = ConversationRecord(
            id=str(uuid4()), title=title.strip() if title else parsed[0].content[:80].strip(),
            created_at=now, updated_at=now, messages=parsed, message_count=len(parsed),
            source="chat", last_summary=last_summary, last_model=last_model,
            last_usage=last_usage,
        )
        return self._create(record)

    @_safe_operation
    def append_chat(self, snapshot: ConversationSnapshot, user_message,
                    assistant_message, last_summary, last_model, last_usage) -> ConversationRecord:
        from google.api_core.exceptions import FailedPrecondition, NotFound
        existing = snapshot.record
        self._valid_id(existing.id)
        if snapshot.update_time is None:
            raise _integrity()
        if len(existing.messages) + 2 > 40:
            raise _error(422, "conversation_message_limit", "최대 20번의 문답에 도달했습니다. 새 대화를 시작하세요.")
        user = user_message if isinstance(user_message, Message) else Message(role="user", content=user_message)
        assistant = assistant_message if isinstance(assistant_message, Message) else Message(role="assistant", content=assistant_message)
        values = existing.model_dump()
        values.update({"updated_at": datetime.now(timezone.utc), "source": "chat",
                       "messages": [*existing.messages, user, assistant],
                       "message_count": len(existing.messages) + 2,
                       "last_summary": last_summary, "last_model": last_model,
                       "last_usage": last_usage})
        record = ConversationRecord.model_validate(values)
        reference = self._collection().document(existing.id)
        option = self.client.write_option(last_update_time=snapshot.update_time)
        # Include null usage when absent so a previous call's usage is not retained.
        values = self._values(record)
        if record.last_usage is None:
            values["last_usage"] = None
        try:
            reference.update(values, option=option, retry=None, timeout=RPC_TIMEOUT_SECONDS)
        except (FailedPrecondition, NotFound):
            raise _changed() from None
        return self._confirmed(reference, record)

    @_safe_operation
    def delete_conversation(self, document_id) -> None:
        from google.api_core.exceptions import FailedPrecondition, NotFound
        reference, snapshot = self._read(document_id)
        option = self.client.write_option(last_update_time=snapshot.update_time)
        try:
            reference.delete(option=option, retry=None, timeout=RPC_TIMEOUT_SECONDS)
        except (FailedPrecondition, NotFound):
            raise _changed() from None
        confirmation = reference.get(retry=None, timeout=RPC_TIMEOUT_SECONDS)
        if confirmation.exists:
            raise _changed()
