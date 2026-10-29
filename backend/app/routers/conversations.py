"""Conversation storage never requires OpenAI configuration or a generation."""
from typing import Annotated
from fastapi import APIRouter, Depends, Path, Response

from app.config import FirebaseError
from app.schemas.conversations import (
    ID_PATTERN, ConversationRecord, ConversationListItem, ManualConversationCreate,
)
from app.services.conversations import ConversationService
from app.services.data import DataServiceError
from app.security import require_access
from pydantic import BaseModel, Field


def get_conversation_service():
    try:
        from app.services.firestore import get_firestore_client
        return ConversationService(get_firestore_client())
    except FirebaseError:
        raise DataServiceError(503, "database_unavailable", "대화 데이터베이스 연결 또는 설정을 확인해야 합니다.") from None


class ConversationListResponse(BaseModel):
    items: list[ConversationListItem]
    count: int = Field(ge=0)


router = APIRouter(prefix="/api/conversations", tags=["대화 기록"], dependencies=[Depends(require_access)])
Service = Annotated[ConversationService, Depends(get_conversation_service)]
ConversationId = Annotated[str, Path(pattern=ID_PATTERN, description="서버가 발급한 UUID4 대화 ID")]


@router.post("", status_code=201, response_model=ConversationRecord,
             summary="완성된 문답 수동 저장", description="user/assistant 문답 쌍을 새 대화로 저장합니다. GPT를 호출하지 않습니다.")
def create_conversation(payload: ManualConversationCreate, service: Service):
    return service.create_manual(payload)


@router.get("", response_model=ConversationListResponse, summary="대화 목록 조회",
            description="updated_at 최신순 메타데이터만 반환합니다. 메시지와 요약은 목록에서 제외합니다.")
def list_conversations(service: Service):
    items = service.list_conversations()
    return ConversationListResponse(items=items, count=len(items))


@router.get("/{id}", response_model=ConversationRecord,
            summary="특정 대화 불러오기", description="전체 메시지와 서버 메타데이터를 반환합니다.")
def get_conversation(id: ConversationId, service: Service):
    return service.get_conversation(id)


@router.delete("/{id}", status_code=204, response_class=Response, summary="대화 한 건 삭제")
def delete_conversation(id: ConversationId, service: Service):
    service.delete_conversation(id)
    return Response(status_code=204)
