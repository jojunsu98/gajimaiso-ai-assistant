"""Clients send one question and an optional server-issued conversation ID."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.conversations import Usage, validate_conversation_id
from app.schemas.summary import MonthPeriod


class ChatRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    message: str = Field(description="앞뒤 공백 제거 후 1~2,000자의 질문")
    conversation_id: str | None = Field(default=None, description="새 대화는 null, 이어가기는 기존 UUID4 ID")

    @field_validator("message")
    @classmethod
    def clean_question(cls, value):
        value = value.strip()
        if not 1 <= len(value) <= 2000:
            raise ValueError("질문은 공백 제거 후 1~2,000자여야 합니다.")
        return value

    @field_validator("conversation_id")
    @classmethod
    def valid_id(cls, value):
        return validate_conversation_id(value) if value is not None else None


class ChatResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    conversation_id: str
    reply: str = Field(min_length=1, max_length=4000)
    saved: Literal[True] = True
    data_period: MonthPeriod
    model: str
    usage: Usage | None
