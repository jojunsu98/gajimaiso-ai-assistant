"""One bounded Chat Completions request with safe errors and completed output only."""

from dataclasses import dataclass

from app.config import OpenAISettings, validate_openai_settings
from app.services.data import DataServiceError


MAX_REPLY_CHARACTERS = 4_000


@dataclass(frozen=True)
class AIResult:
    reply: str
    model: str
    usage: dict[str, int] | None


def _error(status: int, code: str, message: str) -> DataServiceError:
    return DataServiceError(status, code, message)


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _usage(response) -> dict[str, int] | None:
    actual = _field(response, "usage")
    input_tokens = _field(actual, "prompt_tokens")
    output_tokens = _field(actual, "completion_tokens")
    if all(type(value) is int and value >= 0 for value in (input_tokens, output_tokens)):
        return {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return None


def _translate_sdk_error(error) -> DataServiceError:
    """Inspect SDK types and fixed codes, never expose exception text or body."""
    import openai

    code = _field(error, "code")
    error_type = _field(error, "type")
    code = code if isinstance(code, str) else None
    error_type = error_type if isinstance(error_type, str) else None
    if isinstance(error, openai.APITimeoutError):
        return _error(504, "openai_timeout", "AI 응답 시간이 초과되었습니다. 자동 재호출하지 않았습니다.")
    if isinstance(error, openai.AuthenticationError):
        return _error(503, "openai_authentication_failed", "OpenAI 인증 설정을 확인하세요.")
    if isinstance(error, openai.PermissionDeniedError):
        return _error(503, "openai_access_denied", "OpenAI 프로젝트와 모델 접근 권한을 확인하세요.")
    if isinstance(error, openai.RateLimitError):
        quota_codes = {"insufficient_quota", "billing_hard_limit_reached", "billing_not_active"}
        if code in quota_codes or error_type in quota_codes:
            return _error(503, "openai_quota_unavailable", "OpenAI 사용 한도 또는 잔액 설정을 확인하세요.")
        return _error(429, "openai_rate_limited", "OpenAI 호출 빈도 제한에 도달했습니다. 자동 재호출하지 않았습니다.")
    if isinstance(error, openai.NotFoundError):
        return _error(503, "openai_model_unavailable", "설정한 OpenAI 모델을 사용할 수 없습니다.")
    if isinstance(error, openai.BadRequestError):
        if _field(error, "param") == "model" or code in {
            "model_not_found", "model_not_available", "unsupported_model", "invalid_model",
        }:
            return _error(503, "openai_model_unavailable", "설정한 OpenAI 모델을 사용할 수 없습니다.")
        return _error(503, "openai_configuration_error", "OpenAI 모델 또는 요청 설정을 확인하세요.")
    if isinstance(error, openai.APIConnectionError):
        return _error(502, "openai_connection_failed", "OpenAI 서버와 연결할 수 없습니다.")
    return _error(502, "openai_request_failed", "AI 응답 생성에 실패했습니다. 자동 재호출하지 않았습니다.")


class OpenAIService:
    """Synchronous SDK boundary, invoked from the API's synchronous route."""

    def __init__(self, settings: OpenAISettings, client=None):
        self.settings = settings
        self._client = client

    def validate_configuration(self) -> None:
        # Settings validation also rejects unreviewed model changes before any
        # SDK operation; no fallback or succession of models is attempted.
        validate_openai_settings(self.settings)

    def generate(self, instructions: str, messages: list[dict[str, str]]) -> AIResult:
        self.validate_configuration()
        client = self._client
        owns_client = client is None
        try:
            if owns_client:
                from openai import OpenAI

                client = OpenAI(
                    api_key=self.settings.api_key,
                    base_url=self.settings.base_url,
                    max_retries=0,
                    timeout=self.settings.timeout_seconds,
                )
            response = client.chat.completions.create(
                model=self.settings.model,
                messages=[{"role": "system", "content": instructions}, *messages],
                max_completion_tokens=self.settings.max_output_tokens,
            )
        except Exception as error:
            raise _translate_sdk_error(error) from None
        finally:
            if owns_client and client is not None:
                try:
                    client.close()
                except Exception:
                    # A transport cleanup error must not replace the request
                    # outcome, reveal exception text, or trigger another call.
                    pass

        if _field(response, "error") is not None:
            raise _error(502, "openai_response_failed", "AI 응답에 오류가 있어 대화에 저장하지 않았습니다.")
        choices = _field(response, "choices")
        if not isinstance(choices, (list, tuple)) or not choices:
            raise _error(502, "openai_response_invalid", "AI 응답의 필수 정보를 확인할 수 없어 저장하지 않았습니다.")
        choice = choices[0]
        message = _field(choice, "message")
        finish_reason = _field(choice, "finish_reason")
        if finish_reason == "content_filter" or _field(message, "refusal"):
            raise _error(502, "openai_response_refused", "AI가 분석 답변을 제공하지 않아 대화에 저장하지 않았습니다.")
        if finish_reason != "stop":
            raise _error(502, "openai_response_incomplete", "AI 응답이 정상 완료되지 않아 대화에 저장하지 않았습니다.")
        if (_field(message, "role") != "assistant"
                or _field(message, "tool_calls") or _field(message, "function_call")):
            raise _error(502, "openai_response_invalid", "AI 응답의 필수 정보를 확인할 수 없어 저장하지 않았습니다.")
        text = _field(message, "content")
        if not isinstance(text, str) or not text.strip():
            raise _error(502, "openai_response_empty", "AI 답변이 비어 있어 대화에 저장하지 않았습니다.")
        reply = text.strip()
        if len(reply) > MAX_REPLY_CHARACTERS:
            raise _error(502, "openai_response_too_long", "AI 답변이 저장 길이 제한을 초과하여 저장하지 않았습니다.")
        model = _field(response, "model")
        if not isinstance(model, str) or not model.strip() or len(model.strip()) > 200:
            raise _error(502, "openai_response_invalid", "AI 응답의 필수 정보를 확인할 수 없어 저장하지 않았습니다.")
        return AIResult(reply=reply, model=model.strip(), usage=_usage(response))
