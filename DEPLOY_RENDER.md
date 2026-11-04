# 15단계 Render 배포 설정

상태: **15단계 완료 (2026-10-29 21:54 KST).** 사용자가 토큰 공백을 수정하고 재배포한 뒤 실제 인증 200·무인증/오인증 401, 원본 128건·요약 조회, 코디세이 GPT 1회 생성·자동 저장·목록·상세 복원을 확인했습니다. 원본과 기존 질문 3건은 보존했고 검증 질문 1건만 추가됐습니다. 아래 미완료·공백 수정 안내는 이전 상태 기록입니다. 추가 설정 입력은 필요하지 않습니다. 16단계 이후 최신 결과는 [제출 체크리스트](docs/submission/CHECKLIST.md)를 참고하세요.

- 백엔드: https://gajimaiso-ai-assistant.onrender.com
- Swagger: https://gajimaiso-ai-assistant.onrender.com/docs
- 서비스: `srv-dbhdk7afngtc73bck570`, Singapore, Free
- 이전 대시보드 확인 배포: 소스 `075ba79`, `dep-dbhjpum1egvs73foiuf0`, 2026-10-29 21:33:58 KST 기동 완료. 이후 토큰 수정·재배포·Live는 사용자가 확인했으며 이번에는 남은 실제 API 검증만 수행했습니다. 새 배포 ID를 대시보드에서 다시 조회하지 않았습니다.
- 최초 공개 검사: health/docs/openapi 200, data/summary 503 database_unavailable, 보호 API 403 access_not_configured. 보호 해제 없이 설정 대기 중입니다.
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
| `ALLOWED_ORIGINS` | `http://localhost:5500,http://127.0.0.1:5500,https://gajimaiso-ai-assistant.vercel.app` (16단계 기록 기준) |
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
- 프론트 코드·config.js·브라우저 URL에 토큰을 하드코딩하지 않습니다. 16단계에서 password 입력란과 연결 UI를 추가했습니다. 토큰은 현재 탭 메모리에만 유지하고 새로고침 시 다시 입력합니다.
- **새 백엔드 프로세스는 로컬에서도 같은 인증을 요구합니다.** 기존 8002 프로세스는 재시작하지 않았으므로 종전 동작을 유지합니다. 새 보안 버전에 연결한 화면의 보호 기능은 인증 연동 전까지 401/403으로 차단됩니다. 기존 검증 CLI의 HTTP 요청에도 인증 연결이 필요하며, 과거 통과 기록을 새 버전 실행 결과로 간주하지 않습니다.

## 배포 후 검증 절차 — 기존 완료 기록 참고

1. 실제 HTTPS 주소의 `/health` 200, `/docs` 화면, `/openapi.json` 확인.
2. 무인증·잘못된 인증 차단과 인증된 대화 목록 조회 확인. 원본 자료로 수정·삭제 테스트하지 않습니다.
3. 자료 128건, 기간 2016-01~2026-08, 원본·기존 질문 무변경 확인.
4. 환경변수 인식 확인 후 필요한 경우에만 승인된 최대 1회 GPT 검증. 저장 검사 때문에 추가 호출하지 않습니다.
5. 서버·Swagger·접근 보호 검증이 끝나야 15단계 완료로 변경합니다.

