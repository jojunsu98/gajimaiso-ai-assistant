"""Fail-closed bearer access and bounded, single-process chat admission."""
import hmac
import os
from collections import deque
from threading import Lock
from time import monotonic
from typing import Annotated

from dotenv import dotenv_values
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import ENV_FILE

bearer = HTTPBearer(auto_error=False, scheme_name="AppAccessToken")


def load_access_token() -> str:
    # Do not log this value. Process environment takes precedence, including empty.
    try:
        values = dotenv_values(ENV_FILE, interpolate=False, encoding="utf-8-sig")
        value = os.environ.get("APP_ACCESS_TOKEN", values.get("APP_ACCESS_TOKEN", "")) or ""
        return value if len(value) >= 32 and value.isascii() and not any(c.isspace() for c in value) else ""
    except (OSError, UnicodeError, ValueError, TypeError):
        return ""


def require_access(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    expected = load_access_token()
    if not expected:
        raise HTTPException(403, detail={"code": "access_not_configured", "message": "서버 접근 인증 설정이 필요합니다."})
    supplied = credentials.credentials if credentials is not None else ""
    if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(401, detail={"code": "access_denied", "message": "유효한 접근 인증이 필요합니다."},
                            headers={"WWW-Authenticate": "Bearer"})


class ChatAdmission:
    """One in-flight chat; at most 5 attempts/60s per application process.

    Failed admitted attempts also consume the limit. Restart clears the window;
    this is not a durable billing quota and must run with one worker/instance.
    """
    def __init__(self, clock=monotonic):
        self.clock = clock
        self.lock = Lock()
        self.attempts = deque()
        self.active = False

    def enter(self):
        with self.lock:
            now = self.clock()
            while self.attempts and self.attempts[0] <= now - 60:
                self.attempts.popleft()
            if self.active or len(self.attempts) >= 5:
                raise HTTPException(429, detail={"code": "chat_rate_limited", "message": "질문 처리 중이거나 요청 한도를 초과했습니다. 잠시 뒤 직접 다시 시도하세요."},
                                    headers={"Retry-After": "60"})
            self.attempts.append(now)
            self.active = True

    def leave(self):
        with self.lock:
            self.active = False


def limit_chat(request: Request, _: Annotated[None, Depends(require_access)]):
    admission = request.app.state.chat_admission
    admission.enter()
    try:
        yield
    finally:
        admission.leave()
