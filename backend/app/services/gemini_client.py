"""One bounded Gemini Developer API call; no fallback, tools or retries."""

from app.config import GeminiSettings, validate_gemini_settings
from app.services.data import DataServiceError
from app.services.openai_client import AIResult


MAX_REPLY_CHARACTERS = 4_000
OFFICIAL_BASE_URL = "https://generativelanguage.googleapis.com"


def _field(value, name, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _error(status, code, message):
    return DataServiceError(status, code, message)


def _usage(response):
    """Output tokens = reported candidate tokens + reported thought tokens, if any.

    An absent thought count does not imply measured zero thoughts; in that case
    output_tokens contains only the reported candidate count. No total or model
    estimate is used to reconstruct missing usage.
    """
    usage = _field(response, "usage_metadata")
    prompt = _field(usage, "prompt_token_count")
    candidates = _field(usage, "candidates_token_count")
    thoughts = _field(usage, "thoughts_token_count")
    if not all(type(value) is int and 0 <= value <= 2**63 - 1 for value in (prompt, candidates)):
        return None
    if thoughts is not None:
        if type(thoughts) is not int or not 0 <= thoughts <= 2**63 - 1:
            return None
        candidates += thoughts
    if candidates > 2**63 - 1:
        return None
    return {"input_tokens": prompt, "output_tokens": candidates}


def _translate_sdk_error(error):
    """Only SDK types and numeric status codes are inspected, never error text."""
    from google.genai import errors
    import httpx
    import httpx2

    if isinstance(error, (TimeoutError, httpx.TimeoutException, httpx2.TimeoutException)):
        return _error(504, "gemini_timeout", "Gemini 응답 시간이 초과되었습니다. 자동 재호출하지 않았습니다.")
    if isinstance(error, errors.APIError):
        if error.code in (408, 504):
            return _error(504, "gemini_timeout", "Gemini 응답 시간이 초과되었습니다. 자동 재호출하지 않았습니다.")
        if error.code == 401:
            return _error(503, "gemini_authentication_failed", "Gemini 인증 설정을 확인하세요.")
        if error.code == 403:
            return _error(503, "gemini_access_denied", "Gemini 키와 프로젝트의 접근 권한을 확인하세요.")
        if error.code == 429:
            return _error(429, "gemini_rate_or_quota_limited", "Gemini 호출 빈도 또는 할당량 제한을 확인하세요. 자동 재호출하지 않았습니다.")
        if error.code == 404:
            return _error(503, "gemini_model_unavailable", "설정한 Gemini 모델을 사용할 수 없습니다.")
        if error.code == 400:
            return _error(503, "gemini_configuration_error", "Gemini 키 또는 요청 설정을 확인하세요.")
    if isinstance(error, (httpx.TransportError, httpx2.TransportError)):
        return _error(502, "gemini_connection_failed", "Gemini 서버와 연결할 수 없습니다.")
    return _error(502, "gemini_request_failed", "Gemini 응답 생성에 실패했습니다. 자동 재호출하지 않았습니다.")


def _reply(response):
    feedback = _field(response, "prompt_feedback")
    block_reason = _field(feedback, "block_reason")
    if block_reason not in (None, "", "BLOCKED_REASON_UNSPECIFIED"):
        raise _error(502, "gemini_response_blocked", "Gemini가 분석 답변을 제공하지 않아 저장하지 않았습니다.")
    candidates = _field(response, "candidates")
    if not isinstance(candidates, (list, tuple)) or len(candidates) != 1:
        raise _error(502, "gemini_response_invalid", "Gemini 응답의 필수 정보를 확인할 수 없어 저장하지 않았습니다.")
    candidate = candidates[0]
    if _field(candidate, "finish_reason") != "STOP":
        raise _error(502, "gemini_response_incomplete", "Gemini 응답이 정상 완료되지 않아 저장하지 않았습니다.")
    if any(_field(rating, "blocked") is True for rating in (_field(candidate, "safety_ratings", []) or [])):
        raise _error(502, "gemini_response_blocked", "Gemini가 분석 답변을 제공하지 않아 저장하지 않았습니다.")
    parts = _field(_field(candidate, "content"), "parts", []) or []
    if not isinstance(parts, (list, tuple)):
        raise _error(502, "gemini_response_invalid", "Gemini 응답의 필수 정보를 확인할 수 없어 저장하지 않았습니다.")
    text = []
    for part in parts:
        if not isinstance(part, dict) and not hasattr(part, "__dict__"):
            raise _error(502, "gemini_response_nontext", "Gemini가 텍스트 외 응답을 반환하여 저장하지 않았습니다.")
        fields = part if isinstance(part, dict) else (
            part.model_dump(exclude_none=True) if hasattr(part, "model_dump") else vars(part)
        )
        # Do not use response.text: it may silently ignore tool/media parts and
        # emit a warning that includes unwanted response details.
        if any(value is not None and name not in {"text", "thought", "thought_signature"}
               for name, value in fields.items()):
            raise _error(502, "gemini_response_nontext", "Gemini가 텍스트 외 응답을 반환하여 저장하지 않았습니다.")
        content = _field(part, "text")
        if not isinstance(content, str):
            raise _error(502, "gemini_response_nontext", "Gemini가 텍스트 외 응답을 반환하여 저장하지 않았습니다.")
        if _field(part, "thought") is not True:
            text.append(content)
    reply = "".join(text).strip()
    if not reply:
        raise _error(502, "gemini_response_empty", "Gemini 답변이 비어 있어 저장하지 않았습니다.")
    if len(reply) > MAX_REPLY_CHARACTERS:
        raise _error(502, "gemini_response_too_long", "Gemini 답변이 저장 길이 제한을 초과하여 저장하지 않았습니다.")
    return reply


class GeminiService:
    def __init__(self, settings: GeminiSettings, client=None):
        self.settings = settings
        self._client = client

    def validate_configuration(self):
        validate_gemini_settings(self.settings)

    def generate(self, instructions, messages):
        self.validate_configuration()
        from google import genai
        from google.genai import types

        contents = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role not in {"user", "assistant"} or not isinstance(content, str) or not content.strip():
                raise _error(422, "gemini_invalid_input", "Gemini에 전달할 대화 형식이 올바르지 않습니다.")
            contents.append(types.Content(role="model" if role == "assistant" else "user",
                                          parts=[types.Part.from_text(text=content)]))
        if not contents:
            raise _error(422, "gemini_invalid_input", "Gemini에 전달할 대화가 없습니다.")
        client = self._client
        owns_client = client is None
        try:
            if owns_client:
                client = genai.Client(
                    api_key=self.settings.api_key, vertexai=False,
                    http_options=types.HttpOptions(
                        base_url=OFFICIAL_BASE_URL,
                        timeout=max(1, int(self.settings.timeout_seconds * 1000)),
                        retry_options=types.HttpRetryOptions(attempts=1),
                    ),
                )
            response = client.models.generate_content(
                model=self.settings.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=instructions,
                    max_output_tokens=self.settings.max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_level="MINIMAL", include_thoughts=False),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )
        except Exception as error:
            raise _translate_sdk_error(error) from None
        finally:
            if owns_client and client is not None:
                try:
                    client.close()
                except Exception:
                    pass  # Cleanup must not replace the outcome or trigger a call.
        reply = _reply(response)
        model = _field(response, "model_version")
        if not isinstance(model, str) or not 1 <= len(model.strip()) <= 200:
            raise _error(502, "gemini_response_invalid", "Gemini 응답의 실제 모델 정보를 확인할 수 없어 저장하지 않았습니다.")
        return AIResult(reply=reply, model=model.strip(), usage=_usage(response))