[Render Free](https://render.com/docs/free)는 미사용 시 서버가 중지될 수 있어 첫 요청이 지연됩니다. 다음 프론트 연동에서 서버 연결 중 안내가 필요하며, GPT 자동 반복 전송으로 지연을 처리하지 않습니다.


## 이전 사용자 입력 대기 기록

Render의 기존 서비스 **Environment → Edit**에서 아래 3개 값만 직접 입력합니다. 항목 이름은 이미 준비했습니다.

1. `FIREBASE_SERVICE_ACCOUNT_JSON`: 기존 서비스 계정 JSON 파일 전체 내용.
2. `OPENAI_API_KEY`: 로컬 `backend/.env`의 기존 코디세이 키 값(변수명·등호·값을 감싼 따옴표 제외).
3. `APP_ACCESS_TOKEN`: 이번 배포 인증용으로 로컬 `backend/.env` 맨 아래에 준비한 값. 기존 Firebase/OpenAI 설정의 원래 바이트를 변경하지 않고 추가했습니다. 실제 AI 키 신규 발급이 아닙니다.

값을 입력한 뒤 **Choose an option → Save, rebuild, and deploy**를 선택합니다. 이 메뉴 항목은 선택 즉시 저장·재배포하므로 입력을 모두 마친 후 누릅니다. 키는 채팅·문서·GitHub로 전달하지 않습니다.

공개 환경변수 9개는 저장했습니다. 2026-10-29 사용자 설정 완료 안내 후 새 읽기 화면에서 저장된 비밀값 3개를 검사했으나 모두 비어 있었습니다(값은 출력하지 않음). `/health`, `/docs`, `/openapi.json`은 200, `/api/data` 및 `/api/data/summary`는 503 `database_unavailable`, 로컬 접근 토큰을 사용한 `/api/conversations`는 403 `access_not_configured`였습니다. 이는 요청 토큰 불일치(401)가 아니라 서버 접근 토큰이 미설정·부적합한 경우이며, Render 화면에서는 빈 값으로 확인했습니다.

이번 재검사의 실제 AI 호출·DB 쓰기는 0회입니다. 기존 로컬 서버의 읽기 요청으로 원본 128건과 기존 대화 목록 3건이 배포 전 응답 해시와 같은 것도 확인했습니다. 현행 원격 서버에 대한 인증된 요청·자료 128건 조회·선택적 GPT 1회 검증은 설정 입력 후에 수행합니다. 편집 화면에 실제 값을 입력한 뒤 저장·재배포해야 하며 항목 이름만 존재하는 상태는 설정 완료가 아닙니다.

## 최신 확인 결과와 남은 항목 — 2026-10-29 21:43 KST

- 위 빈 값 기록은 이전 배포 당시 상태입니다. 현재 3개 비밀값은 모두 저장돼 있습니다. 값 자체는 출력·문서화하지 않았습니다.
- Firebase 서비스 계정 JSON 형식과 실제 `/api/data`, `/api/data/summary` HTTP 200을 확인했습니다. 자료 128건·2016-01~2026-08·기존 응답 해시 일치로 원본 보존을 확인했습니다.
- `APP_ACCESS_TOKEN`은 앞뒤 공백/줄바꿈이 있고 내부 공백은 없습니다. 공백 제거 후 ASCII 32자 이상 조건을 충족합니다. 현재 서버는 이를 부적합한 설정으로 처리하며 무인증·로컬 토큰 인증 요청 모두 403 `access_not_configured`입니다.
- `OPENAI_API_KEY`는 값이 저장돼 있고 공백/변수명 접두사가 없습니다. 접근 인증 사전 검사에서 중단했으므로 실제 AI 인증·생성 성공으로 해석하지 않습니다. 이번 GPT 요청·DB 쓰기는 0회입니다.
- health/docs/openapi 200, 실제 Swagger 보호 경로 표시, CORS 허용/거부 동작을 확인했습니다. 원격 대화 목록·기존 질문 3건 보존·GPT 답변 저장/복원 검증은 남아 있습니다.
- **사용자 처리:** 기존 서비스 Environment → Edit에서 `APP_ACCESS_TOKEN` 값 앞뒤의 공백·줄바꿈만 제거하고 **Save, rebuild, and deploy**를 실행합니다. 다른 두 비밀값은 다시 입력할 필요가 없습니다. 실제 토큰은 채팅에 보내지 않습니다.
- 확인 근거: `.local/verification-15/render-resume-environment-state.json`, `render-resume-20261029T124024584167Z-9a0888d9-report.json`, `render-resume-20261029T124243495373Z-84f07743-diagnostics.json`. 기존 로컬 서버·배포 설정·비밀값을 이번에 변경하지 않았습니다.
