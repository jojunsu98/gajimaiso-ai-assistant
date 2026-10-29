# 진행 기록

**16단계 진행 중:** Vercel 운영 배포와 Render API·인증·CORS·원본 보존 검증 통과. Chrome 확장프로그램 창 차단 해제와 사용자 토큰 입력 후 실제 PC/모바일·질문 불러오기·콘솔 검증 대기. 17단계는 시작하지 않았습니다.

**15단계 완료 (2026-10-29 21:54 KST):** 수정된 토큰으로 실제 Render API 인증 200, 무인증·오인증 401 차단, Firebase 원본 128건·요약 조회를 확인했습니다. 코디세이 GPT 실제 생성은 정확히 1회 성공했고 자동 저장·목록·상세 복원이 일치합니다. 원본 자료와 기존 질문 3건은 검증 전후 동일하며 검증 질문 1건만 추가돼 현재 질문은 4건입니다. 기존 서버·Swagger·CORS 검증은 재실행하지 않고 이전 근거를 유지했습니다. **16단계는 시작하지 않고 중단합니다.** [배포 안내](DEPLOY_RENDER.md) 및 마지막 최종 검증 기록을 참고하세요.

현재 상태: **10~12단계 완료 — 코디세이 중계 서버를 통한 OpenAI GPT 호출, 실제 답변 내용 검증·자동 저장·목록·상세 복원 성공**.
2026-10-29 `codyssey-chat-20261029-01`에서 Chat Completions 1회 성공. `/responses`는 호출하지 않았습니다.
이전 개인 키의 `openai_quota_unavailable` 실패와 Gemini 성공 기록은 별도 보존합니다. 코디세이 키의 결과와 혼합하지 않습니다.
**13~14단계 완료 — 사용자 수동 확인창3항목 통과 및 UI/UX 통합 검수 완료(2026-10-29).** 이번 UI 통합의 추가 GPT 호출은0회입니다. 과거의 실제 GPT 화면1회 성공은 유지하며 이번에 재호출하지 않았습니다. 최신 결과는 마지막 통합 완료 절을 참고하세요. 아래 미완료·시간초과 기록은 당시 이력입니다.

## 1~4단계 기록

확인일: 2026-10-28 (Asia/Seoul)

## 작업 위치와 사전 확인

- 절대 경로: `C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant`
- 폴더명과 지정 경로 일치 확인: 통과
- 시작 시 숨김 파일을 포함한 기존 항목 수: 0개
- 기존 파일을 덮어쓰거나 삭제한 작업 없음
- 소스·설정·문서는 이 프로젝트 안에만 생성했습니다.

## 단계별 상태

| 단계 | 코드·파일 준비 | 실행 테스트 | 사용자 화면(브라우저) 확인 |
| --- | --- | --- | --- |
| 1. 프로젝트 기본 구조 | 완료. backend/frontend 분리, 앱/라우터 분리, services/schemas 패키지 공간 준비 | 파일·폴더 존재 확인. frontend 내부 항목 0개 | 해당 없음 |
| 2. Python 가상환경 | 완료. 루트 `.venv` 생성, 필요한 패키지 설치 | Python 3.12.10, 가상환경 격리, pip 위치, 의존성 정상 확인 | 해당 없음 |
| 3. FastAPI 기본 서버 | 완료. `/health`, 지정 API 제목, `/docs` | 127.0.0.1:8000에서 실제 서버 실행 및 HTTP 검사 통과 | Chrome에서 `/health` 실행 결과 확인 |
| 4. `/docs` 테스트 화면 | 완료 | `/docs` 및 `/openapi.json` HTTP 200 확인 | 에이전트가 Chrome 실제 화면과 `Try it out` → `Execute`의 200 응답 확인 |

코드 작성, HTTP 실행 테스트, 브라우저 화면 확인을 각각 수행했습니다.
사용자 본인이 직접 화면을 열어본 여부는 확인하지 않았습니다.

## Python 및 설치 결과

- 실제 실행 확인한 기본 Python: `C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe`
- 버전: Python 3.12.10, 64-bit. Python 3.10 이상 조건 충족.
- 실제 사용한 가상환경 Python: `C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant\.venv\Scripts\python.exe`
- `sys.prefix != sys.base_prefix`: 참
- `.venv/pyvenv.cfg`의 `include-system-site-packages = false`: 확인
- pip 25.0.1의 설치 위치가 프로젝트 `.venv/Lib/site-packages/pip`임을 확인
- 가상환경 생성, 패키지 설치, 환경 확인 명령: 모두 종료 코드 0
- 활성화 스크립트 사용 및 PowerShell 실행 정책 변경 없음

| 직접 설치한 패키지 | 설치 버전 |
| --- | --- |
| fastapi | 0.162.0 |
| uvicorn | 0.54.0 |
| python-dotenv | 1.2.4 |

전역 Python 패키지를 설치·업데이트하지 않았습니다. 패키지는 `.venv` Python의 pip로 설치했습니다.
`backend/requirements.txt`의 고정 버전과 설치된 버전이 일치함을 검사했습니다.
`firebase-admin`과 `openai`는 이번에 설치하지 않았으며, 각 연결 단계에서 추가할 예정이라고 requirements에 기록했습니다.

## 실제 실행 검증

테스트 주소: `http://127.0.0.1:8000` — 시작 전 8000번 포트가 비어 있어 기본 포트를 사용했습니다.

| 검사 | 실제 결과 |
| --- | --- |
| `.venv` Python의 `-m pip check` | `No broken requirements found.`, 종료 코드 0 |
| `.venv` Python의 `-m compileall -q backend/app` | 문법 컴파일 통과, 종료 코드 0 |
| `GET /health` | HTTP 200, JSON이 정확히 `{"status":"ok"}`와 일치 |
| `GET /docs` | HTTP 200, Swagger HTML과 지정 제목 확인 |
| `GET /openapi.json` | HTTP 200, `paths`에 `/health`의 GET 포함 |
| OpenAPI 제목 | `가지마이소창원 AI 비서 API`와 일치 |
| OpenAPI 등록 경로 | `/health` 하나만 있음 |
| HTTP 검증 명령 전체 | 모든 assertion 통과, 종료 코드 0 |
| Chrome Swagger UI | 한글 제목과 GET `/health`가 실제 화면에 표시됨 |
| Swagger `Try it out` → `Execute` | 화면에서 응답 코드 200 및 `{"status":"ok"}` 확인 |

`/health`는 서버 자체의 응답 확인만 의미합니다. Firebase나 OpenAI 연결을 검사하지 않습니다.

로컬 확인 근거 (`.local/`은 Git 제외 대상):

- [HTTP 및 브라우저 검증 기록](.local/http-verification.json)
- [Uvicorn 시작 로그](.local/uvicorn.stderr.log)
- [HTTP 접근 로그](.local/uvicorn.stdout.log)
- [Swagger 제목과 health 화면](.local/swagger-ui.jpg)
- [Swagger 200 응답 화면](.local/swagger-health-response.jpg)

## 실행 중 발생한 문제와 최종 서버 상태

최초 터미널 연결(PTY) 방식은 실행 도구의 `CreateProcessW` 접근 거부 오류(os error 5)로
서버 실행 전에 실패했습니다. 시스템 정책을 바꾸지 않고 `Start-Process -WindowStyle Hidden`으로
이 프로젝트의 `.venv` Python을 실행하여 HTTP 및 브라우저 검증을 완료했습니다.

**검증용 서버는 테스트 후 종료했습니다.** 실행 기록과 프로세스 경로·명령행·부모 관계를 대조한 뒤
이번에 시작한 Uvicorn 프로세스만 종료했습니다. 다른 프로세스는 종료하지 않았습니다.

- 검증 당시 실행기 PID: 22960, Uvicorn PID: 23432
- 종료 후 두 프로세스 부재 및 8000번 포트의 리스너 부재 확인: 통과
- 서버 종료 및 결과 기록 명령: 종료 코드 0
- 재실행 위치·명령·주소: [README.md](README.md)의 Windows PowerShell 실행 안내 참조

화면 저장 도구가 JPEG 데이터를 반환하여, 최종 파일 검사에서 확장자 불일치를 발견했습니다.
이미지 내용은 바꾸지 않고 `.png`를 `.jpg`로 수정했으며 문서와 검증 기록의 링크도 일치시켰습니다.

## 제외 규칙과 작업 경계

`.gitignore`는 `.venv`, `.env`와 로컬 변형 파일, Python 캐시, 비밀키 전용 폴더
(`backend/secrets/`, `secrets/`), 구체적인 서비스 계정 키 파일명, `.local/`을 제외합니다.
`.env.example`과 `.env.sample`은 허용하며 일반 JSON·CSV·설정 파일을 일괄 제외하지 않습니다.
이전 단계의 프로젝트 내부 키 보관 안내는 5~6단계에서 변경했습니다.
실제 키는 프로젝트와 OneDrive 밖에 보관하며, 위 제외 폴더 규칙은 방어용으로만 유지합니다.

이번 1~4단계에서 미완료로 남은 필수 검증은 없습니다. 사용자 자신의 재실행과 화면 확인은 별도로 할 수 있습니다.
AI API 호출, Firebase 연결, 데이터 입력, 대화 저장·불러오기, 프론트엔드 구현,
Render/Vercel 배포는 수행하지 않았습니다. Git 초기화·커밋·푸시·기존 이력 변경도 수행하지 않았습니다.

## 구조 참고

