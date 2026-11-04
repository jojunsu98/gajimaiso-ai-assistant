"""Clients send one question and an optional server-issued conversation ID."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.conversations import Usage, validate_conversation_id
from app.schemas.summary import MonthPeriod


class ChatRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", json_schema_extra={
        "examples": [{"message": "최근 저장된 데이터의 추세와 해석 한계를 알려줘.", "conversation_id": None}]
    })
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
    # Documentation example only; this is not a recorded GPT response.
    model_config = ConfigDict(strict=True, extra="forbid", json_schema_extra={
        "examples": [{
            "conversation_id": "00000000-0000-4000-8000-000000000001",
            "reply": "문서용 가상 예시: 2044-01 자료 1건은 -12명이며 24개월 비교 자료가 부족합니다.",
            "saved": True,
            "data_period": {"start": "2044-01", "end": "2044-01"},
            "model": "gpt-5.4-mini",
            "usage": {"input_tokens": 100, "output_tokens": 40},
        }]
    })
    conversation_id: str
    reply: str = Field(min_length=1, max_length=4000)
    saved: Literal[True] = True
    data_period: MonthPeriod
    model: str
    usage: Usage | None
