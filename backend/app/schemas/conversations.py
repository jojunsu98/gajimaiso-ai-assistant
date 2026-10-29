"""Strict public conversation inputs and validated server-owned metadata."""

from datetime import datetime, timedelta
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.summary import SummaryResponse


ID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"


def validate_conversation_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(ID_PATTERN, value):
        raise ValueError("유효한 UUID4 대화 ID가 필요합니다.")
    parsed = UUID(value)
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("유효한 UUID4 대화 ID가 필요합니다.")
    return value


class ConversationModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class Message(ConversationModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content", mode="before")
    @classmethod
    def trim_content(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def role_limit(self):
        if self.role == "user" and len(self.content) > 2000:
            raise ValueError("사용자 메시지는 최대 2,000자입니다.")
        return self


def _complete_pairs(messages):
    if len(messages) % 2:
        raise ValueError("사용자로 시작하는 완성된 문답 쌍이 필요합니다.")
    for index, message in enumerate(messages):
        if message.role != ("user" if index % 2 == 0 else "assistant"):
            raise ValueError("사용자와 답변 메시지를 순서대로 입력하세요.")
    return messages


class ManualConversationCreate(ConversationModel):
    title: str | None = Field(default=None, max_length=80)
    messages: list[Message] = Field(min_length=2, max_length=40)

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("messages")
    @classmethod
    def complete_pairs(cls, value):
        return _complete_pairs(value)


class Usage(ConversationModel):
    input_tokens: int = Field(ge=0, le=2**63 - 1)
    output_tokens: int = Field(ge=0, le=2**63 - 1)


class ConversationListItem(ConversationModel):
    id: str = Field(pattern=ID_PATTERN)
    title: str = Field(min_length=1, max_length=80)
    created_at: datetime
    updated_at: datetime
    message_count: int = Field(ge=2, le=40)

    @field_validator("id")
    @classmethod
    def valid_id(cls, value):
        return validate_conversation_id(value)

    @field_validator("created_at", "updated_at")
    @classmethod
    def utc_time(cls, value):
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("대화 시각은 UTC여야 합니다.")
        return value

    @model_validator(mode="after")
    def valid_metadata(self):
        if self.updated_at < self.created_at or self.message_count % 2:
            raise ValueError("대화 메타데이터가 올바르지 않습니다.")
        if not self.title.strip() or self.title != self.title.strip():
            raise ValueError("대화 제목이 올바르지 않습니다.")
        return self


class ConversationRecord(ConversationListItem):
    messages: list[Message] = Field(min_length=2, max_length=40)
    source: Literal["chat", "manual"]
    last_summary: SummaryResponse | None = None
    last_model: str | None = Field(default=None, min_length=1, max_length=200)
    last_usage: Usage | None = None

    @model_validator(mode="after")
    def valid_record(self):
        _complete_pairs(self.messages)
        if self.message_count != len(self.messages):
            raise ValueError("저장 메시지 수가 일치하지 않습니다.")
        if self.source == "manual":
            if any(value is not None for value in (self.last_summary, self.last_model, self.last_usage)):
                raise ValueError("수동 저장에는 AI 실행 메타데이터를 지정할 수 없습니다.")
        elif self.last_summary is None or self.last_model is None:
            raise ValueError("AI 대화에는 실제 사용한 요약과 모델 정보가 필요합니다.")
        return self


class ConversationList(ConversationModel):
    items: list[ConversationListItem]
    count: int = Field(ge=0)
