"""Read only the explicitly configured Firebase credentials; never use implicit ADC."""

import json
import os
import math
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_ai_provider() -> str:
    """Choose one configured provider explicitly; never fail over on errors."""
    from app.services.data import DataServiceError
    try:
        values = dotenv_values(ENV_FILE, interpolate=False, encoding="utf-8-sig")
        provider = os.environ.get("AI_PROVIDER", values.get("AI_PROVIDER", "openai"))
        if provider not in {"openai", "gemini"}:
            raise ValueError()
        return provider
    except (OSError, UnicodeError, TypeError, ValueError):
        raise DataServiceError(503, "ai_provider_invalid", "AI_PROVIDER는 openai 또는 gemini로 명시해야 합니다.") from None


@dataclass(frozen=True)
class GeminiSettings:
    api_key: str = field(default="", repr=False)
    model: str = "gemini-3.5-flash-lite"
    max_output_tokens: int = 800
    timeout_seconds: float = 45.0


def load_gemini_settings() -> GeminiSettings:
    """Read only the project Gemini setting; no implicit Google credential search."""
    from app.services.data import DataServiceError
    try:
        values = dotenv_values(ENV_FILE, interpolate=False, encoding="utf-8-sig")
        def value(name, default):
            return os.environ[name] if name in os.environ else values.get(name, default)
        return GeminiSettings(
            api_key=value("GEMINI_API_KEY", "") or "",
            model=value("GEMINI_MODEL", "gemini-3.5-flash-lite") or "",
            max_output_tokens=int(value("GEMINI_MAX_OUTPUT_TOKENS", "800")),
            timeout_seconds=float(value("GEMINI_TIMEOUT_SECONDS", "45")),
        )
    except (OSError, UnicodeError, TypeError, ValueError, OverflowError):
        raise DataServiceError(503, "gemini_configuration_invalid", "Gemini 서버 설정 형식을 확인해야 합니다.") from None


def validate_gemini_settings(settings: GeminiSettings) -> None:
    from app.services.data import DataServiceError
    if not isinstance(settings.api_key, str) or not settings.api_key.strip():
        raise DataServiceError(503, "gemini_key_missing", "Gemini 키가 설정되지 않았습니다.")
    if settings.model != "gemini-3.5-flash-lite":
        raise DataServiceError(503, "gemini_model_unverified", "설정한 Gemini 모델의 파라미터 호환성 확인이 필요합니다.")
    if (type(settings.max_output_tokens) is not int or not 1 <= settings.max_output_tokens <= 4096
            or type(settings.timeout_seconds) not in (int, float)
            or not math.isfinite(settings.timeout_seconds) or not 0 < settings.timeout_seconds <= 120):
        raise DataServiceError(503, "gemini_configuration_invalid", "출력 토큰 한도(1~4096) 또는 제한 시간(0초 초과~120초)을 확인하세요.")


@dataclass(frozen=True)
class OpenAISettings:
    api_key: str = field(default="", repr=False)
    model: str = "gpt-5.4-mini"
    max_output_tokens: int = 800
    timeout_seconds: float = 45.0
    base_url: str = "https://copa.codyssey.kr/v1"


def load_openai_settings() -> OpenAISettings:
    """Load only configured values; never search other projects or print secrets."""
    from app.services.data import DataServiceError
    try:
        values = dotenv_values(ENV_FILE, interpolate=False, encoding="utf-8-sig")
        def value(name, default):
            return os.environ[name] if name in os.environ else values.get(name, default)
        return OpenAISettings(
            api_key=value("OPENAI_API_KEY", "") or "",
            model=value("OPENAI_MODEL", "gpt-5.4-mini") or "",
            max_output_tokens=int(value("OPENAI_MAX_OUTPUT_TOKENS", "800")),
            timeout_seconds=float(value("OPENAI_TIMEOUT_SECONDS", "45")),
            base_url=value("OPENAI_BASE_URL", "https://copa.codyssey.kr/v1") or "",
        )
    except (OSError, UnicodeError, TypeError, ValueError, OverflowError):
        raise DataServiceError(503, "openai_configuration_invalid", "OpenAI 서버 설정 형식을 확인해야 합니다.") from None


def validate_openai_settings(settings: OpenAISettings) -> None:
    from app.services.data import DataServiceError
    if not isinstance(settings.api_key, str) or not settings.api_key.strip():
        raise DataServiceError(503, "openai_key_missing", "OpenAI 키가 설정되지 않았습니다. 서버에서 키를 설정한 뒤 이용하세요.")
    # Other models require a deliberate compatibility review, never fallback.
    if settings.model != "gpt-5.4-mini":
        raise DataServiceError(503, "openai_model_unverified", "설정한 모델의 코디세이 Chat Completions 호환성 확인이 필요합니다.")
    if settings.base_url != "https://copa.codyssey.kr/v1":
        raise DataServiceError(503, "openai_base_url_invalid", "OPENAI_BASE_URL에 승인된 코디세이 SDK용 주소를 설정하세요.")
    if (type(settings.max_output_tokens) is not int or not 1 <= settings.max_output_tokens <= 4096
            or type(settings.timeout_seconds) not in (int, float)
            or not math.isfinite(settings.timeout_seconds) or not 0 < settings.timeout_seconds <= 120):
        raise DataServiceError(503, "openai_configuration_invalid", "출력 토큰 한도(1~4096) 또는 제한 시간(0초 초과~120초)을 확인하세요.")