앱과 라우터를 나누는 구조는 [FastAPI 공식 문서](https://fastapi.tiangolo.com/tutorial/bigger-applications/)의
`APIRouter` 및 `include_router` 방식에 따랐습니다.

## 5~6단계 — Firestore 연결 준비와 검증

확인일: 2026-10-28 (Asia/Seoul). 기존 구조와 `.venv`를 재사용했습니다.

| 단계 | 코드·설정 준비 | 키 없는 실행 검증 | 실제 클라우드 검증 |
| --- | --- | --- | --- |
| 5. Firestore 연결 준비 | 완료 | 최종 모의 테스트 39개 통과 | 이 상태만으로 실제 연결 성공을 뜻하지 않음 |
| 6. 실제 저장·조회·삭제 연결 검증 | CLI 준비 완료 | 검사·정리·시간초과 분기 모의 검증 통과 | **완료. 사용자 키 설정 후 실제 검사 1회 성공, 종료 코드 0** |

### 변경 사항

- `backend/app/config.py`: 터미널 위치와 무관한 `backend/.env` 로딩, 프로세스 환경변수 우선,
  JSON 문자열 우선, 안전한 원인별 오류, 키의 프로젝트 ID 일치 검증.
- `backend/app/services/firestore.py`: 기본 `(default)` DB 연결을 필요할 때 초기화하고 잠금으로
  중복 초기화를 방지하며 같은 프로세스에서 재사용. 기본 API 시작 시에는 호출하지 않음.
- 동일 이름의 미소유 Firebase 앱이 남아 있으면 다른 자격증명을 임의로 채택하지 않고 중단.
- `backend/scripts/check_firestore.py`: `--live` 옵션에서만 접속하는 명령줄 검사. 공개 HTTP 경로 추가 없음.
- `backend/tests/test_firebase.py`: 표준 `unittest`와 모의 객체를 이용한 오프라인 테스트.
- `backend/.env.example`: 세 변수의 사용법과 우선순위 설명. `backend/.env`는 없음을 확인한 뒤
  배타적 생성 모드로 빈 설정 틀만 생성했으며, 기존 파일이 생겼다면 보존하도록 처리.
- `backend/requirements.txt`: 실제 설치된 `firebase-admin==7.7.0` 추가. `openai`는 미설치·후속 단계로 유지.
- `.gitignore`의 환경파일 제외·예제 허용 규칙은 유지. 키 보관 안내는 프로젝트·OneDrive 밖으로 변경.
- README에 현재 가능한 준비·CLI 실행 방법과 `data`/`conversations`의 향후 목적만 추가.

### 연결 준비 당시 수행한 검증

| 검사 | 결과·근거 |
| --- | --- |
| 기존 Python·가상환경 재사용 | Python 3.12.10, `sys.prefix`가 프로젝트 `.venv`와 일치 |
| 설치 | `.venv`에 firebase-admin 7.7.0 및 필수 의존성 설치, 종료 코드 0 |
| 기존 패키지 보존 | 설치 전 16개 전체 버전을 constraints로 고정하고 설치 후 동일함을 확인 |
| 의존성 충돌 | `pip check`: `No broken requirements found.`, 종료 코드 0 |
| 최종 오프라인 테스트 | `Ran 39 tests ... OK`, 종료 코드 0 |
| Python 문법 | `compileall -q backend/app backend/scripts backend/tests`, 종료 코드 0 |
| 실제 환경의 기본 CLI | `--live` 없이 한 번 실행. `FIREBASE_PROJECT_ID` 누락 안내, 예상 종료 코드 2 |
| `/health` 회귀 검사 | 별도 8001 포트에서 HTTP 200, 정확한 `{"status":"ok"}` 응답 |
| `/docs` 회귀 검사 | 별도 8001 포트에서 HTTP 200 및 기존 문서 제목 확인 |
| `/openapi.json` 회귀 검사 | 별도 8001 포트에서 HTTP 200, 등록 경로는 기존 `/health` 하나 |
| 기본 앱의 Firebase 의존성 | 기본 앱 실행 시 `firebase_admin` 모듈이 로딩되지 않음 확인 |
| 검증용 서버 종료 | 이번 8001 검증용 서버만 종료, 종료 확인 통과 |
| 기존 8000 서버 보존 | 시작·HTTP 검증 종료 시 리스너의 주소·포트·프로세스 ID 동일함을 확인 |

오프라인 테스트는 설정 누락, 없는 파일, 잘못된 JSON, 프로젝트 불일치, 우선순위와 우회 금지,
환경변수 우선·고정 `.env` 경로, 동시 초기화, 비밀값을 숨긴 오류, 실제 접속 옵션 제한,
테스트 문서 소유 확인·삭제, 정리 실패 보고, 시간초과 시 작업 프로세스 종료 순서를 확인합니다.
실제 키 대신 명백한 테스트용 문자열과 모의 객체를 사용했으며, 이는 클라우드 연결 증거가 아닙니다.

최종 검토에서 기존 named app의 자격증명을 임의로 재사용할 가능성을 차단했습니다.
또한 Windows `.venv` 실행기의 부모 프로세스만 종료되는 경우를 고려해, CLI가 생성한 작업
프로세스 트리의 종료를 확인한 뒤에만 후속 정리를 하도록 보완하고 관련 모의 테스트를 추가했습니다.
수정 후 39개 전체 테스트를 다시 실행했습니다. 이 프로세스 종료 분기의 실제 OS 실행은 모의 검증이며,
이번 작업에서 실제 연결 worker를 실행하거나 사용자 서버 프로세스를 종료한 것은 아닙니다.

근거 파일:

- [최종 오프라인 테스트 로그](.local/firebase-offline-tests.log)
- [한 차례 수행한 로컬 설정 검사](.local/firebase-settings-check.log)
- [8001 HTTP 검증 결과](.local/firebase-http-verification.json) — 당시 35개 통과 후 HTTP 검사, 이후 안전성 보완 후 최종 39개 통과
- [기존 패키지 고정 목록](.local/firebase-existing-constraints.txt)
- [8000 리스너 작업 전](.local/firebase-port8000-before.json) / [HTTP 검증 후](.local/firebase-port8000-after.json)

### 연결 준비 당시 상태와 사용자 준비 사항

아래 내용은 키 설정 전의 기록이며, 이후 실제 검증 결과는 마지막 항목에 있습니다.
당시 설정 검사에서 `FIREBASE_PROJECT_ID`가 없어 **설정 대기**로 종료했습니다.
Firebase 콘솔의 프로젝트·DB·키 준비 여부는 확인하지 않았으며 추정하지 않습니다.
실제 Firestore 저장·조회·삭제 검사, 외부 키 파일 탐색, 키 대기·반복 실행은 하지 않았습니다.

사용자가 콘솔에서 과제용 프로젝트, 기본 `(default)` Firestore DB, 서비스 계정 키를 준비한 뒤
`backend/.env`에 실제 프로젝트 ID와 프로젝트·OneDrive 밖 키 파일의 절대 경로를 설정해야 합니다.
로컬 파일 방식에서는 `FIREBASE_SERVICE_ACCOUNT_JSON`을 비워 둡니다.
실제 프로세스 환경변수가 `.env`보다 우선하므로 기존 환경변수 설정도 사용자가 확인해야 합니다.
재실행 명령은 [README의 Firestore 연결 준비와 검사](README.md#firestore-연결-준비와-검사)에 있습니다.

요청별 5초·자동 재시도 없음, worker 35초·비정상 종료 후 정리 worker 20초,
종료 확인까지 포함한 설정상 최대 합계 약 75초로 제한했습니다. 중간 실패 시에도 이번 실행의
테스트 문서만 소유권·갱신 시각을 확인한 뒤 정리하며, 정리 실패를 숨기지 않습니다.
worker 종료를 확인하지 못하면 후속 작업을 시작하지 않고 별도로 보고합니다.

`data`(창원 인구이동 데이터), `conversations`(대화 기록)에는 실제 데이터나 샘플을 입력하지 않았습니다.
CSV 탐색·가져오기, 데이터 CRUD·summary API, OpenAI·대화 저장 API, 프론트엔드 구현,
배포·GitHub 푸시·유료 전환·보안 규칙 변경은 하지 않았습니다.
이번 단계에서 브라우저 화면을 다시 확인하지는 않았으며 사용자의 직접 화면 확인 상태도 미확인입니다.

SDK 사용 근거: [Firebase Admin 초기화 API](https://firebase.google.com/docs/reference/admin/python/firebase_admin),
[Firestore client와 database_id](https://firebase.google.com/docs/reference/admin/python/firebase_admin.firestore),
[문서 create/get/delete 및 retry·timeout API](https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.document.DocumentReference).

## 6단계 실제 연결 검증 완료

확인일: 2026-10-28 (Asia/Seoul).

사용자가 실제 프로젝트 ID와 키 보관 폴더를 제공하여 작업을 재개했습니다.
지정한 폴더 바로 안의 JSON 파일이 한 개임을 확인하고 그 파일만 사용했습니다.
다른 폴더나 하위 폴더의 키를 검색하지 않았습니다.

로컬 사전 확인에서 키가 프로젝트·OneDrive 밖에 있음을 확인했고, 키의 `project_id`가
사용자가 지정한 프로젝트와 일치하며 인증서 형식을 정상적으로 읽을 수 있음을 확인했습니다.
프로세스 환경변수와 우선 JSON 설정의 충돌이 없음을 확인한 뒤 `backend/.env`의 프로젝트 ID와
키 파일 절대 경로를 설정했습니다. JSON 문자열 설정은 비워 두고 다른 설정은 보존했습니다.
실제 키 내용·private_key·인증 토큰·`.env` 원문은 출력하거나 기록하지 않았습니다.

프로젝트 루트에서 실행한 명령:

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\check_firestore.py' --live
```

| 실제 확인 항목 | 결과 |
| --- | --- |
| 실제 연결 검사 횟수 | 1회 |
| 대상 DB | 기본 `(default)` |
| 테스트 컬렉션 | `_connection_checks` |
| 무작위 ID 문서 1개 생성 | 성공 |
| 생성 문서 조회 및 저장 값 일치 | 성공 |
| 이번 실행의 문서만 조건부 삭제 | 성공 |
| 삭제 후 재조회에서 부재 확인 | 성공 |
| CLI 종료 코드 | **0** |
| 정리 실패 또는 잔여 테스트 문서 | 없음. 이번 생성 문서의 삭제 확인 완료 |
| 8000번 서버 | 종료·재시작하지 않음. 작업 전후 리스너의 주소·포트·프로세스 ID 동일 |

근거: [안전한 사전 설정 확인 결과](.local/firebase-live-config-check.json),
[실제 연결 검사 출력](.local/firebase-live-check.log),
[실제 연결 결과 및 8000 서버 유지 기록](.local/firebase-live-result.json),
[8000 작업 전](.local/firebase-live-port8000-before.json) / [작업 후](.local/firebase-live-port8000-after.json).

이번 실제 검사에서 남은 문제는 발견되지 않았습니다. 이전 모의 테스트 39개와 HTTP 검증은
이번에 다시 실행하지 않았으며, 위 실제 연결 성공 결과와 구분합니다.
`data`·`conversations` 데이터 입력, 데이터 CRUD 구현, OpenAI 연결, 프론트엔드 구현,
배포 또는 Git 작업으로 넘어가지 않았습니다.

## 7단계 — 기존 CSV 검증과 Firestore 가져오기 완료

확인일: 2026-10-28 (Asia/Seoul).

### 원본 확인과 보존

먼저 현재 프로젝트의 CSV·TSV가 없음을 확인했습니다. 이후 상위 폴더에서 이름에
`gajimaiso` 또는 `가지마이소`가 포함된 기존 프로젝트만 읽었으며 `.venv`, `.git`,
`node_modules`, `.local`은 탐색에서 제외했습니다. 전체 드라이브·개인 파일·키 파일 재탐색은 하지 않았습니다.

확인한 후보는 기존 프로젝트의 정제 CSV, 원자료 `migration_raw.csv`, 분석 결과
`monthly_metrics.csv`, 달별 평균 `monthly_pattern.csv`입니다. README·정제 코드와 원자료를
대조하여 다음 정제 CSV가 창원시 전체 월별 순이동 시계열임을 확인했습니다.

- 원본: `C:\Users\user\OneDrive\바탕 화면\gajimaiso-changwon-starter\gajimaiso-changwon\data\changwon_migration_monthly_clean.csv`
- 복사본: `backend/data/source/changwon_migration_monthly_clean.csv`
- 크기: 9,921바이트
- 원본·복사본 SHA-256: `e9c97c21f17695520431434b2e7c587babe2caf4ba62c1d83153329c10570475`
- 복사 전·후 및 실제 가져오기 후 원본 해시 동일. 원본 수정·이동·삭제 없음.
- UTF-8 BOM, 쉼표 구분, 실제 13개 열. 전체 열 이름은 [README](README.md#실제-원본과-해석)에 기록.
- 기존 원자료 지역 `48120`·항목 `T25`의 월/순이동 값과 정제 CSV가 128개월 모두 일치.
- 원자료 해시: `8fd4d73b3c5fe2adc3de3e308934065ae46788ebde62054b9b3a7986e696a674`

출처는 기존 README·정제 코드에서 확인한 KOSIS 「시군구별 이동자수」 국내인구이동통계,
표 ID `DT_1B26001_A01` 기록입니다. 기존 README의 메타자료 표시 시각은 2026-10-15 17:42이며,
기록된 URL은 [이 통계표](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1B26001_A01)입니다.
새 데이터 다운로드나 KOSIS 최신성·개정 여부 확인은 하지 않았습니다.

### 검증과 변환

| 검사 | 결과 |
| --- | --- |
| 전체 데이터 행 / 유효 월 | 128행 / 서로 다른 128개월 |
| 기간 | 2016-01~2026-08 전체 사용, 120개로 절단하지 않음 |
| 지역·대상·단위 | `48120`, 창원시 전체, 월별 순이동자수, 명 |
| 중복 월 / 누락 월 / 빈 값 | 각각 0건 |
| 잘못된 날짜 / 비수치 / NaN·무한대 / 소수 부분 | 각각 0건 |
| 순이동 검산 | 모든 행에서 `total_inflow - total_outflow = net_migration` |
| 최소 100개 조건 | 이번 대상 시계열 128개월만으로 충족 |

`month` → 문서 ID `changwon-net-YYYY-MM` 및 `date=YYYY-MM-01`,
`net_migration` → 정수 `value`, 고정 `memo=창원시 월별 순이동자수(명)`으로 변환했습니다.
`region_code`와 `region_name`은 대상 검증에 사용했습니다. 음수와 0은 허용하고 소수는 반올림하지 않습니다.
01은 월 대표일이며 하루치 관측일이 아닙니다. 다른 원본 열은 복사본에 모두 보존했습니다.
순이동은 출생·사망을 포함한 전체 인구 증감이 아니며, 없는 연령·이동 사유 등의 정보는 추론하지 않습니다.

### 코드와 오프라인 테스트

- `backend/scripts/import_migration.py`: 전체 CSV 검증·변환 함수, 기본/`--dry-run`, `--apply`, `--verify` CLI.
- `backend/app/services/migration_import.py`: 전체 충돌 사전 검사, 동일 기록 건너뛰기,
  생성 전용 최대 400건 묶음 저장, 전체 대상 묶음 조회 대조, 부분 실패·불확실 상태 구분.
- `backend/tests/test_migration.py`: 신규 테스트 34개. 날짜/대표일/음수/0/소수/NaN/무한대/지역/
  중복/누락/100개 미만/동일 재실행/충돌/부분 실패/기본 실행 시 DB 미접속 검증.
- 기존 Firebase 테스트 39개와 합쳐 **73개 모두 통과**, 종료 코드 0.
- 가짜 테스트 자료는 프로젝트 `.local` 임시 폴더와 모의 객체 안에서만 사용 후 정리.
  실제 `data`에는 확인된 원본 128개월만 저장.
- 새 패키지 설치·업그레이드 없음. 기존 `.venv`, 환경설정과 연결 서비스를 재사용.

Firestore 요청은 `retry=None`, `timeout=10`으로 지정했습니다. 전체 사전 조회 상한은 10,000건이며
초과하면 쓰기를 중단합니다. 기존 문서를 수정·삭제하지 않고 같은 ID에는 생성 전제조건을 적용합니다.
사전 검사 이후 외부 작성자가 다른 ID로 같은 월을 추가하는 경쟁 상황까지 보장하는 구조는 아닙니다.
SDK 참고: [WriteBatch의 commit·timeout](https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.batch.WriteBatch),
[Client의 batch·get_all](https://docs.cloud.google.com/python/docs/reference/firestore/latest/google.cloud.firestore_v1.client.Client).

### 실제 실행 명령과 결과

실행 위치는 프로젝트 루트입니다. 실제로 다음 순서의 명령을 실행했습니다.

```powershell
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\import_migration.py' --dry-run --report migration-dry-run.json
& '.\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s backend/tests -t backend -v
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\import_migration.py' --apply --report migration-first-apply.json
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\import_migration.py' --verify --report migration-verify.json
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\import_migration.py' --apply --report migration-reapply.json
```

| 실제 검사 | 결과 | 종료 코드 |
| --- | --- | --- |
| dry-run | 128개월 검증·변환 성공, DB 접속·쓰기 없음 | 0 |
| 첫 실제 가져오기 | `data` 신규 생성 128, 동일 건너뜀 0, 충돌 0 | 0 |
| 저장 후 전체 대조 | 대상 128건의 ID 및 date/value/memo 타입·값 일치, 누락·불일치 0 | 0 |
| 동일 CSV 재실행 | 신규 생성 **0**, 동일 건너뜀 **128**, 충돌 0 | 0 |
| 최종 로컬 근거 검사 | 각 보고서의 원본 해시·128개 조건 일치, 원본 불변, 8000 리스너 동일 | 0 |

모든 실제 실행은 기본 `(default)` DB의 `data` 컬렉션을 사용했습니다. 연결용 테스트 문서나
다른 컬렉션의 문서를 128개 집계에 포함하지 않았습니다. 오류·정리 필요·미완료 기록은 없습니다.

확인 근거:

- [원본 복사·해시](.local/migration-source.json), [dry-run](.local/migration-dry-run.json)
- [오프라인 테스트 로그](.local/migration-offline-tests.log)
- [첫 가져오기](.local/migration-first-apply.json), [전체 대조](.local/migration-verify.json)
- [재실행](.local/migration-reapply.json), [최종 확인](.local/migration-final-verification.json)
- [8000 작업 전](.local/migration-port8000-before.json) / [작업 후](.local/migration-port8000-after.json)

**7단계 완료.** 기존 8000번 서버를 종료·재시작하지 않았으며 작업 전후 리스너 주소·포트·PID가 같았습니다.
이번에는 서버·라우터를 변경하지 않았고 HTTP·브라우저 검증을 다시 실행하지 않았습니다.
키·`.env` 내용은 출력하거나 수정하지 않았습니다. CRUD·summary API, OpenAI·대화 저장,
프론트엔드, 배포, GitHub 푸시, 요금·보안 설정 변경은 수행하지 않았습니다.

## 8~9단계 — 데이터 CRUD 및 summary API 완료

확인일: 2026-10-28 (Asia/Seoul). 기존 가상환경·패키지·Firebase 설정·연결을 재사용했습니다.
새 설치·업그레이드 없이 필요한 라우터·서비스·모델·검사만 추가했습니다.

### 구현과 코드 검토

- `POST /api/data` 201, `GET /api/data` 200, `PUT /api/data/{id}` 200,
  `DELETE /api/data/{id}` 204, `GET /api/data/summary` 200 구현.
- `backend/app/routers/data.py`: 일반 `def` 라우터와 교체 가능한 서비스 의존성. DB 호출은 worker thread에서 처리.
- `backend/app/schemas/data.py`: 엄격한 날짜·월 대표일·int64·memo·추가 필드 검사와 응답 모델.
- `backend/app/services/data.py`: 전체 목록·생성·존재하는 문서 수정·삭제, 무결성 검증,
  create 전제조건과 수정 시각 전제조건, 안전한 404/409/422/500/503 오류. RPC별 10초·자동 재시도 없음.
- `backend/app/services/summary.py`, `schemas/summary.py`: 현재 자료를 읽는 서비스와 분리한 순수 계산·응답 모델.
  한 요청의 DB 읽기는 한 번이며 캐시·요약 저장소 없음. 최소 100개 조건은 적용하지 않음.
- `backend/app/main.py`: 앱 팩터리, 새 라우터 등록, 비밀값 없는 오류 응답, CORS. 기본 서버·문서 제목 유지.
- `backend/app/config.py`, `backend/.env.example`: ALLOWED_ORIGINS 두 로컬 기본 출처와 쉼표 파싱,
  프로세스 환경변수 우선. 실제 `.env` 값은 변경하지 않음.
- `backend/scripts/check_data_api.py`: 명시적 `--live` 실제 통합 검사. 원본 data 읽기와 격리 쓰기 분리.
- 테스트 3개 파일 추가: `test_data_api.py`, `test_data_service.py`, `test_summary.py`.

요약은 최신 저장 월을 기준으로 두 연속 12개월 평균을 비교합니다. 정확한 Fraction 계산으로
반올림 전 방향을 판정하고 표시값만 소수점 둘째 자리로 반올림합니다. 극값의 동률 월을 모두 반환하며,
누락·부족한 최신 24개월은 비교값 null과 insufficient_data로 구분합니다.
오래된 누락은 품질 목록에 표시하고 최근 비교 구간의 누락과 구분합니다.
빈 자료는 200/count=0/total=0, 나머지 정의된 통계는 null·빈 목록으로 응답합니다.

사용 근거: [FastAPI 동기 라우터](https://fastapi.tiangolo.com/async/),
[FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/),
[Pydantic strict mode](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/).

### 오프라인 검증

담당별 관련 테스트 후 전체 오프라인 테스트를 한 번 실행했습니다. 실패한 테스트는 없었습니다.

| 범위 | 통과 개수 |
| --- | --- |
| 기존 Firebase·가져오기 테스트 | 73 |
| CRUD HTTP·입력·CORS·정리 안전성 | 30 |
| Firestore 서비스 모의 테스트 | 22 |
| DB 없는 요약 계산 테스트 | 21 |
| 전체 | **146, 종료 코드 0** |

정상 CRUD 상태·본문, 음수·0·int64 경계, 잘못된 날짜/숫자/불리언/NaN/무한대/memo/추가 필드,
409·404·월 변경 422·비밀값 없는 오류, 저장 형식 오류, 동시 수정·삭제 전제조건을 확인했습니다.
빈 자료·1건·극값 동률·음수 개선/악화/동일 평균·최근 누락·부족·오래된 누락·현재 달과 독립된
최신 월 기준·반올림 전 판정·CRUD 직후 요약 반영·요약당 읽기 한 번을 확인했습니다.
허용·비허용 CORS와 설정 우선순위, health/docs/OpenAPI 유지, --live 없는 DB 미접속도 검증했습니다.
모의 객체는 테스트에만 사용하며 운영 DB 대체 기능은 없습니다.

기존 httpx/TestClient 조합의 Starlette 사용 중단 예고 경고가 있었지만 테스트는 모두 통과했습니다.
이 경고만을 이유로 패키지를 설치·변경하지 않았습니다.

### 실제 Firestore 통합 검사

`check_data_api.py --live`를 **1회 실행**, 종료 코드 **0**입니다.
실제 SDK와 DB를 사용하는 TestClient 통합 검사이며 위 모의 테스트와 구분합니다.

| 검사 | 실제 결과 |
| --- | --- |
| 실제 `GET /api/data` | 200, 128건, 정렬·ID·date/value/memo 타입·값 전체가 CSV와 일치 |
| 실제 `GET /api/data/summary` | 200, 표준 csv·Fraction의 독립 집계와 모든 통계·기간·극값 월·추세 일치 |
| 격리 컬렉션 | `_data_api_checks_84c8a56763794cc08b7d060424f59f1c` |
| 격리 CRUD | 같은 라우터에서 POST 201 → GET 200 → PUT 200 → summary 200 → DELETE 204 |
| 수정 후 summary | 변경한 0 값 즉시 반영, 1건은 insufficient_data |
| 삭제 본문·부재 | 204 본문 없음, 목록 비어 있음, 직접 재조회에서 테스트 문서 부재 확인 |
| finally 정리 | 성공. 이미 삭제되어 추가 삭제 불필요, 정리 실패 없음 |
| 원본 보존 | 검사 전후 128건의 ID·전체 값·타입·create_time·update_time(나노초 포함) 동일 |

원본 전후 전체 해시(문서 메타데이터 포함):
`cb0a475784c06377a59baa6bd26680226e8d7e93160e69a4035271e70db1d994`.
실제 `data`에는 POST·PUT·DELETE를 하지 않았고 가져오기로 덮어쓰거나 복구하지 않았습니다.
보관 CSV의 SHA-256도 기존 `e9c97c21f17695520431434b2e7c587babe2caf4ba62c1d83153329c10570475`와 동일합니다.

### 실제 요약 대조 결과

| 항목 | 확인 값 |
| --- | --- |
| 기간·개수 | 2016-01~2026-08, 128개월 |
| 합계 | −82,400명 |
| 월평균 | −643.75명 |
| 최댓값 / 해당 월 | 430명 / 2021-06 |
| 최솟값 / 해당 월 | −1,756명 / 2025-02 |
| 최신 저장 월 / 값 | 2026-08 / −813명 |
| 최근 12개월 / 평균 | 2025-09~2026-08 / −558.00명 |
| 직전 12개월 / 평균 | 2024-09~2025-08 / −551.42명 |
| 평균 차이 / 추세 | −6.58명 / decrease, 순이동 수치 하락 |
| 전체 누락 월 | 없음 |

이 계산은 원본 CSV를 별도로 읽는 검증 함수로 대조했으며 API의 calculate_summary를
다시 호출한 것만으로 검증하지 않았습니다. 최신 저장 월 기준의 결과이며 현재 달 실적·전체 인구 증감·
이동 원인·정책 효과를 뜻하지 않습니다. 사용자가 저장값을 수정하면 공식 원본과 달라질 수 있습니다.

### 실제 HTTP·서버 보존

변경 코드는 비어 있는 **127.0.0.1:8001**에서 새 Uvicorn 프로세스로 검증했습니다.
health/docs/openapi/data/summary 모두 HTTP 200, API 경로·메서드·128건 정렬·타입·요약 일치를 확인했습니다.
허용 출처 preflight 200과 해당 CORS 헤더, 비허용 출처 preflight 400과 허용 헤더 부재를 확인했습니다.
브라우저 화면을 직접 다시 열어본 검증은 하지 않았습니다.

검증 후 **이번에 만든 실행기 PID 19536과 그 자식 서버 프로세스만 종료**했습니다.
종료 명령 코드 0, 실행기 종료와 8001 포트 닫힘을 확인했습니다.
기존 **8000번 서버는 종료·재시작하지 않았고**, 전후 리스너 주소·포트·PID가 동일했습니다.
기존 8000 서버에 새 코드를 반영하려면 사용자가 해당 서버를 재시작해야 합니다.
기존 서버를 유지하며 확인하려면 README의 8001 별도 실행 명령과 `/docs` 주소를 사용합니다.

### 실행 명령과 근거

프로젝트 루트에서 실제 실행한 명령:

```powershell
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'
& '.\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s backend/tests -t backend -v
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\check_data_api.py' --live
& '.\.venv\Scripts\python.exe' -X utf8 '.\.local\verify_data_api_http.py'
```

모두 종료 코드 0. 키·환경변수·`.env` 원문·로컬 키 파일 경로를 응답이나 로그에 출력하지 않았습니다.

- [전체 오프라인 결과](.local/data-api-offline-tests.log)
- [실제 DB 검사·요약·원본 보존·정리](.local/data-api-live.json)
- [별도 8001 HTTP·CORS·서버 종료](.local/data-api-http.json)
- [8000 작업 전](.local/data-api-port8000-before.json) / [작업 후](.local/data-api-port8000-after.json)
- [최종 확인](.local/data-api-final.json)

**8~9단계 완료.** 필수 API 구현·오프라인·실제 DB 읽기·격리 쓰기·별도 HTTP 검증과 정리가 모두 끝났습니다.
CORS는 사용자 인증이 아니며 **공개 배포 전 쓰기 권한 보호가 필요**합니다. 이번에는 로그인 시스템을 추가하지 않았습니다.
OpenAI 연결·채팅·대화 저장·프론트엔드·공개 배포·Git 작업은 수행하지 않았습니다.

## 10~12단계 — 초기 OpenAI 구현·검증 당시 기록

확인일: 2026-10-28 (Asia/Seoul).

| 단계 | 구현·모의 검증 | 실제 검증 상태 |
| --- | --- | --- |
| 10. OpenAI 연결 | 공식 SDK·Responses 설정·실패 처리 구현, 모의 검증 통과 | 키 인식 완료. 실제 요청 1회가 사용 한도·잔액 관련 오류로 실패하여 **정상 생성 검증 대기** |
| 11. 데이터 기반 채팅 | 공유 요약 주입·제한된 이력·단일 호출·자동 저장 구현, 모의 및 실제 DB+가짜 AI 검증 통과 | **실제 GPT 답변 수치·기간·해석 검증 대기** |
| 12. 대화 저장·조회·불러오기·삭제 | API 구현 완료 | 격리된 실제 Firestore 검증 완료. 실제 AI 시연 대화 생성·불러오기는 대기 |

### 설정·패키지와 작업 범위

초기 구현 검증 당시 프로세스 환경변수와 프로젝트 `backend/.env`만 안전하게 확인했습니다.
키 존재 여부만 기록했으며 **OPENAI_API_KEY 없음**을 확인했습니다. 다른 프로젝트·개인 폴더에서 키를
검색하지 않았고 실제 `.env` 값도 변경하지 않았습니다. 키 신규 발급·결제·충전·모델 자동 변경 없음.

공식 `openai==3.40.0`을 기존 `.venv`에 설치하고 `backend/requirements.txt`에 기록했습니다.
기존 46개 패키지를 constraints로 고정하여 버전 변경 없이 보존했습니다.
필수 추가 의존성은 httpx2 2.16.0, httpcore2 2.16.0, jiter 0.18.0, sniffio 1.3.1,
truststore 0.10.5입니다. 전역 Python 변경 없음. 설치·버전 보존 검사·pip check 모두 종료 코드 0.

설정은 기존 고정 `.env` 경로와 프로세스 환경변수 우선 방식을 재사용합니다.
공개 예제에 빈 키와 `gpt-5.4-mini`, 출력 토큰 800, timeout 45초를 추가했습니다.
기본 모델 이외에는 호환성 확인 전 호출을 차단합니다. 초기 구현 당시 환경설정 파일 중 `.env.example`만 수정했고, 키 파일을 별도로 탐색하지 않았습니다.
실제 Firestore 연결 시 기존 연결 서비스가 기존 설정 경로의 자격증명을 필요한 범위에서 사용하는 것은 유지했습니다.

### 변경한 코드와 동작

- `schemas/chat.py`, `schemas/conversations.py`: 엄격한 요청·응답, UUID4, UTC 시각, 문답 쌍, 길이·역할·추가 필드 제한.
- `routers/chat.py`, `routers/conversations.py`: 채팅 1개와 기록 4개 API, 동기 SDK를 일반 def 라우터에서 실행.
- `services/chat.py`: 매 질문마다 DataService 읽기 + 기존 calculate_summary 직접 재사용, 자기 HTTP 요청 없음.
  최신 SummaryResponse JSON만 고정 instructions에 넣으며 memo·CSV 전체·키·환경변수·내부 경로 제외.
- `services/openai_client.py`: 공식 responses.create 단일 요청, max_retries=0, 설정 timeout,
  reasoning none/store false/stream false, 완료·본문·거절·오류·불완전·길이 확인, 실제 model/usage만 반환.
  내부 SDK 클라이언트는 finally에서 정리하고 자동 재시도하지 않음.
- `services/conversations.py`: 서버 UUID4/UTC/제목·message_count·source 관리, 새 create/기존 조건부 update,
  저장 후 재조회 일치 확인, 한 건 조건부 삭제와 부재 확인.
- `config.py`, `.env.example`, `requirements.txt`: 키 없는 기동과 공개 설정 예시, 설치 버전.
- `main.py`: 새 라우터, 저장 실패 saved=false, 고정 오류 코드·요청 ID만 로그에 기록.
- `scripts/check_chat.py`: 명시적 --live-firestore와 --live-openai 분리, 소유 문서 정리·원본 비교·단일 유료 시도 보호.
- 테스트: `test_chat_api.py`, `test_chat_config.py`, `test_conversations.py`, `test_openai_client.py`.

모델 입력의 과거 대화는 최근 최대 5문답·12,000자이며 문답 쌍 단위로 선택합니다.
저장된 전체 대화는 보존합니다. 저장 한도는 40메시지/20문답, user 2,000자, assistant 4,000자,
제목 80자, UTF-8 JSON payload 256 KiB입니다. 호출 전에 최대 답변 크기까지 예약하고 초과 시 422로 중단합니다.
수동 저장은 GPT를 호출하지 않고 source=manual, 실제 AI 문답이 붙으면 source=chat으로 저장합니다.
사용량이 없으면 null이며 이전 사용량을 현재 응답의 사용량으로 재사용하지 않습니다.

새 대화는 create, 기존 대화는 읽은 갱신 시각 조건으로 update합니다. 동시 변경·삭제는 409,
답변 후 저장 실패는 503/saved=false이며 GPT를 재호출하지 않습니다. DB 저장 미확인은
실제 쓰기 부재를 뜻하지 않으므로 기록을 확인해야 합니다. DB RPC는 각 10초·자동 재시도 없음.
키/인증/모델/잔액 503, 호출 빈도 429, AI timeout 504, 불완전·빈 응답 등 502를 구분합니다.

OpenAI로 질문·요약·선택된 최근 대화가 전달됩니다. store=False를 외부 전송 없음 또는 모든 보관 없음으로 설명하지 않습니다.
근거: [공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
[플랫폼 데이터 관리](https://developers.openai.com/api/docs/guides/your-data), 설치된 공식 SDK 3.40.0의 Responses 인터페이스.

### 오프라인 검증

담당 코드의 관련 테스트 후 전체 오프라인 테스트를 한 번 실행했습니다.

| 범위 | 통과 개수 |
| --- | --- |
| 기존 데이터·요약·Firebase·가져오기 | 146 |
| 채팅·기록 HTTP 및 검사 도구 안전성 | 30 |
| OpenAI 설정 | 16 |
| 대화 모델·Firestore 저장 모의 | 32 |
| SDK 요청·응답·오류 모의 | 39 |
| 전체 | **263, 종료 코드 0** |

새 채팅 저장·이어가기·목록·상세·삭제, 문답/역할/길이/추가 필드/UUID, 최신 요약 주입과 memo 제외,
5문답·12,000자 입력 한도와 전체 기록 보존, 빈 자료·설정 누락·잔액·429·timeout·빈/불완전 응답,
저장 실패·동시 수정/삭제·불필요한 재호출 차단·기존 API 회귀를 확인했습니다.
검사 도구는 소유하지 않은 문서 정리를 거부하며 한 번의 유료 시도 기록이 실패 뒤에도 남는 것을 모의 검증했습니다.
실제 Firestore timestamp 하위 타입은 소유권 비교에서만 정확한 UTC 시각·나노초로 정규화했고,
원본 전후 비교는 전체 타입·메타데이터를 그대로 유지했습니다.

### 실제 Firestore + 모의 AI 검증

`check_chat.py --live-firestore`를 1회 실행해 **종료 코드 0**으로 통과했습니다.
모의 AI 응답은 실제 OpenAI 응답으로 표시하지 않았으며 실제 Responses 생성 요청은 **0회**입니다.

- 격리 컬렉션: `_conversation_checks_cc4d3a0cd47047329b6b257075a5e1df`
- 수동 저장 201, AI 호출 없음.
- 새 채팅 200/saved=true, 기존 ID 이어가기 200/saved=true.
- 전체 4개 메시지와 실제 사용 요약·모의 모델·null 사용량 상세 복원 확인.
- 목록 200, 최신순 및 지정 메타데이터만 포함 확인.
- 생성한 두 대화 삭제 204/본문 없음, 상세 404와 빈 목록·직접 부재 확인.
- finally 정리 결과: 소유 문서 2개 모두 부재, 정리 실패 없음.
- 모의 AI 호출 2회, 라벨 `fake-ai-no-network`, 사용량 null. 실제 AI 성능·답변 품질 증거가 아님.

원본 data 전후 **128건**의 ID·전체 값·타입·생성·수정 시각이 동일했습니다.
메타데이터 포함 해시: `cb0a475784c06377a59baa6bd26680226e8d7e93160e69a4035271e70db1d994`.
기존 conversations는 전후 **0건**으로 동일하며 여기에 테스트용 대화를 저장하지 않았습니다.
원본 CSV 복사본 해시는 기존 `e9c97c21f17695520431434b2e7c587babe2caf4ba62c1d83153329c10570475`와 일치합니다.

### 초기 OpenAI 검증 — 키 미설정으로 미실행했던 기록

키가 없으므로 --live-openai를 실행하지 않았습니다. 실제 생성 **0회**, 실제 모델·토큰 사용량·답변 없음,
시연용 대화 ID 없음입니다. 미제공 사용량을 0으로 기록하거나 모의 답변을 실제 답변으로 제시하지 않았습니다.

검증 예정 질문:
“최신 저장 월 기준으로 최근 12개월과 직전 12개월의 월평균 순이동을 비교해줘.
전체 인구 증감이나 이동 원인까지 이 자료로 확정할 수 있는지도 알려줘.”

키 준비 후 별도 --live-openai 경로는 같은 /api/chat 흐름으로 최대 한 번 생성하고,
성공한 `[연결 검증]` 대화를 기본 conversations에 남긴 뒤 목록·상세를 조회합니다.
이 조회에 GPT를 다시 호출하지 않습니다. 실제 답변의 수치·기간·해석 한계는 그때 직접 검토해야 합니다.
초기 검증 당시 `.local/chat-openai-attempt.json`은 없었습니다. 아래 최신 실제 시도에서 생성됐으며 보호 기록을 유지합니다.
실패·표현 차이를 이유로 자동 재시도하거나 다른 모델을 시도하지 않습니다. 추가 유료 호출에는 별도 허락이 필요합니다.

### 초기 HTTP·서버·실행 근거

기존 8000/8001과 다른 빈 **127.0.0.1:8002**에 검증용 서버를 실행했습니다.
health/docs/OpenAPI/data/summary/conversations 모두 HTTP 200, 새 경로·메서드 확인 통과.
검증용 자식 프로세스에서만 OPENAI_API_KEY를 빈 값으로 두어 chat의 503/openai_key_missing을
확인했습니다. 실제 환경변수나 `.env`를 덮어쓰지 않았으며 이 검사도 유료 호출 0회입니다.
브라우저 화면은 다시 직접 확인하지 않았습니다.

검증 후 이번 실행기 PID **19976**과 그 자식 프로세스만 종료했고 실행기 종료·8002 포트 닫힘을 확인했습니다.
기존 **8000/8001 리스너 주소·포트·PID는 전후 동일**하며 종료·재시작하지 않았습니다.
새 기능 확인용 명령과 http://127.0.0.1:8002/docs 주소는 README에 기록했습니다.

프로젝트 루트에서 실제 실행한 주요 명령:

```powershell
& '.\.venv\Scripts\python.exe' -m pip --isolated --disable-pip-version-check install --no-cache-dir --constraint '.local\openai-existing-constraints.txt' openai
& '.\.venv\Scripts\python.exe' -m pip check
& '.\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s backend/tests -t backend -v
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\check_chat.py' --live-firestore
& '.\.venv\Scripts\python.exe' -X utf8 '.\.local\verify_chat_http.py'
```

모두 종료 코드 0. 실제 OpenAI 명령은 위 실행 목록에 포함하지 않습니다.

- [안전한 키 존재 여부](.local/openai-presence-check.json), [설치·기존 버전 보존](.local/openai-install-verification.json)
- [전체 오프라인 테스트](.local/chat-offline-tests.log)
- [실제 Firestore+모의 AI·정리·원본 보존](.local/chat-firestore-live.json)
- [8002 HTTP·키 누락·프로세스 종료](.local/chat-http.json)
- [8000/8001 작업 전](.local/chat-ports-before.json) / [작업 후](.local/chat-ports-after.json)
- [초기 구현 시점의 단계별 상태](.local/chat-final.json)

### 실제 OpenAI 1회 검증 — 사용 한도·잔액 관련 오류로 실패

2026-10-28 04:57:19~04:57:26 KST에 프로젝트 `.venv`의 새 Python 프로세스에서 실행했습니다.
앞선 키 인식 수정으로 사용자 제공 TXT의 기존 키를 `backend/.env`에 등록했고 Firebase 설정은 보존했습니다.
이번 실행에서는 키 재발급·재탐색·재등록을 하지 않았습니다.

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\check_chat.py' --live-openai
```

- 종료 코드 **1**. 실제 Responses 생성 요청 **1회**, 정상 답변 **0건**.
- 기존 `/api/chat` 흐름이 현재 요약을 읽고 지정 질문으로 요청한 뒤 앱 HTTP **503**, 안전한 코드
  **`openai_quota_unavailable`**, `saved=false`를 반환했습니다.
- 설정 모델 `gpt-5.4-mini`, 최대 출력 800토큰, timeout 45초를 유지했습니다.
  SDK `max_retries=0`, 스크립트의 독점 생성 가드로 추가 요청 없음. 모델 전환 없음.
- 응답의 실제 model/usage는 **null**이며 토큰 사용량을 0으로 추정하지 않았습니다.
- 답변이 없어 기간·수치·해석 대조, 시연용 대화 저장과 목록·상세 복원은 미실행입니다. 대화 ID 없음.
- 생성한 문서 없음, 정리 대상 없음. 기존 data **128→128건**, conversations **0→0건**.
  ID·전체 값·타입·생성·수정 시각의 전후 해시가 모두 동일했습니다.
- `.local/chat-openai-attempt.json`을 보존했습니다. 자동 재시도·추가 유료 호출 없음.
- 기존 8000·8001 등 사용자 서버에 조작하지 않았고 새 서버도 실행하지 않았습니다.
  코드 변경이 없어 기존 263개 테스트를 재실행하지 않았습니다.

필요 조치: 해당 OpenAI API 조직·프로젝트의 사용 한도·잔액·결제 활성 상태 확인.
이번 안전한 오류 기록만으로 이 중 어느 항목이 직접 원인인지는 단정할 수 없습니다.
키 재발급은 요구하지 않으며 결제·충전·모델 변경을 자동 수행하지 않습니다.
문제 해결 후 추가 생성은 사용자의 별도 승인과 기존 시도 기록 보존을 전제로 합니다.

근거: [실제 1회 검사 결과](.local/chat-openai-live.json), [추가 시도 방지 기록](.local/chat-openai-attempt.json).

**10~12단계 전체 완료는 아님.** 실제 OpenAI 연결과 답변·시연용 대화 검증이 남아 있습니다.
인증·사용량 제한 전까지 로컬 전용이며 공개 배포 전 데이터 쓰기, 채팅 비용, 대화 조회 권한을 보호해야 합니다.
프론트엔드·배포·GitHub·로그인·LangChain·벡터 DB·임베딩·MCP·Function Calling·스트리밍은 추가하지 않았습니다.

## 이전 Gemini 전환 기록 — 2026-10-28, 이후 사용자 지시로 중단

아래 구현·검증은 과거 사실로만 보존합니다. 현재 과제의 AI는 OpenAI이며 Gemini 추가 작업은 중단했습니다.

사용자가 기존 Gemini 설정을 재사용하도록 요청했습니다. 지정 파일만 읽기 사용했습니다.
`C:\Users\user\OneDrive\바탕 화면\oiso_changwon\oiso_changwon_clean_20261005\jojunsu-api-setup.txt`

키는 환경변수 대입문 형태로 보관되어 있었습니다. 값을 출력하지 않고 파싱해 현재 프로젝트의
`backend/.env`에 `GEMINI_API_KEY`로 추가했습니다. 원본 파일 바이트와 `.env`의 기존 모든 설정 값·바이트를
보존했으며 Firebase·OpenAI 설정을 변경하지 않았습니다. 새 키 발급과 다른 폴더 탐색 없음.
`AI_PROVIDER=gemini`, `GEMINI_MODEL=gemini-3.5-flash-lite`, 출력 한도 800, timeout 45초를 추가했고
새 Python 프로세스에서 실제 로더의 키 인식·설정 검증을 통과했습니다.

### 구현·패키지

- `config.py`: Gemini 설정과 명시적 제공자 선택. 고정 경로·환경변수 우선, 자동 자격증명 탐색·제공자 전환 없음.
- `routers/chat.py`: 기존 ChatService에 선택한 서비스만 주입. 기존 대화·데이터 서비스는 수정하지 않음.
- `services/gemini_client.py`: 공식 SDK의 네이티브 generate_content 1회, 공식 API 주소·명시적 키,
  총 시도 1회, ms 단위 timeout, 최대 출력 800, MINIMAL thinking, 도구·스트리밍·자동 함수 호출 비활성화.
  정상 STOP 텍스트/실제 model_version 검증, 안전한 오류, 실제 제공 사용량 또는 null.
- `scripts/check_chat.py`: 기존 동일 API 검증 본문을 공유하는 `--live-gemini` 추가.
  Gemini 전용 가드·결과 파일, OpenAI 기록 보존, 정상 시 시연 대화 저장·복원 및 원본 보존 비교.
- `.env.example`: 실제 키 값 없이 두 제공자의 설정만 안내.
- `requirements.txt`: `google-genai==2.33.0` 추가. 필요한 신규 의존성 distro 1.9.0,
  tenacity 9.1.4, websockets 17.3. 기존 52개 패키지 버전 유지, pip check 종료 코드 0.

출력 사용량은 제공된 candidates_token_count에 thoughts_token_count가 제공된 경우만 더합니다.
미제공 수치를 추정하지 않습니다. Gemini에는 질문·요약·선택된 최근 대화가 전송되며 OpenAI의 store=False가 적용되지 않습니다.
모델 근거: [Google 공식 모델 문서](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
[파라미터 안내](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.6).

### Gemini 전환 준비 시 실행한 오프라인 검증

| 검사 | 통과 개수 |
| --- | --- |
| Gemini 설정·제공자 선택 | 16 |
| Gemini SDK 요청·응답·오류 | 29 |
| Gemini 검사 도구·가드 분리 | 12 |
| 기존 채팅·저장·복원·실패 회귀 | 30 |
| 기존 OpenAI 설정 회귀 | 16 |
| 합계 | **103** |

각 관련 검사 최종 종료 코드 0. 최초 설정 검사 명령은 프로젝트 루트에서 모듈 경로를 잘못 지정해
`ModuleNotFoundError: app`가 발생했으며 코드를 바꾸지 않고 backend에서 재실행해 32개 통과했습니다.
기존 전체 263개 검사는 반복하지 않았습니다.

주요 검사 명령은 backend에서 프로젝트 `.venv`의 Python으로 실행했습니다.

```powershell
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant\backend'
& '..\.venv\Scripts\python.exe' -X utf8 -m unittest tests.test_gemini_config tests.test_chat_config -v
& '..\.venv\Scripts\python.exe' -X utf8 -m unittest tests.test_gemini_client -v
& '..\.venv\Scripts\python.exe' -X utf8 -m unittest tests.test_gemini_check -v
& '..\.venv\Scripts\python.exe' -X utf8 -m unittest tests.test_chat_api -v
```

새 Python 프로세스의 TestClient로 /health, /docs, /openapi.json HTTP 200 확인.
서버를 띄우거나 기존 8000·8001 서버를 종료·재시작하지 않았습니다. 이 준비 단계에서는 실제 DB에 접근하지 않았으며
128건 대조와 시연 대화 저장은 아래 승인 후 실제 검사에서 수행했습니다.

### 실제 검증 승인 전의 상태와 보안 기록

준비 단계까지 Gemini 실제 생성은 **0회**였습니다. 추가 유료 호출 별도 승인 조건을 유지해 준비까지만 수행했습니다.
당시 시연용 Gemini 대화·실제 모델 응답·사용량은 없었고 `chat-gemini-attempt.json`도 미생성이었습니다.
이전 OpenAI 생성 요청 1회 가드와 `openai_quota_unavailable` 실패 보고서는 유지했습니다.
승인 전에는 10~12단계 전체 완료로 표시하지 않았습니다. 다음은 당시 Gemini 검증 기록이며 현재 GPT 완료 근거가 아닙니다.

예제 파일을 확인하는 과정에서 실제 OpenAI 키가 들어 있던 `.env.example`을 출력하는 실수가 있었습니다.
사용자에게 즉시 알렸고 예제의 키 값을 제거했으며 두 예제 키 항목이 비어 있음을 확인했습니다.
노출된 OpenAI 키는 사용자가 폐기해야 합니다. 실제 `.env`와 원본 키 파일을 임의로 삭제하지 않았습니다.
Gemini 키는 값·일부 문자·파일 내용 모두 출력하지 않았습니다.

근거: [설치·기존 버전 보존](.local/gemini-install-verification.json),
[설정 인식·오프라인 HTTP·검사 개수·실제 호출 0회](.local/gemini-preparation.json).

## 과거 승인 후 Gemini 실제 1회 검증 결과 — 2026-10-28

사용자가 “Gemini 1회 검증 진행”을 선택한 뒤 기존 `.venv`의 새 Python 프로세스에서 실행했습니다.
실행 시각: **2026-10-28 05:20:44~05:20:50 KST**, 종료 코드 **0**.

```powershell
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\check_chat.py' --live-gemini
```

Gemini 생성 요청 **1회 성공**, 이번 OpenAI Responses 요청 **0회**.
기존 OpenAI 실패 요청 1회와 Gemini 성공 요청 1회의 기록을 각각 보존했습니다.
모델·최대 출력 800토큰·45초 timeout·SDK 총 시도 1회 설정은 유지했고 재시도·대체 모델·추가 생성은 없었습니다.

### 실제 질문·답변과 대조

질문: “최신 저장 월 기준으로 최근 12개월과 직전 12개월의 월평균 순이동을 비교해줘.
전체 인구 증감이나 이동 원인까지 이 자료로 확정할 수 있는지도 알려줘.”

실제 모델: **gemini-3.5-flash-lite**. 제공된 사용량: **입력 796토큰, 출력 231토큰**.

실제 답변:

> 창원시 월별 순이동 데이터를 바탕으로 한 최근 12개월과 직전 12개월의 평균 비교 결과입니다. 최신 저장 월인 2026년 8월을 기준으로 최근 12개월(2025년 9월~2026년 8월)의 월평균 순이동은 -558.0명이며, 직전 12개월(2024년 9월~2025년 8월)의 월평균은 -551.42명으로 집계되었습니다. 두 기간 평균의 차이는 -6.58명으로, 순이동 수치는 하락(순유출 확대 또는 순유입 감소)한 것으로 나타났습니다.
>
> 다만, 순이동은 전입과 전출의 차이만을 나타내므로 출생과 사망 등을 포함한 전체 인구 증감과 동일하지 않습니다. 또한 본 데이터만으로는 인구 이동의 원인이나 특정 정책의 효과를 확정하여 설명할 수 없습니다.

실제 전달 요약과 최신 월·두 기간·평균·차이를 직접 대조해 모두 일치함을 확인했습니다.
전체 인구 증감과 순이동을 구분하고 원인·정책 효과·통계적 유의성을 과장하지 않았습니다.
두 평균 모두 음수이므로 이번 자료에 한정한 정확한 해석은 **월평균 순유출 규모 6.58명 확대**입니다.
답변의 “또는 순유입 감소”는 일반적인 대안 표현으로 불필요하지만 수치·방향 오류는 아닙니다.
이 표현을 이유로 재호출하거나 저장 답변을 변경하지 않았습니다.

### 자동 저장·복원·보존

- 같은 `/api/chat` 흐름으로 생성 후 저장을 확인했고 `saved=true`입니다.
- 제목 `[연결 검증]`의 시연 ID: **`94ff2d2f-dc18-4f50-a0c6-0f933c13b57e`**.
- 목록에서 정확히 한 건 확인, 상세에서 동일 질문·답변·요약·모델·사용량 복원 확인.
- `api_checks_passed`, `listed`, `reload_matches` 모두 true. 조회 시 추가 생성 없음.
- 시연 대화 1건은 요청대로 유지. 그 외 생성·정리 대상 없음.
- 원본 data **128→128건**. 모든 ID·값·타입·생성·수정 시각의 해시 동일:
  `cb0a475784c06377a59baa6bd26680226e8d7e93160e69a4035271e70db1d994`.
- 기존 conversations는 0건이었으며 시연 추가 후 1건. 시연 ID를 제외한 전후 해시 동일.
- Gemini·OpenAI의 시도 방지 파일을 모두 유지했습니다. 키 재탐색·재등록·발급 없음.
- 기존 8000·8001 등 사용자 서버를 종료·재시작하지 않았고 새 서버도 실행하지 않았습니다.
- 구현 수정이 없어 기존 전체 263개 및 전환 관련 103개 테스트를 반복하지 않았습니다.

| 단계 | 당시 Gemini 기준 검증 상태(현재 GPT 완료 판정에 사용하지 않음) |
| --- | --- |
| 10. AI 연결 | **완료** — 실제 Gemini 정상 응답 1회 |
| 11. 데이터 기반 채팅 | **완료** — 전달 요약과 실제 답변의 기간·수치·해석 한계 대조 |
| 12. 대화 저장·조회·불러오기·삭제 | **완료** — 이번 실제 답변의 저장·목록·상세 복원 + 기존 격리 실제 DB 삭제 검증 |

실제 시연 대화는 보존해야 하므로 이번에는 삭제하지 않았으며 삭제 기능의 근거는 앞선 격리 DB 검증입니다.
초기 과제의 OpenAI 연결 성공을 뜻하지 않습니다. 당시 Gemini 전환 요청에 따라 검증했으나 이후 전환 지시가 취소됐습니다.
이전에 노출된 OpenAI 키의 폐기 완료 여부는 확인하지 않았습니다.

근거: [실제 생성·저장·복원·보존 결과](.local/chat-gemini-live.json),
[실제 답변 대조 결과](.local/gemini-answer-review.json), [Gemini 1회 시도 방지 기록](.local/chat-gemini-attempt.json).

## OpenAI GPT 경로 복구 — 2026-10-28, 외부 호출 없음

최신 사용자 지시가 Gemini 전환을 취소하고 OpenAI GPT 사용을 다시 명시했습니다.
현재 상태는 **GPT 구현·키 인식 완료, 실제 답변 검증은 결제·사용 한도 해결 대기**입니다.
10~12단계 전체 완료로 표시하지 않습니다.

### 중단 범위와 최소 수정

Gemini는 앞선 승인으로 연결 코드·설정·모의 검사와 실제 생성 1회·시연 대화 저장까지 진행됐습니다.
이번에는 Gemini 구현·키 탐색·실제 요청을 모두 중단했고 오이소창원 프로젝트를 탐색하거나 수정하지 않았습니다.
현재 진행 중인 외부 생성 요청은 없으며 새로운 호출을 시작하지 않았습니다.

- `backend/.env`: 기존 `AI_PROVIDER=gemini` 한 항목만 `openai`로 변경.
- `backend/.env.example`: 같은 제공자 항목만 `openai`로 변경. 키 값은 출력하지 않음.
- README·PROGRESS: 현재 GPT 상태와 과거 Gemini 기록을 구분.
- 기존 `OPENAI_API_KEY`, OpenAI 모델·한도·timeout, Firebase 및 나머지 설정은 모두 값이 같음을 확인.
- OpenAI Responses 코드·라우터·요약·대화 서비스는 그대로 유지. Gemini 잔여 코드·패키지의 불필요한 정리 없음.
- 현재 프로젝트 밖의 파일 접근·수정, Git 이력 변경·푸시, 프론트엔드·배포 없음.

### 새 Python 프로세스의 실제 설정 경로 확인

기존 로더는 `backend/.env` 고정 경로를 매번 읽으며 캐시가 없습니다.
현재 프로세스에는 파일 값을 가리는 AI_PROVIDER 환경변수가 없었습니다.
소켓 연결을 차단한 새 프로젝트 `.venv` Python 프로세스에서 실제 `get_chat_service`에
외부 저장소 대신 객체를 주입해 선택된 AI 서비스만 확인했습니다.

- `load_ai_provider()` → **openai**.
- 선택 서비스 → **OpenAIService**, 기존 키 인식 성공(값·일부 문자 미출력).
- 모델 **gpt-5.4-mini**, 최대 출력 **800토큰**, timeout **45초** 유지.
- Gemini 설정 함수가 호출되면 실패하게 만든 검사도 통과. Gemini 서비스 모듈 미로딩.
- SDK 클라이언트 미생성, 실제 AI·DB 요청 **0회**.
- 기존 호출 코드는 `https://api.openai.com/v1` + `responses.create`, `max_retries=0`이며
  Gemini 주소·키를 사용하거나 다른 모델·제공자로 자동 전환하지 않습니다.

### 필요한 모의 검사만 실행

프로젝트 backend에서 `.venv` Python의 unittest로 아래 기존 테스트 11개를 선택 실행했습니다.
**11개 통과, 종료 코드 0**. 코드 변경이 없어 전체 263개 및 Gemini 관련 103개 검사는 반복하지 않았습니다.

| 범위 | 선택 검사 |
| --- | --- |
| 제공자 선택 3개 | OpenAI 기본 호환·명시적 OpenAI 라우터·잘못된 제공자 시 우회 차단 |
| Responses 4개 | 공식 주소·재시도 0·timeout, 요약 포함 요청, 정상 응답·실제 사용량, 할당량 오류 재호출 차단 |
| 채팅·저장 4개 | 매 질문 최신 요약, 새 대화 저장·복원, 기존 기록 이어가기, 저장 실패 시 추가 생성 없음 |

이 검사는 가짜 응답·모의 DB만 사용했습니다. 모의 통과를 실제 GPT 답변 성공으로 표시하지 않습니다.
실제 Firestore를 읽거나 쓰지 않았으므로 원본 128건과 기존 시연 대화에 변경을 가하지 않았습니다.
사용자 서버를 종료·재시작하지 않았고 새 서버도 띄우지 않았습니다.

OpenAI 실패 보고서·1회 시도 방지 파일, Gemini 보고서·시도 방지 파일·답변 검토,
기존 준비·Firestore 검사·전체 테스트 로그의 전후 파일 해시 일치를 확인했습니다.
과거 데이터 보존·실제 검증 근거는 그대로 유지하며 이번에 다시 실제 DB 검증했다고 쓰지 않습니다.

### 남은 작업

사용자 보고상 API 잔액은 0달러였으며 이번 작업에서 결제 화면을 다시 조회하지 않았습니다.
사용자가 **결제·잔액 반영 완료를 알리고 추가 1회 검증을 허용하기 전에는 실제 OpenAI 요청을 하지 않습니다.**
자동 결제·충전·모델 변경과 키 재발급·재탐색·재등록을 하지 않았습니다.
기존 실패·재시도 방지 기록을 보존합니다. 현재 단계별 상태:

| 단계 | 현재 GPT 과제 상태 |
| --- | --- |
| 10. OpenAI 연결 | 구현·키 인식 완료, 결제·사용 한도 해결 후 정상 응답 검증 대기 |
| 11. 데이터 기반 채팅 | 구현·모의 검증 완료, 실제 GPT 답변 대조 대기 |
| 12. 대화 저장·조회·불러오기·삭제 | 기존 구현·모의 및 격리 실제 DB 검증 유지, 실제 GPT 시연 대화 저장·복원 대기 |

근거: [현재 실제 앱의 OpenAI 선택](.local/openai-restored-path.json),
[복구·모의 검사·과거 기록 보존 결과](.local/openai-restore-verification.json).

## 코디세이 키로 승인된 실제 GPT 1회 검증 — 2026-10-29

실행 ID: `codyssey-20261029-01`. 실행 시각: 11:54:13~11:54:18 KST.
이번 키의 실제 생성 요청은 기존 0회에서 **1회**가 됐으며 이후 추가 요청은 없습니다.
사용자 승인에 따라 기존 검사 도구를 새 `.venv` 프로세스에서 실행했으며 키 재등록·재발급·재탐색은 하지 않았습니다.

### 최소 변경과 모의 확인

- `backend/scripts/check_chat.py`: 명시적 `--run-id`별 방지 파일·결과 분리, 동일 ID 차단, `[GPT 연결 검증]` 제목 표시,
  전달 요약과 제공자의 정수 HTTP 상태·허용 목록 오류 코드만 기록. 기존 앱의 Responses·요약·저장 코드는 유지.
- `backend/tests/test_chat_live_run.py`: 새 7개 오프라인 검사. 이전 기록 보존·재실행 차단·경로 조작 차단·안전한 오류 분류 등.
- `backend/tests/test_gemini_check.py`: 기존 성공 모의 응답에 모델·사용량 필드를 보충. 실제 Gemini 호출 없음.
- 새 실행/기존 검사 도구 테스트 19개와 기존 호출·응답·저장·정리 관련 18개, 합계 **37개 통과**, 각각 종료 코드 0.
  전체 263개를 반복하지 않았습니다.
- 실제 설정 로더와 앱 의존성 확인: `openai` → `OpenAIService`, 키 존재, `gpt-5.4-mini`, 출력 800토큰·45초.
  SDK `max_retries=0`, 1회 생성 후 저장 실패로 재생성하지 않는 기존 동작을 유지했습니다.

### 실제 명령과 결과

프로젝트 루트에서 실행:

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 -c 'import logging, runpy; logging.disable(logging.CRITICAL); runpy.run_path("backend/scripts/check_chat.py", run_name="__main__")' --live-openai --run-id codyssey-20261029-01
```

종료 코드 **1**. 기존 FastAPI `POST /api/chat`의 처리 흐름에서 현재 Firestore 요약을 읽고 질문과 함께 실제 Responses 요청을 1회 보냈습니다.

| 확인 항목 | 실제 결과 |
| --- | --- |
| 앱 오류 | HTTP 503, `openai_authentication_failed`, `saved=false` |
| 제공자 오류 | HTTP 401, `invalid_api_key` |
| 요청/응답 모델 | 요청 `gpt-5.4-mini`; 실제 응답 모델 미제공 |
| 토큰·정상 답변 | 사용량 미제공, 정상 답변 없음 |
| 전달 기간·평균 | 최신 월 2026-08; 2025-09~2026-08 -558.00명, 2024-09~2025-08 -551.42명 |
| 전달 해석 한계 | 월별 순이동과 전체 인구 증감 구분, 현재 달 자료 아님, 원인·정책 효과 확정 불가 포함 |
| GPT 답변 내용 대조 | 생성 실패로 수행 불가; 전달 요약을 AI 답변으로 표시하지 않음 |
| 자동 저장·목록·상세 복원 | 정상 답변 없음으로 수행하지 않음; 신규 대화 ID 없음 |
| 원본 data | 128 → 128건, ID·타입 포함 내용·생성/수정 시각 해시 일치 |
| 기존 conversations | 1 → 1건, 동일 범위 해시 일치; 기존 Gemini 시연 대화 보존 |
| 문서 쓰기·정리 | 생성·수정·삭제한 문서 없음 |

이전 개인 키의 실패·방지 기록, Gemini 성공·방지·검토·준비 기록, 기존 Firestore 검사와 전체 테스트 로그 **8개 파일의 해시 일치**도 확인했습니다.
이번 실행의 별도 방지 파일과 실패 결과를 보존하며 재시도·모델 변경·Gemini 전환·결제·충전은 하지 않았습니다.
사용자 서버를 종료·재시작하지 않았고 프론트엔드·배포·Git 작업은 하지 않았습니다.

### 남은 작업과 현재 상태

코디세이 지원 담당자의 키 활성 상태 및 공식 OpenAI API 접속 방식 확인이 필요합니다.
현재 근거는 인증 실패이며, 개인 키의 잔액 부족을 이번 키에 적용하지 않습니다.
키 폐기·오타·별도 접속 방식 중 어느 것이 원인인지는 이 응답만으로 확정할 수 없습니다.

| 단계 | 최신 상태 |
| --- | --- |
| 10. OpenAI 연결 | 구현·로컬 키 인식 완료, 코디세이 키 인증 문제 해결 후 정상 답변 검증 필요 |
| 11. 데이터 기반 채팅 | 구현·모의 검증 유지, 실제 GPT 답변의 기간·수치·해석 검증 미완료 |
| 12. 대화 저장·조회·불러오기·삭제 | 구현·기존 실제 DB 검증 유지, 실제 GPT 시연 자동 저장·목록·상세 복원 미완료 |

**10~12단계 전체 완료로 표시하지 않습니다.** 추가 GPT 생성 요청은 이번 승인에 포함되지 않습니다.
근거: [실제 실패 결과](.local/chat-openai-codyssey-20261029-01-live.json),
[이번 시도 방지 기록](.local/chat-openai-codyssey-20261029-01-attempt.json),
[새 프로세스 사전 확인](.local/codyssey-openai-preflight-20261029.json),
[최종 검토와 기록 보존](.local/chat-openai-codyssey-20261029-01-review.json).

## 코디세이 Chat Completions 전환 및 10~12단계 완료 — 2026-10-29

사용자가 공식 연결 안내와 실제 생성 요청 추가 1회를 명시적으로 허용했습니다.
새 실행 ID `codyssey-chat-20261029-01`, 실행 12:21:58~12:22:08 KST, 종료 코드 **0**.

### 최소 변경

- `backend/app/config.py`: `OPENAI_BASE_URL`을 고정 `.env` 경로·프로세스 우선 규칙으로 읽음. 승인 주소 `https://copa.codyssey.kr/v1`만 허용하며 잘못된 주소를 다른 서버로 우회하지 않음.
- `backend/app/services/openai_client.py`: SDK 생성에 설정 base_url 명시, `client.chat.completions.create` 사용. system 규칙·현재 요약과 기존 제한된 messages, `max_completion_tokens=800`만 전달. timeout 45초·재시도 0 유지.
- 응답: choices 첫 메시지의 assistant 본문과 finish_reason=stop을 확인. 빈 답변·차단·거절·잘림·도구 응답 거부. prompt/completion 토큰을 기존 input/output 필드로 변환, 없는 값 추정 안 함.
- `backend/.env`, `.env.example`: base URL 한 항목만 추가. 기존 키·Firebase·AI_PROVIDER·모델·기타 설정 보존 확인. 비밀값 출력 없음.
- `backend/scripts/check_chat.py`: 기존 1회 검증 경로 유지, `[코디세이 GPT 연결 검증]` 표시와 chat_completions 요청 수·중계 주소 기록. 기존 요약·채팅·대화 저장 서비스는 변경하지 않음.
- 관련 테스트 수정·추가: `test_openai_client.py`, `test_codyssey_http.py`, `test_chat_config.py`, `test_chat_live_run.py`.

### 외부 접속 없는 관련 검증

| 범위 | 통과 수 | 확인 내용 |
| --- | --- | --- |
| OpenAI 클라이언트 단위 검사 | 41 | 인자·완료/실패 판정·사용량·오류·단일 호출 |
| 실제 SDK + 모의 HTTP | 10 | 정확한 최종 Codyssey URL, system/이력/질문, max_completion_tokens, 재시도/다른 서버 전환 없음 |
| 설정·채팅 API·검사 도구·실행 ID | 67 | 설정 우선순위·주소 차단·요약·저장·불러오기·실패 시 재생성 없음·과거 기록 보존 |
| OpenAI 제공자 선택 | 3 | 기본/명시적 OpenAI, 잘못된 제공자 거부 |
| 합계 | **121** | 가짜 키·모의 객체/전송만 사용 |

클라이언트 41개, 모의 HTTP 10개, 제공자 3개 명령은 각각 종료 코드 0입니다.
67개 검사 실행 명령에 존재하지 않는 제공자 테스트 이름 1개를 함께 지정해 로더 오류가 발생했습니다.
실제 67개는 모두 통과했고, 잘못 지정한 이름을 수정해 제공자 3개만 별도 실행하여 통과했습니다. 전체 263개는 반복하지 않았습니다.
모의 HTTP는 소켓 연결을 차단하고 요청 URL·JSON만 검사했으며 실제 키나 Authorization 헤더를 출력하지 않았습니다.

### 실제 실행과 답변 대조

프로젝트 루트에서 새 `.venv` Python 프로세스로 실행:

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 -c 'import logging, runpy; logging.disable(logging.CRITICAL); runpy.run_path("backend/scripts/check_chat.py", run_name="__main__")' --live-openai --run-id codyssey-chat-20261029-01
```

실제 `POST /api/chat` 처리 흐름: 현재 Firestore 요약 → 코디세이의 Chat Completions 1회 → 정상 답변 → 자동 저장 → 목록 → 상세 복원.
최종 외부 URL은 **https://copa.codyssey.kr/v1/chat/completions**. `AI_PROVIDER=openai`, 중계 `codyssey`, 실제 응답 모델 **gpt-5.4-mini**.
실제 생성 **1회**, Responses **0회**, 추가 생성·자동 재시도 **0회**. 입력 **736토큰**, 출력 **198토큰**이 제공됐습니다.

| 답변 검토 항목 | 결과 |
| --- | --- |
| 최신 저장 월 | 2026-08, 현재 날짜와 혼동 없음 |
| 최근 12개월 | 2025-09~2026-08, 월평균 -558.0명 |
| 직전 12개월 | 2024-09~2025-08, 월평균 -551.42명 |
| 차이·방향 | -6.58명, 순이동 수치 하락으로 정확히 설명 |
| 해석 한계 | 순이동과 출생·사망 포함 전체 인구 증감 구분; 이동 원인·정책 효과 확정 불가; 현재 달 실적 아님 |
| 완료 여부 | 서비스가 finish_reason=stop·비어 있지 않은 본문 검증을 통과시킴; 잘린 답변으로 취급할 근거 없음 |

답변은 '순이동 수치 하락'이라고 표현했으며, '두 기간 모두 순유출이고 최근 월평균 순유출 규모가 약 6.58명 증가'를 명시적으로 풀어 쓰지는 않았습니다.
표현을 더 명확하게 할 여지는 있으나 기간·수치·방향의 오류는 없습니다. 원문을 수정하거나 다시 생성하지 않고 검토 기록에 남겼습니다.

### 자동 저장·복원·보존

- `/api/chat` HTTP **200**, `saved=true`.
- 시연 대화 ID: **b3d5e4ba-9bda-46db-90d6-b012e071b5b6**. 제목은 `[코디세이 GPT 연결 검증]`으로 시작하며 기존 규칙에 따라 질문을 붙이고 80자로 제한합니다.
- 목록에 해당 ID가 정확히 1건 존재하고 상세에서 같은 질문·답변 2개 메시지·요약·응답 모델·제공 사용량이 복원됐습니다.
- 원본 data **128→128건**, ID·타입 포함 전체 값·생성/수정 시각 해시 일치.
- 기존 Gemini 대화 **1건** 동일 범위 보존. 이번 시연 1건만 추가되어 conversations **1→2건**. 기존 문서 수정·삭제 없음.
- 이전 개인 키 실패, OpenAI 직접 주소에서의 코디세이 키 실패, Gemini 성공, 각 시도 방지 및 검토·테스트 기록 **12개 파일 해시 일치**.
- 사용자 서버 종료·재시작 없음. 실제 조회 검증 때문에 GPT를 다시 부르지 않았으며 키 재발급·재탐색·개인 결제·프론트엔드·배포·Git 작업 없음.

| 단계 | 현재 상태 |
| --- | --- |
| 10. OpenAI 연결 | **완료** — 코디세이 중계 서버의 실제 GPT 정상 답변 1회 |
| 11. 데이터 기반 채팅 | **완료** — 현재 요약 전달과 실제 답변의 기간·수치·해석 대조 |
| 12. 대화 저장·조회·불러오기·삭제 | **완료** — 기존 기능/삭제 검증 유지, 실제 GPT 시연 자동 저장·목록·상세 복원 추가 확인 |

현재 범위의 미해결 실행 오류는 없습니다. 이 완료는 로컬 백엔드 10~12단계이며 프론트엔드·배포 완료를 뜻하지 않습니다.
근거: [실제 결과와 답변 원문](.local/chat-openai-codyssey-chat-20261029-01-live.json),
[답변 대조·과거 기록 보존](.local/chat-openai-codyssey-chat-20261029-01-review.json),
[이번 1회 시도 방지 기록](.local/chat-openai-codyssey-chat-20261029-01-attempt.json),
[설정·사전 기록](.local/codyssey-chat-completions-preflight-20261029.json).

## 13~14단계 웹 화면 — 2026-10-29, 일부 검증 미완료

### 구현과 범위

- `frontend/index.html`, `styles.css`: 밝은 한국어 화면, 요약·채팅·대화 목록·월별 데이터 폼/표, PC 병렬/모바일 한 열 CSS, 입력 이름·키보드 포커스.
- `frontend/app.js`: 기존 summary/chat/conversations/data API 계약을 사용. 요약 재계산 없이 서버값 표시, null/0 구분, textContent 출력, 서버 ID로 이어가기, 저장 여부 표시, 실패 입력 보존, IME·중복 전송 방지, 수정 월 잠금·대상 확인·목록/요약 갱신.
- `frontend/api.js`, `config.js`: 공통 오류·204·timeout 처리, 자동 재시도 없음. 공개 FastAPI 주소 한 곳(`http://127.0.0.1:8002`). 브라우저에 비밀 설정 없음.
- `backend/scripts/check_frontend.py`: 기존 앱과 서비스·의존성 교체·격리 컬렉션·소유 문서 정리 방식을 재사용한 로컬 검증 도구. 명시적 모드만 허용하며 공개 제어 엔드포인트 없음. 실제 AI 모드는 승인 질문 1회 방지 기록과 원본 쓰기 차단을 포함하지만 이번에는 실행하지 않음.
- `backend/tests/test_frontend_check.py`, `backend/tests/frontend-unit-tests.mjs`: 관련 모의 테스트. 새로운 패키지/프레임워크 설치 없음.
- 기존 운영 API·키·Firebase·코디세이 제공자/모델/주소/출력 제한/재시도 설정은 변경하지 않음. 사용자 서버와 이전 검증 기록 보존.

### 실제 검증과 모의 검증 구분

| 구분 | 결과 및 한계 |
| --- | --- |
| 실제 정상 백엔드 HTTP | 8002번 health/docs/OpenAPI 200, data 128건·summary 128건·대화 2건·기존 GPT 시연 상세 200. GPT 상세 모델 gpt-5.4-mini, 메시지 2개. AI 재생성 없음 |
| 실제 CORS·정적 루트 | 5500 출처의 OPTIONS 200, allow-origin은 정확히 http://127.0.0.1:5500. frontend만 제공, .env/키 TXT 및 상위 경로 요청 404, frontend 심볼릭 링크 없음 |
| 실제 Chrome + 격리 Firestore | 빈 데이터 표시 → 2040-01 값0 추가201 → 같은 월 중복409/입력 보존 → 2040-02 값-12 추가201. 목록 최신순·요약 갱신·0과 자료없음 구분·평균 -6 확인 |
| 실제 Chrome 입력 안전 | HTML 형태 메모가 문자로 표시되며 해당 표의 img 요소0. 수정 폼에 기존 값 채움과 월 잠금 확인. 수정 확인 창의 대상월/변경값 표시까지 확인 |
| 수정 완료·삭제 화면 | 확인 창 처리 중 도구가 중단되어 PUT/DELETE 성공 화면 미확인. 보고서에 PUT/DELETE 요청 없음. 문서 정리는 UI 기능 검증과 별도로 실행 |
| 프론트엔드 순수 테스트 | 최종 파일을 캐시 없이 읽어 47/47 통과. 날짜·정수·IME·Shift+Enter·중복 제출·fake fetch·204·422/409/404/503·비JSON·네트워크/timeout·자동 재시도 없음. 외부 HTTP/DB/AI 0 |
| 검증 도구 오프라인 테스트 | 9/9 통과, 종료 코드0. 가짜 클라이언트·TestClient 사용, 외부 DB/AI 0 |
| 브라우저 미확인 | 기존 GPT 시연 화면 불러오기·새로고침 복원, 채팅 로딩/실패/이어가기/저장/삭제, 수정·삭제 성공, 서버중단·422·503 화면, 390px 모바일. 모의 테스트를 이 항목의 실제 화면 성공으로 대체하지 않음 |
| 화면 캡처 | 1440×1000 초기 화면은 관찰. 최종 PC 및 390px 검수용 캡처 파일은 생성하지 못함 |
| 이번 실제 AI | 0회. 브라우저 검증 대신 직접 호출하지 않음. 새 대화0, 이번 실제 답변·자동 저장·화면 복원은 미수행 |

### 중단 원인, 정리와 보존

2040-02 격리 기록을 -15로 바꾸는 확인 창에서 브라우저 명령이 timeout으로 중단되었습니다. 컴퓨터 사용 복구 도구도 현재 브라우저 URL을 정책 검증에 필요한 수준으로 확인하지 못해 이번 턴 화면 조작을 중단했습니다. 이후 브라우저 입력·실제 GPT 호출은 하지 않았습니다.

검증 서버의 stdin이 닫혀 `stop` 입력을 보낼 수 없었습니다. 실행 명령을 대조하여 이번에 만든 격리 서버 PID29692(8011)만 종료하고, 원본 스냅샷과 보고서를 보존한 채 복구 정리를 수행했습니다.

- 이번 소유 `changwon-net-2040-01`, `changwon-net-2040-02`의 ID·값·메모·생성 시각 확인 후 기존 `cleanup_owned` 사용.
- 문서별 삭제 및 부재 확인 성공, 두 격리 컬렉션의 잔여 문서0. 컬렉션 전체 삭제 없음.
- 최초 `.local/frontend-original-before.json` 대비 원본 data **128건**, 기존 GPT/Gemini 대화 **2건**의 ID·타입 포함 전체 값·생성/수정 시각 해시가 정리 전후 모두 일치.
- 기존 사용자 서버8000 PID1656 유지. 정상 백엔드8002 PID9424와 정적 서버5500 PID31036 유지. 8011은 종료.
- 공개 config는 정상 백엔드8002로 복원하고 HTTP로 확인. 브라우저에 격리 확인 창이 남으면 취소 후 새로고침 필요.

### 실행·증거와 남은 일

프로젝트 루트에서 새 프로세스로 실제 실행한 서버 명령:

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002
& '.\.venv\Scripts\python.exe' -X utf8 -m http.server 5500 --bind 127.0.0.1 --directory frontend
# 당시 실행한 격리 검증 서버. 이미 종료·정리됐고 같은 run-id 재사용은 차단됩니다.
& '.\.venv\Scripts\python.exe' -X utf8 -c 'import logging, runpy; logging.disable(logging.CRITICAL); runpy.run_path("backend/scripts/check_frontend.py", run_name="__main__")' --isolated-firestore --run-id ui-isolated-20261029 --port 8011
```

최종 실행 주소: 화면 <http://127.0.0.1:5500/>, 문서 <http://127.0.0.1:8002/docs>. 재실행 위치·별도 PowerShell 창 사용 방법은 README 최신 절에 기록했습니다. 현재 실행 중인 동일 포트에 중복 실행하지 않습니다.

증거:
- [실제 서버/CORS/정적 루트 검사](.local/frontend-initial-read-check.json)
- [최종 서버 실행·공개 설정 확인](.local/frontend-final-server-check.json)
- [프론트엔드 순수 검사47개](.local/frontend-unit-tests.json)
- [격리 UI API 요청과 종료 보고서](.local/frontend-ui-isolated-20261029-report.json)
- [소유 문서 정리·최초 스냅샷 대비 원본 보존](.local/frontend-ui-isolated-20261029-cleanup.json)

**13~14단계 전체 미완료**: 화면 코드는 준비됐으나 위 브라우저 미확인 항목, PC/모바일 캡처, 실제 화면 GPT 1회·저장·새로고침 복원 검증이 남았습니다. 기존 10~12단계의 완료 근거는 유지합니다. 공개 배포 전에 데이터 변경·대화 접근·AI 호출 권한 보호 및 코디세이 키의 배포 사용 허용 범위 확인이 필요합니다. 프론트 공개 배포·GitHub 작업은 하지 않았습니다.

## 13~14단계 재개 검수 결과 — 2026-10-29

### 확인한 화면 동작

| 항목 | 실제 브라우저 확인 결과 |
| --- | --- |
| 초기 화면 | 정상 원본128행·요약·버튼·입력 표시. 초기 콘솔 error 항목0 |
| 기존 GPT 대화 | 목록 클릭으로 실제 gpt-5.4-mini 기록의 질문·답변 표시. 새로고침 후 messages 문자열 동일. AI 호출 없음 |
| PC/모바일 | 1440×1000, 390×844 관찰·캡처. 페이지 가로 넘침 없음. 버튼 겹침 없음. 모바일 대화 목록 접기/펼치기와 폼·표 접근 가능 |
| 격리 자료 추가/중복 | 2041-01 값0 및 2041-02 값-12 추가201. 같은 월409와 입력값 보존. 2건/평균-6·최신순 갱신 |
| 수정 준비/취소 | 월 잠금·기존값 채움. -99 입력 후 취소하면 저장 -12 유지 |
| 출력 안전 | img 형태 메모와 script 형태 질문을 문자로 표시. 해당 메시지/표에 실행 요소 없음 |
| 모의 채팅 전송 | Shift+Enter는 줄바꿈만, Enter 전송. 로딩 중 보내기·새대화·질문 입력 disabled 확인 |
| 모의 채팅 저장/복원 | fake-ai-no-network 답변 2회. 첫 문답 자동저장 후 새로고침 동일 복원, 두 번째 질문은 같은 대화ID 사용. 대화1건/메시지4개 |
| 실제 GPT | 이번 요청0회. 핵심 확인창 검증이 남아 추가 유료 호출하지 않음 |

### 미확인 및 도구 문제

기존 탭 바인딩/새로고침이 시간초과여서 문서화된 새 탭 방식을 사용했고 읽기·폼·채팅 검증은 진행됐습니다. `window.confirm`에는 정확한 2041-02, -12→-15 표시가 나타났습니다. 도구의 `getJsDialog().accept()`와 별도 접근성 OK 버튼 클릭 모두 시간초과가 재현됐습니다. 각 결과가 불명확한 경우 서버 요청 보고서를 확인했으며 PUT·DELETE는 발생하지 않았습니다. 같은 작업을 반복하거나 확인 절차를 건너뛰지 않았습니다.

따라서 수정·삭제 확정/확인창 취소, 대화 삭제의 최종 화면 결과는 미확인입니다. 서버중단·422·503 등의 실제 오류 화면도 남아 있습니다. 모의 채팅 성공은 실제 GPT 생성 성공이 아닙니다. 실제 GPT 화면 생성·저장·복원도 미완료입니다. 사용자가 수행할 안전한 격리 검수 절차를 별도로 작성했으며 실행 완료로 기록하지 않았습니다.

앱의 기능·CSS 결함은 확인하지 못했으므로 소스 변경 없음. 검증 중 공개 config의 포트만 8002→8011→8002로 임시 전환·복원했습니다. 기존 47개 프론트엔드/9개 도구 검사 통과 근거를 재사용했고 변경 없는 테스트를 반복하지 않았습니다.

### 격리 실행·정리·보존

실행 ID `ui-isolated-resume-20261029`, 포트8011, PID27112. 기존 `.venv` Python으로 `check_frontend.py --isolated-firestore`를 실행하고 stdin을 열어 두어 `stop`으로 정상 종료(종료코드0)했습니다. `finalized=true`, `cleanup.ok=true`.

- `changwon-net-2041-01`, `changwon-net-2041-02` 및 모의 대화 `62218dcd-2060-41c6-8a14-9caba41eb6b4`만 소유권 기록으로 삭제·부재 확인.
- 최초 `.local/frontend-original-before.json` 대비 data128건·기존 GPT/Gemini 대화2건의 전체 ID·typed payload·create_time·update_time 해시 일치.
- 실제 외부 AI 요청0. 기존 개인키/Gemini/Codyssey 시도·검증 기록 보존.
- 기존5500 PID31036,8002 PID9424,8000 PID1656 종료·재시작 없음. 8011만 정상 종료. 프론트 공개 주소8002로 복원 후 화면/health/docs/config HTTP200.
- UI 검증용 viewport override 해제. 키·설정 파일 내용 출력 없음. 패키지·모델·Firebase·운영 API 변경 없음.

### 증거 및 상태

- [.local/verification-13-14/browser-resume-results.json](.local/verification-13-14/browser-resume-results.json): 화면별 성공/미확인·실제AI0·원본 전체 비교·최종 HTTP 상태
- [.local/frontend-ui-isolated-resume-20261029-report.json](.local/frontend-ui-isolated-resume-20261029-report.json): 실제 격리 API 요청/모의AI2/정리/보존
- [.local/verification-13-14/desktop-1440.jpg](.local/verification-13-14/desktop-1440.jpg)
- [.local/verification-13-14/mobile-390-chat.jpg](.local/verification-13-14/mobile-390-chat.jpg)
- [.local/verification-13-14/mobile-390-data.jpg](.local/verification-13-14/mobile-390-data.jpg)
- [.local/verification-13-14/MANUAL_CHECK.md](.local/verification-13-14/MANUAL_CHECK.md): 격리 수정·삭제 확인창의 수동 검수 순서/기대 결과. 미실행 절차.

**13~14단계 전체 미완료 유지.** 이전10~12단계 완료는 보존. Render·Vercel 배포, GitHub 작업은 진행하지 않았습니다.

## 13~14단계 최종 추가 검증 — 2026-10-29

**최종 상태: 확인창 승인 3항목 수동 검수 대기.** 실제 GPT 화면 검증은 이번에 완료했지만 전체13~14단계는 미완료로 유지합니다. 아래는 앞선 기록에 추가한 결과이며, 지난 성공/실패 기록은 보존했습니다.

| 검증 계층 | 이번 결과 |
| --- | --- |
| 격리 Firestore API·DB | 기존 QAState/build_app/TestClient 재사용,13/13 통과. -12→-15 수정값·목록·평균(-6→-7.5) 일치. 데이터 삭제204·실제 부재·요약 갱신. 모의 대화 삭제204·목록0·상세404. 입력422·중복409·없는 데이터404 확인 |
| 실제 오류 화면 | 정수가 아닌1.5 입력 거절, 중복 월409 안내, 삭제된 격리 대화404 안내, 서버 종료 후 network_error 안내, 모의 GPT 오류502/openai_request_failed 안내·입력 보존·미저장 확인 |
| 실제 GPT 브라우저 | 질문→보내기→로딩/버튼·입력 잠금→답변→자동 저장→목록→새로고침 동일 복원→새 대화 후 이전 대화 선택 동일 복원 성공. 추가 호출 없음 |
| 브라우저 확인창 | 사전 dialog 이벤트 핸들러가 지원되지 않아 이전에 실패한 accept/OK 동작을 반복하지 않음. 자료 수정 승인·자료 삭제 승인·대화 삭제 승인은 실제 브라우저 미확인 |
| 소스/회귀 검사 | 앱·CSS 결함 발견 없음, 소스 수정 없음. 기존47개/9개 검사와 PC1440/모바일390 결과 재사용. 전체 테스트 재실행 없음 |

실제 질문: “저장된 최신 월을 기준으로 최근 창원시 순이동 추세를 간단히 설명해줘.” 기존 `check_frontend`의 `UI_QUESTION`을 이번 새 Python 프로세스에서만 지정하고 `main(["--live-openai", "--run-id", "ui-final-live-20261029", "--port", "8011"])`을 실행했습니다. 기존 OneAttemptAI의 별도 실행 파일과 max_retries=0,800토큰,45초 제한을 유지했습니다. 모델·키·Firebase 설정은 바꾸지 않았습니다.

- 실제 GPT 생성 **1회 성공**, `gpt-5.4-mini`, 입력711/출력221토큰. 기존 코디세이 Chat Completions 경로 사용.
- 시연 ID `4bc508f3-e079-40d6-9174-4157e5a5e79f`, `[화면 연결 검증]` 제목. `saved`, `demo_listed`, `demo_reload_matches` 모두true.
- 답변 대조: 최신2026-08/-813, 최근2025-09~2026-08/-558, 직전2024-09~2025-08/-551.42, 전체평균-643.75, 최댓값2021-06/430, 최솟값2025-02/-1756 모두 전달 요약 일치. 두 평균은 음수이고 최근 값은 더 낮으며, 답변은 순유출·전체 인구 증감 구분을 명시했습니다. 현재 달이나 원인·정책 효과로 단정하지 않았습니다.
- 격리 실행 `ui-final-api-20261029` 소유 자료2·모의 대화1, `ui-final-browser-20261029` 소유 자료1·모의 대화1 정리 완료. 보고서의 cleanup/finalized 모두true. 모의 AI 성공2회와 모의 오류 응답은 실제 GPT 호출 횟수에 포함하지 않습니다.
- 원본128건 보존 해시 `cb0a475784c06377a59baa6bd26680226e8d7e93160e69a4035271e70db1d994` 동일. 기존 대화2건 해시 `6200191907c88d8ee5c71b416bf96746aee27e31c2cca611a7b00faeb43771bb` 동일. ID·타입 포함 값·생성/수정시각 비교이며, 새 시연1건만 추가되어 현재 대화3건입니다.
- 검증용 서버는 정상 종료코드0. 공개 config는8002로 원문 복원, 실제 브라우저 강력 새로고침 후128건/대화3건 정상 표시. 기존5500 PID31036,8002 PID9424,8000 PID1656 유지. 화면/health/docs HTTP200,8011/8012/8013은 종료 상태. 최종 브라우저 콘솔 error0.

증거: [API13개](.local/verification-13-14/final-api-results.json), [브라우저 성공/미확인](.local/verification-13-14/final-browser-results.json), [격리 화면·정리](.local/frontend-ui-final-browser-20261029-report.json), [실제 GPT1회·저장·복원·보존](.local/frontend-ui-final-live-20261029-report.json), [최종 상태](.local/verification-13-14/final-results.json), [복원 캡처](.local/verification-13-14/final-gpt-restored.jpg), [남은 수동 절차](.local/verification-13-14/MANUAL_CHECK.md).

남은 차단 원인은 **확인창 자동화의 승인 처리 제한**입니다. API·DB 통과를 해당 브라우저 승인 통과로 대체하지 않았습니다. 수동 확인3항목의 결과를 받은 뒤 전체 완료 여부를 갱신합니다. 배포·GitHub 작업 없음.


## 13~14단계 UI/UX 통합 완료 — 2026-10-29

**완료 판정:** 기능 구현·격리 API/DB·실제 GPT 화면 검증의 기존 근거에, 사용자가 확인한 마지막 확인창3항목과 이번 UI 통합 회귀/실화면 검수를 합쳐13~14단계를 완료로 기록합니다. 사용자 수동 확인과 자동화 검증은 아래처럼 구분합니다.

| 근거 | 결과 |
| --- | --- |
| 사용자 직접 확인 | 2042-02 -12→-15 수정, 평균-6→-7.5 반영, 해당 기록 삭제 후2→1건, 모의 질문 삭제 후1→0건, 삭제 안내 정상 |
| 이번 에이전트 읽기 검사 | 동일 격리 실행의 PUT200·자료DELETE204·질문DELETE204 기록 확인. 잔여2042-01/0명·목록1·평균0·질문0 확인. 과거 -15/평균-7.5 화면은 사용자 확인 근거이며 자동 확인으로 바꾸지 않음 |
| 이번 UI 변경 | frontend/index.html·styles.css·app.js만 수정. 지정 Hero 문구/브랜드/아이콘 제거/질문 용어 통일. 실제 참고 디자인의 색상·폰트·평면 카드·작은 모서리 반영, 기존 레이아웃 유지 |
| 관련 회귀 | 기존 프론트엔드47개 모두 통과. HTML id·JS API 경로·이벤트 대상id 동일, api.js/config.js 해시 동일. 전체 백엔드263개는 반복하지 않음 |
| 실제 PC/모바일 | 1440×1000,390×844에서 Hero 줄바꿈·브랜드·질문 제목/입력·버튼 글자·간격 확인. 가로 넘침 없음. 모바일 수정/삭제44×44px. 이전 질문 목록 접기/펼치기·조회, 예시 입력·Shift+Enter, 새로고침 동일 복원. 콘솔error0 |
| AI 호출 | 이번0회. 실제 GPT 답변/저장/복원의 이전1회 성공 기록을 재사용. 모의 AI도 이번 UI 통합에서 추가 호출하지 않음 |
| 데이터 보존 | 원본data128·실제questions3(기존GPT/Gemini2+화면시연1)의 전체 값·create_time/update_time 해시 동일. 이름은 UI만 변경했고 실제 DB 컬렉션명conversations 유지 |
| 종료/범위 | 수동 격리 실행 정상 종료코드0, 소유 잔여 자료만 정리·부재 확인. 임시5501/8011 종료. 사용자5500/8002/8000 유지. 키·Firebase·모델·보안 설정 변경 없음. 배포/푸시/신규 기능 없음 |

참고 디자인은 `gajimaiso-changwon-starter/gajimaiso-changwon`의 index.html/styles.css/script.js와 참조 PNG3개를 읽기만 했고 해시가 동일합니다. 청록#087f75, ink#142d38, paper#f8f9f5, line#d6dfda, 시스템 폰트와 카드4~5px 모서리를 확인했습니다. 기존 통계 배열/모바일 전환은 이미 계승돼 유지했고, 참고 사이트에는 입력 폼이 없어 그 스타일을 추정하지 않았습니다.

증거 폴더: [.local/verification-13-14/ui-integration/](.local/verification-13-14/ui-integration/)
- DESIGN_REVIEW.md: 실제 파일 근거와 적용/유지 구분
- manual-confirmation.json: 사용자 확인 및 동일 실행의 서버 기록
- frontend-tests.json: 이번47/47
- browser-results.json: 이번PC/모바일·복원·콘솔 결과
- preservation.json: 원본128/실제질문3·참고 파일·API 설정 보존 및 격리 정리
- pc-1440-main.jpg, pc-1440-question.jpg, mobile-390-main.jpg, mobile-390-question.jpg, mobile-390-input.jpg, mobile-390-data.jpg: 최종 캡처

**13~14단계 완료.** 앞선 미완료 문단은 당시 결과로 보존하며 이 절이 최종 상태입니다. 다음 배포 단계는 시작하지 않았습니다. 공개 배포 전 인증/권한, 비밀 환경설정·CORS·프론트 주소, 키의 배포 사용 조건 및 실제 배포 후 검증은 후속 범위입니다.


## 15단계 시작 및 질문 화면 안내 영역 제거 — 2026-10-29

- 추가 UI 요청: QUESTION / 새 질문 / 안내 문구를 포함한 상단 블록과 관련 CSS·DOM 참조 제거. 질문 삭제 버튼은 이전 질문 목록 아래로 이동해 기능 유지. 입력창·답변·새 질문 버튼·저장 구조는 보존.
- 기존 문구 변경에 맞지 않던 프론트 테스트 기대값 2곳을 "이전 질문 목록"으로 정정. 관련 프론트 47개 통과. 전체 과거 테스트를 재실행한 기록이 아님.
- 인증·CORS·분당/동시 채팅 제한 신규 10개 및 관련 기존 데이터·채팅·코디세이 모의 HTTP 검사 포함 80개 통과. 실제 외부 AI 호출 0회, DB 쓰기 0회.
- 새 로컬 프로세스에서 /health·/docs·/openapi.json·data·summary 200, 무인증·오인증 401, 인증된 질문 목록 3건 확인. 원본 데이터 128건. 검증용 임시 서버만 종료. 실행 근거 `.local/verification-15/local-http.json`.
- 패키지 추가/업데이트 없이 pip check 통과. 기존 Python 3.12.10 명시, $PORT 사용, worker 1, 접근 로그 비활성화. render.yaml은 자동 배포 Off/Free.
- 초기 프로젝트에 Git 저장소·이력 없음. GitHub 사용자 소유 저장소 목록과 정확한 저장소명 조회에서 동일 저장소 없음 확인. 새 로컬 Git 초기화. 업로드 후보에서 실제 로컬 비밀값·대표 키 패턴 미검출, .env·키 TXT·.venv·.local 제외 확인. 커밋/원격 업로드 결과는 후속 기록으로 구분.
- 코디세이 외부 배포 허용: 사용자 확인 받음(공개 약관 독립 검증과 구분).
- 실제 Render 서비스·환경변수·공개 HTTPS 검증은 아직 미완료. 로그인 후 이어서 진행.


### 15단계 준비 결과 — 사용자 계정 연결 진행 중

- 비공개 원격 `jojunsu98/gajimaiso-ai-assistant` 생성 및 초기 커밋 `1c78ea2685f68071adea76c820611a06915b35f5` push 성공, 원격 main SHA 일치.
- 스테이징 파일 60개 및 전체 Git 이력 blob 60개 검사: 실제 설정 비밀값·대표 키 패턴 검출 0건. 기존 이력은 없었으며 다른 프로젝트 이력은 수정하지 않음.
- UI 실제 확인: 안내 블록 0개, 기존 질문 답변 표시·새로고침 동일 복원·새 질문 초기화·삭제 버튼 유지, 콘솔 오류 0건. `.local/verification-15/ui-result.json`, `question-pc-1482.jpg`. 뷰포트 요청은 적용되지 않아 이번 모바일 재검수는 미확인(과거 완료 검사와 구분).
- `.local/verification-15/preservation-after.json`: 데이터128건 및 기존 질문3건 목록 응답 해시 작업 전후 일치. 실제 DB 변경과 GPT 호출0회.
- Render 로그인 후 My Workspace에 기존 서비스0건 확인. GitHub 연결 승인 화면에서 사용자가 과제 저장소만 선택하여 승인하는 단계. 실제 서비스 생성·비밀값 설정·배포 URL 검증은 미실행이며 15단계는 미완료.


### Render 연결 후 실제 배포 확인 — 2026-10-29

- 사용자가 GitHub 연결을 완료한 뒤 이미 생성된 Free/Singapore 서비스 `srv-dbhdk7afngtc73bck570`을 발견하여 재사용했습니다. 중복 서비스를 생성하지 않았습니다.
- 공개 백엔드 https://gajimaiso-ai-assistant.onrender.com 및 Swagger https://gajimaiso-ai-assistant.onrender.com/docs 확인. health/docs/openapi HTTP200, 실제 Swagger 제목·Authorize·보호 경로 보안 표시 확인.
- 초기 data/summary는 503 `database_unavailable`, 보호 요청은 403 `access_not_configured`: 비밀값 미설정 상태를 안전하게 차단하며 연결 성공으로 표시하지 않음.
- 실제 서비스의 자동 배포를 Off로 변경하고 시작 명령에 `--workers 1 --no-access-log`, 헬스체크 `/health` 설정. 공개 환경변수9개 저장 후 재빌드 `dep-dbhdmlafngtc73bcq80g` Live 확인. 배포 로그에서 해당 시작 명령 확인.
- 로컬 `.env` 기존 바이트를 보존하고 접근 인증 전용 APP_ACCESS_TOKEN을 추가 준비. Render의 서비스 계정 JSON·코디세이 키·같은 접근 토큰은 사용자 직접 입력 대기. 실제 키 값을 출력·커밋하지 않음.
- 이번 연결 후 작업의 실제 AI 호출0회, 실제 DB 쓰기0회. 사용자 로컬 서버 종료·재시작 없음. 전체 테스트 반복 실행 없음. 기존 원본 보존 결과 유지.
- 근거: `.local/verification-15/render-public-check.json`, `render-swagger.jpg`, `render-secret-form.jpg`, `access-token-setup.json`. 공개 URL의 서버 실행과 외부 서비스 연결 완료는 구분하며 15단계 미완료 유지. 16단계는 시작하지 않음.

## 15단계 — 사용자 환경설정 완료 안내 후 재검사 (2026-10-29)

- 새 배포 `dep-dbhdt86c6qcc73f5eirg` / 소스 `b83e8d8`: Render Live 확인.
- HTTPS health/docs/openapi: HTTP 200. data/summary: 503 `database_unavailable`. 로컬 접근 토큰을 보낸 대화 목록: 403 `access_not_configured`.
- 보호 API 8개에 무인증·잘못된 인증으로 보낸 16개 요청 모두 403 차단 확인. 쓰기 요청은 빈 본문·존재하지 않는 시험용 ID를 사용했으며 GPT 생성·DB 변경은 발생하지 않았습니다.
- 별도로 연 Render 읽기 화면에서 실제 저장값을 비출력 방식으로 검사: Firebase JSON·코디세이 키·APP_ACCESS_TOKEN 모두 빈 값. 사용자에게 실제 value 입력 후 저장·재배포를 안내하고 편집 화면 준비.
- 이번 확인의 GPT 생성 0회, DB 쓰기 0회. 기존 로컬 서버에 대한 읽기 요청으로 data 128건 및 대화 목록 3건의 응답 해시가 배포 전과 일치함을 확인. 기존 서버 재시작·종료 없음.
- 코드 변경 없음. 앞서 통과한 테스트는 반복하지 않음. Render 인증 성공·Firestore 조회·GPT 검증은 설정 대기이며 15단계 미완료 유지.
- 근거: `.local/verification-15/render-post-secrets-preflight.json`, `preservation-post-secret-handoff.json`, `render-empty-secret-fields-confirmed.jpg`.

## 15단계 — 저장된 환경변수 적용 재검사 (2026-10-29 21:40~21:43 KST)

- 새 배포 `dep-dbhjpum1egvs73foiuf0` / 소스 `075ba79010ff57ca662e8ff24ece9e537dcd4c04`: Render `Deploy succeeded | Live`. 대시보드 배포 시각 21:32:58, 실제 기동 완료 로그 21:33:58. worker 1·접근 로그 비활성화 시작 명령 확인.
- 저장값은 비공개로 검사했습니다. Firebase JSON은 서비스 계정 JSON 형식이며 실제 자료·요약 조회 모두 200입니다. 원본 128건, 2016-01~2026-08, 기존 자료 응답 해시 일치. 이전의 빈 값/503 상태는 해소됐습니다.
- `APP_ACCESS_TOKEN`은 값이 있고 ASCII 32자 이상이지만 앞뒤 공백/줄바꿈이 있습니다. 내부 공백은 없으며 앞뒤 공백을 제거하면 형식 조건을 충족합니다. 무인증·로컬 토큰 인증 요청 모두 403 `access_not_configured`로, 서버 설정 부적합 상태입니다. 토큰 값은 출력하지 않았고 변경하지 않았습니다.
- `OPENAI_API_KEY`는 저장돼 있고 공백·변수명 접두사는 없습니다. 보호 API 사전 검사에서 중단했으므로 실제 AI 인증·생성은 아직 미검증입니다. GPT POST 0회, DB 쓰기 0회. 기존 질문 3건의 원격 조회·상세 보존 검증도 인증 복구 후 진행합니다.
- health/docs/openapi 200 및 실제 Swagger 보호 경로 표시 확인. CORS 허용 origin은 200/Authorization 허용, 비허용 origin은 400/allow-origin 없음.
- 이번 검증 스크립트 종료코드 1은 접근 토큰 설정 미통과를 나타냅니다. 기존 전체 테스트·로컬 서버 시작/종료·GitHub 업로드·Render 설정 변경은 하지 않았습니다. 원격 설정 편집 화면은 취소했고 비밀값은 모두 다시 숨겼습니다.
- 근거: `.local/verification-15/render-resume-20261029T124024584167Z-9a0888d9-report.json`, `render-resume-20261029T124243495373Z-84f07743-diagnostics.json`, `render-resume-environment-state.json`.
- 다음 단계: 사용자가 Render `APP_ACCESS_TOKEN` 앞뒤 공백/줄바꿈만 제거하고 저장·재배포한 뒤, 인증 401/200·기존 질문 보존·승인된 GPT 최대 1회와 저장/복원을 검증합니다. 15단계 미완료이며 16단계는 시작하지 않았습니다.

## 15단계 최종 검증 완료 — 2026-10-29 21:54 KST

사용자가 접근 토큰 앞뒤 줄바꿈을 수정하고 Save, rebuild, and deploy 및 Live를 확인한 후, 남은 실제 Render API 검증만 수행했습니다. 이전 실패 기록은 당시 상태로 보존합니다.

| 검증 항목 | 이번 실제 결과 |
| --- | --- |
| 접근 인증 | 로컬 기존 토큰으로 원격 대화 목록·상세 HTTP 200. 무인증·잘못된 토큰은 각각 401 access_denied |
| Firebase 자료·요약 | 모두 HTTP 200. 128건, 2016-01~2026-08. 기존 배포 전 자료·질문 목록 응답 해시와 일치 |
| 코디세이 GPT | POST /api/chat 정확히 1회, HTTP 200. gpt-5.4-mini, 입력 716 / 출력 160토큰. 자동 재시도 0회 |
| 답변 내용 | 최신 2026-08/-813명, 최근 12개월 평균 -558명, 직전 -551.42명 및 기간이 서버 요약과 일치. 순유출·전체 인구 증감의 구분과 원인/정책효과 해석 한계 명시 |
| 자동 저장·복원 | saved=true. 새 질문이 목록에 정확히 1회 표시. 상세의 질문·답변·요약·모델·사용량이 생성 응답과 일치 |
| 기존 자료 보존 | 원본 128건·요약·기존 질문 3건 목록과 전체 상세(생성/수정시각 포함)의 검증 전후 해시 일치 |
| 추가 기록 | 검증 질문 1건만 추가, 현재 질문 총 4건. 기존 기록 수정·삭제 없음 |
| 실행 결과 | 검증 스크립트 종료코드 0. 비밀값 출력 없음. GPT 재호출 방지 marker 유지 |

검증 질문 ID: `34766710-ca74-465f-b0e0-f92fbc58e8d2`, 제목 접두사 `[Render 연결 검증]`.

실행 근거:

- [최종 검증 결과](.local/verification-15/render-resume-20261029T125347566349Z-54c196ba-report.json)
- [GPT 답변과 대조 요약](.local/verification-15/render-resume-20261029T125347566349Z-54c196ba-reply.json)
- [검증 전 자료·질문](.local/verification-15/render-resume-20261029T125347566349Z-54c196ba-before.json)
- [검증 후 자료·질문](.local/verification-15/render-resume-20261029T125347566349Z-54c196ba-after.json)

기존 health/docs/OpenAPI·실제 Swagger·CORS 및 오프라인 테스트 통과 근거는 이전 실행에서 상속했으며 이번에 반복하지 않았습니다. 새로운 배포 ID·대시보드 Live 확인은 이번 자동 검증에 포함하지 않았고 사용자 확인과 구분합니다. 환경변수·앱 소스·로컬 서버·배포 설정 변경, 커밋·푸시는 수행하지 않았습니다.

**15단계 완료. 16단계 및 프론트 배포/인증 연동으로 자동 진행하지 않고 여기서 종료합니다.**

## 16단계 Vercel 프론트 배포 — 진행 중 (2026-10-29)

- 운영 URL: https://gajimaiso-ai-assistant.vercel.app
- Vercel 프로젝트 `prj_NW1ATS6Jm07fhPH0gAR50fwtAN2d`, production 배포 `dpl_6JoehLe9QE1S2FYRAchGBaUdC4eH` READY. 기존 프로젝트 검색 결과 없음 확인 후 생성했습니다.
- GitHub 배포 커밋 `e715972274f17ea37c47a7e54d2ee2b921c21f86`: 비공개 기존 저장소의 main에 필요한 7개 파일만 업로드. 저장소 공개 범위 변경 없음.
- Framework Other(null), Root frontend, Build node build.mjs, Output dist, 별도 의존성 설치 없음. API_BASE_URL 공개 설정을 빌드에서 config.js로 생성하며 기본/허용 주소는 기존 Render HTTPS origin입니다. 정적 브라우저가 서버 환경변수를 읽는 방식이 아닙니다.
- 배포 파일은 index.html/styles.css/app.js/api.js/config.js 5개뿐입니다. 서비스 계정·GPT 키·접근 토큰·로컬 검증 파일은 포함하지 않습니다. 미추적 backend/backend.env도 명시적으로 Git에서 제외했습니다.
- 접근 토큰은 사용자가 password 입력란에 입력하며 현재 탭의 함수 메모리에만 유지합니다. 연결 시 입력란을 비우고, 연결 해제·새로고침 시 다시 입력해야 합니다. URL·로그·오류·localStorage·sessionStorage·공개 환경변수에 저장하지 않습니다. HTTPS Authorization 헤더로 보호 요청에만 전송하며 리디렉션을 거부합니다.
- **인증 한계:** 이 토큰은 공유된 단일 관리 권한입니다. 공개 다중 사용자 로그인·사용자별 권한·개별 기록 격리가 아니며, 토큰을 가진 사람은 같은 질문 기록과 자료 변경 기능에 접근합니다. 불특정 사용자에게 배포하지 말아야 합니다. 공개 자료 조회와 보호 기능 접근은 구분됩니다.
- Render ALLOWED_ORIGINS에는 기존 로컬 출처 2개를 보존하고 정확히 https://gajimaiso-ai-assistant.vercel.app 하나만 추가했습니다. 와일드카드와 임의 Preview 도메인은 허용하지 않았습니다.
- 이번 관련 검증: 빌드 5파일·JS 모듈 구문·신규 인증 전달 4항목 통과. 실제 운영 파일 모두200/비밀값 미검출, Render 자료·요약·질문 목록200, 기존 128건/질문4건 전체 상세 보존, 무인증·오인증401, CORS 운영출처200/미허용출처400. GPT 생성0회·DB 쓰기0회. 이전 전체 테스트는 반복하지 않았습니다.
- 남은 필수 검증: Chrome 확장프로그램 UI가 자동화를 차단해 사용자의 닫기 및 토큰 입력 대기. 실제 PC·모바일 레이아웃·기존 질문 UI 불러오기·최종 콘솔 검증은 아직 완료로 표시하지 않습니다.
- 근거: `.local/verification-15/stage16-read-verification.json`. 17단계 종합 테스트는 시작하지 않았습니다.
