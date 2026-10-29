import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import load_allowed_origins
from app.routers import chat, conversations, data, health
from app.services.data import DataServiceError
from app.security import ChatAdmission

logger = logging.getLogger("gajimaiso.api")


def create_app() -> FastAPI:
    application = FastAPI(
        title="가지마이소창원 AI 비서 API",
        description="창원시 월별 순이동 자료·요약·AI 질문과 대화 기록. 날짜의 01은 월 대표일입니다. 자료 조회·요약은 공개이며 변경·질문·대화 기록은 Bearer 인증이 필요합니다. /health는 서버 생존만 확인합니다.",
        version="0.3.0",
        docs_url="/docs",
    )
    application.state.chat_admission = ChatAdmission()

    @application.exception_handler(DataServiceError)
    async def data_error(request: Request, exc: DataServiceError):
        if exc.status_code >= 500:
            logger.warning("request_failed code=%s request_id=%s", exc.code, request.state.request_id)
        content = {"detail": {"code": exc.code, "message": exc.message}}
        if getattr(exc, "saved", None) is False:
            content["saved"] = False
        return JSONResponse(status_code=exc.status_code, content=content)

    @application.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError):
        # Do not echo raw input, exception context, NaN/Infinity, or user secrets.
        return JSONResponse(status_code=422, content={"detail": {
            "code": "validation_error", "message": "입력의 필수 항목·형식·길이·역할·ID를 확인하세요. API 문서의 허용 범위를 따라야 합니다."
        }})

    @application.middleware("http")
    async def safe_unexpected_errors(request: Request, call_next):
        request.state.request_id = uuid4().hex
        try:
            response = await call_next(request)
        except Exception:
            # Handling here also avoids raw exception tracebacks in server logs.
            logger.error("request_failed code=internal_error request_id=%s", request.state.request_id)
            response = JSONResponse(status_code=500, content={"detail": {
                "code": "internal_error", "message": "요청 처리 중 서버 오류가 발생했습니다."
            }})
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    application.add_middleware(
        CORSMiddleware,
        allow_origins=load_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    application.include_router(health.router)
    application.include_router(data.router)
    application.include_router(conversations.router)
    application.include_router(chat.router)
    return application


app = create_app()