def load_allowed_origins() -> list[str]:
    """Read a public CORS setting without changing .env or initializing Firebase."""
    default = "http://localhost:5500,http://127.0.0.1:5500"
    try:
        values = dotenv_values(ENV_FILE, interpolate=False, encoding="utf-8-sig")
    except (OSError, UnicodeError):
        # A failed settings read must not open CORS to additional origins.
        return []
    raw = os.environ.get("ALLOWED_ORIGINS", values.get("ALLOWED_ORIGINS", default)) or ""
    origins = list(dict.fromkeys(origin.strip() for origin in raw.split(",") if origin.strip()))
    # Never allow a wildcard, including a mistaken deployment setting.
    from urllib.parse import urlsplit
    for origin in origins:
        try:
            parsed = urlsplit(origin)
            if ("*" in origin or parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.path or parsed.query or parsed.fragment):
                return []
        except ValueError:
            return []
    return origins

_ERROR_MESSAGES = {
    "missing_project_id": "FIREBASE_PROJECT_ID에 이번 과제용 프로젝트 ID를 설정하세요.",
    "missing_credentials": "GOOGLE_APPLICATION_CREDENTIALS 또는 FIREBASE_SERVICE_ACCOUNT_JSON을 설정하세요.",
    "invalid_json": "선택한 서비스 계정 설정이 올바른 JSON이 아닙니다. 다른 자격증명으로 우회하지 않았습니다.",
    "invalid_credentials": "서비스 계정 JSON의 형식 또는 필수 항목이 올바르지 않습니다.",
    "credentials_file_missing": "지정한 서비스 계정 키 파일이 없습니다.",
    "credentials_file_unreadable": "지정한 서비스 계정 키 파일을 읽을 수 없습니다.",
    "credentials_path_not_absolute": "GOOGLE_APPLICATION_CREDENTIALS에는 키 파일의 절대 경로를 설정하세요.",
    "project_mismatch": "키의 project_id와 FIREBASE_PROJECT_ID가 달라 연결을 중단했습니다.",
    "settings_read_failed": "backend/.env 설정 파일을 읽을 수 없습니다.",
    "emulator_configured": "FIRESTORE_EMULATOR_HOST가 설정되어 클라우드 연결 검사를 중단했습니다. 해당 설정을 제거한 뒤 실행하세요.",
    "initialization_project_mismatch": "이미 초기화된 Firebase 앱의 프로젝트가 설정과 달라 연결을 중단했습니다.",
    "initialization_conflict": "같은 이름의 Firebase 앱이 이미 존재합니다. 다른 자격증명을 재사용하지 않고 중단했습니다. 검사 프로세스를 새로 실행하세요.",
    "initialization_failed": "Firebase 연결 객체 초기화에 실패했습니다. 키 형식과 설치 환경을 확인하세요.",
}


class FirebaseError(RuntimeError):
    """Only fixed, public error text is exposed; no original exception values."""

    def __init__(self, code: str):
        self.code = code if code in _ERROR_MESSAGES else "initialization_failed"
        super().__init__(_ERROR_MESSAGES[self.code])


@dataclass(frozen=True)
class FirebaseSettings:
    project_id: str = ""
    credentials_path: str = field(default="", repr=False)
    credentials_json: str = field(default="", repr=False)
    emulator_host: str | None = field(default=None, repr=False)


def load_firebase_settings() -> FirebaseSettings:
    """Use a fixed backend/.env path; process values (even empty) take priority."""
    try:
        file_values = dotenv_values(ENV_FILE, interpolate=False, encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise FirebaseError("settings_read_failed") from None

    def value(name: str, default: str | None = "") -> str | None:
        if name in os.environ:
            return os.environ[name]
        return file_values.get(name, default)

    return FirebaseSettings(
        project_id=(value("FIREBASE_PROJECT_ID") or "").strip(),
        credentials_path=value("GOOGLE_APPLICATION_CREDENTIALS") or "",
        credentials_json=value("FIREBASE_SERVICE_ACCOUNT_JSON") or "",
        emulator_host=value("FIRESTORE_EMULATOR_HOST", None),
    )


def validate_credentials(settings: FirebaseSettings) -> dict:
    """Offline validation. Read only the supplied file if JSON text is absent."""
    if settings.emulator_host is not None:
        raise FirebaseError("emulator_configured")
    if not settings.project_id:
        raise FirebaseError("missing_project_id")

    if settings.credentials_json:
        credential_text = settings.credentials_json
    else:
        if not settings.credentials_path:
            raise FirebaseError("missing_credentials")
        key_file = Path(settings.credentials_path)
        if not key_file.is_absolute():
            raise FirebaseError("credentials_path_not_absolute")
        try:
            credential_text = key_file.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            raise FirebaseError("credentials_file_missing") from None
        except OSError:
            raise FirebaseError("credentials_file_unreadable") from None
        except UnicodeError:
            raise FirebaseError("invalid_json") from None

    try:
        info = json.loads(credential_text)
    except (ValueError, RecursionError):
        raise FirebaseError("invalid_json") from None
    if not isinstance(info, dict) or info.get("type") != "service_account":
        raise FirebaseError("invalid_credentials")
    if not isinstance(info.get("project_id"), str) or not info["project_id"]:
        raise FirebaseError("invalid_credentials")
    if info["project_id"] != settings.project_id:
        raise FirebaseError("project_mismatch")
    if not all(isinstance(info.get(key), str) and info[key].strip()
               for key in ("private_key", "client_email", "token_uri")):
        raise FirebaseError("invalid_credentials")
    return info
