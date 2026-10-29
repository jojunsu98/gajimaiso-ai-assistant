"""Synchronous SDK and Firestore calls execute in a FastAPI worker thread."""
from typing import Annotated
from fastapi import APIRouter, Depends

from app.config import load_ai_provider, load_gemini_settings, load_openai_settings
from app.routers.conversations import get_conversation_service
from app.routers.data import get_data_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService
from app.security import limit_chat


def get_chat_service(conversations=Depends(get_conversation_service), data=Depends(get_data_service)):
    provider = load_ai_provider()
    if provider == "gemini":
        from app.services.gemini_client import GeminiService
        ai_service = GeminiService(load_gemini_settings())
    else:
        from app.services.openai_client import OpenAIService
        ai_service = OpenAIService(load_openai_settings())
    return ChatService(conversations, data, ai_service)


router = APIRouter(prefix="/api/chat", tags=["데이터 기반 채팅"], dependencies=[Depends(limit_chat)])


@router.post("", response_model=ChatResponse, summary="요약 기반 질문과 대화 자동 저장",
             description="현재 저장 자료 요약과 최근 최대 5문답만 AI에 보냅니다. 정상 답변과 저장을 확인한 뒤 saved=true를 반환합니다.")
def chat(payload: ChatRequest, service: Annotated[ChatService, Depends(get_chat_service)]):
    return service.chat(payload)
