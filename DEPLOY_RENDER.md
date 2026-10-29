# 15단계 Render 배포 설정

상태: 로컬 보안 구현·검증 완료. 실제 Render 배포 및 공개 URL 검증은 아직 완료하지 않았습니다.
2026-10-29 사용자가 코디세이 키의 외부 배포 사용이 허용됨을 확인했습니다.
해당 확인은 사용자 제공 정보이며 별도의 공개 이용약관을 확인한 것으로 기록하지 않습니다.

## 실행 설정

루트 `render.yaml`을 사용하거나 Render Web Service에 아래 설정을 적용합니다.
기존 같은 서비스가 있으면 재사용하며, Free 이외 요금제로 자동 변경하지 않습니다.

| 항목 | 값 |
| --- | --- |
| 저장소 | `jojunsu98/gajimaiso-ai-assistant` (비공개) |
| Language / Root Directory | Python / `backend` |
| Python | `PYTHON_VERSION=3.12.10` |
| Build | `pip install -r requirements.txt` |
| Start | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log` |
| Health Check | `/health` |
| Plan / 자동 배포 | Free / Off |

단일 worker와 `WEB_CONCURRENCY=1`을 유지합니다. `--no-access-log`는 요청 URL에 실수로 넣은 비밀값이 액세스 로그에 남지 않게 합니다. 토큰은 URL에 넣지 않습니다.
실행 설정은 [FastAPI 배포 안내](https://render.com/docs/deploy-fastapi), [Python 버전 지정](https://render.com/docs/python-version), [Blueprint 명세](https://render.com/docs/blueprint-spec)를 확인했습니다.

## Render 환경변수

Render의 해당 서비스 **Environment → Add Environment Variable**에서 비밀값은 사용자가 직접 입력합니다. 채팅·GitHub·빌드 명령에 넣지 않습니다.

| 변수 | 용도 / 설정 |
| --- | --- |
| `FIREBASE_PROJECT_ID` | 기존 Firebase 프로젝트 ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 기존 서비스 계정 JSON 전체. 앱이 명시적으로 파싱하고 프로젝트 일치 검증 |
| `OPENAI_API_KEY` | 기존 코디세이 가상 키 |
| `OPENAI_BASE_URL` | `https://copa.codyssey.kr/v1` |
| `OPENAI_MODEL` | `gpt-5.4-mini` |
| `AI_PROVIDER` | `openai` |
| `OPENAI_MAX_OUTPUT_TOKENS` | `800` |
| `OPENAI_TIMEOUT_SECONDS` | `45` |
| `ALLOWED_ORIGINS` | 현재 `http://localhost:5500,http://127.0.0.1:5500`; 16단계에서 정확한 Vercel origin 추가 |
| `APP_ACCESS_TOKEN` | API 접근 전용 무작위 비밀값, 공백 없는 ASCII 32자 이상. GPT 키와 별개 |
| `PYTHON_VERSION` / `WEB_CONCURRENCY` | `3.12.10` / `1` |

Windows 키 경로는 Render에서 사용할 수 없습니다. JSON 환경변수를 사용하는 경우 `GOOGLE_APPLICATION_CREDENTIALS`는 Render에 설정하지 않습니다. 대안으로 Render Secret File에 기존 키를 사용자가 등록하고 Render가 표시하는 실제 절대 경로를 `GOOGLE_APPLICATION_CREDENTIALS`에 지정할 수 있습니다. 두 방식 중 JSON이 우선이며 잘못된 JSON을 다른 자격증명으로 우회하지 않습니다.

## API 접근 범위와 16단계 인터페이스

- 공개: `GET /health`, `/docs`, `/openapi.json`, `/api/data`, `/api/data/summary`. 데이터 목록의 memo도 공개 응답이므로 개인정보·비밀값을 입력하지 않습니다.
- 인증 필수: `POST/PUT/DELETE /api/data...`, `POST /api/chat`, 모든 `/api/conversations...` 요청.
- 요청 헤더: `Authorization: Bearer <APP_ACCESS_TOKEN의 실제 값>`. 이 설명의 꺾쇠 문구를 설정값으로 쓰지 않습니다.
- Swagger의 **Authorize**에는 Bearer 접두사 없이 접근 토큰 값만 입력합니다. 다른 API 키를 입력하지 않습니다.
- 서버 접근 토큰 누락·부적합: `403 access_not_configured`. 인증 누락·불일치: `401 access_denied`. 인증 실패는 DB·AI 서비스 초기화 이전에 반환합니다.
- 채팅: 인증 후 동시 1건, 60초당 최대 5건. 초과 `429 chat_rate_limited`와 `Retry-After: 60`. 실패한 요청도 승인된 시도 횟수에 포함되며 자동 재시도하지 않습니다.
- 요청 제한은 단일 프로세스 메모리 기준으로 재시작하면 초기화됩니다. 영구 사용량/결제 상한이 아닙니다. 다중 worker·다중 instance 배포 전에는 공유 제한 저장소가 필요합니다.
- CORS는 명시한 origin만 허용하며 `*` 또는 잘못된 origin 설정은 전체 차단합니다. Authorization 헤더 preflight를 허용합니다. CORS는 인증의 대체 수단이 아닙니다.
- 프론트 코드·config.js·브라우저 URL에 토큰을 하드코딩하지 않습니다. 16단계에서는 사용자 입력 등 별도 인증 전달 방식을 연결해야 합니다. 현재 프론트에는 인증 전달 UI를 추가하지 않았습니다.
- **새 백엔드 프로세스는 로컬에서도 같은 인증을 요구합니다.** 기존 8002 프로세스는 재시작하지 않았으므로 종전 동작을 유지합니다. 새 보안 버전에 연결한 화면의 보호 기능은 인증 연동 전까지 401/403으로 차단됩니다. 기존 검증 CLI의 HTTP 요청에도 인증 연결이 필요하며, 과거 통과 기록을 새 버전 실행 결과로 간주하지 않습니다.

## 배포 후 남은 검증

1. 실제 HTTPS 주소의 `/health` 200, `/docs` 화면, `/openapi.json` 확인.
2. 무인증·잘못된 인증 차단과 인증된 대화 목록 조회 확인. 원본 자료로 수정·삭제 테스트하지 않습니다.
3. 자료 128건, 기간 2016-01~2026-08, 원본·기존 질문 무변경 확인.
4. 환경변수 인식 확인 후 필요한 경우에만 승인된 최대 1회 GPT 검증. 저장 검사 때문에 추가 호출하지 않습니다.
5. 서버·Swagger·접근 보호 검증이 끝나야 15단계 완료로 변경합니다.

[Render Free](https://render.com/docs/free)는 미사용 시 서버가 중지될 수 있어 첫 요청이 지연됩니다. 다음 프론트 연동에서 서버 연결 중 안내가 필요하며, GPT 자동 반복 전송으로 지연을 처리하지 않습니다.
