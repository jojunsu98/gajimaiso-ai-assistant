# 가지마이소창원 AI 비서

**15단계 진행 중:** Render HTTPS 서버·Swagger 200 확인. 2026-10-29 사용자 설정 완료 안내 후 재검사했지만 Render에 저장된 Firebase JSON·코디세이 키·접근 토큰 값이 모두 비어 있었습니다. 데이터 조회 503, 보호 API 403으로 안전하게 차단되며 실제 배포 GPT 호출은 0회입니다. 비밀 환경변수 입력과 인증된 연결 검증이 남아 미완료입니다. [Render 배포 설정과 인증 인터페이스](DEPLOY_RENDER.md)를 참고하세요.

현재 과제는 **코디세이 중계 서버를 통한 OpenAI GPT 호출**을 사용합니다. 데이터 CRUD·요약, Chat Completions 기반 채팅, 대화 저장·목록·불러오기·삭제 API를 제공합니다.
초기 오프라인 테스트 263개와 실제 Firestore+모의 AI의 격리 검증은 통과했습니다.
**10~12단계 완료** — 2026-10-29 코디세이 경로의 실제 GPT 답변·내용 대조·자동 저장·목록·상세 복원을 확인했습니다.
`AI_PROVIDER=openai`, `OPENAI_MODEL=gpt-5.4-mini`를 유지하며 Gemini 자동 전환은 없습니다.
이전 개인 키의 사용 한도 오류와 Gemini 성공 기록은 별도 보존했습니다. 개인 키의 잔액 상태를 코디세이 키에 적용하지 않습니다.
최신 실행은 `codyssey-chat-20261029-01`이며 이번 승인으로 실제 Chat Completions 요청 **1회 성공**했습니다. 이전 직접 호출의 인증 실패 기록도 보존했습니다.
`GET /health`는 서버 자체의 응답만 확인하며 Firebase나 AI 연결 성공을 뜻하지 않습니다.

**13~14단계 완료 — 2026-10-29.** 기존 실제 GPT 화면·저장·복원 성공에 더해 사용자가 격리 화면의 수정·자료 삭제·질문 삭제 확인창을 검수했습니다. 확정 문구와 브랜드 통합 후 PC1440px·모바일390px 및 관련 프론트엔드47개 검사도 통과했습니다. 이번 UI 통합의 추가 GPT 호출은0회입니다. 상세 근거는 마지막 “13~14단계 UI/UX 통합 완료” 절에 기록했으며 아래 이전 미완료 기록은 당시 이력으로 보존합니다.

## 현재 환경과 구조

- Python 3.12.10 (요구 조건: Python 3.10 이상)
- 가상환경: 프로젝트 루트의 `.venv`
- 패키지: `backend/requirements.txt`에 실제 설치 버전 고정
- `backend/app/main.py`: FastAPI 앱 초기화와 라우터 등록
- `backend/app/routers/health.py`: 서버 응답 확인 라우터
- `backend/app/config.py`: 고정 경로 환경설정 로딩과 자격증명 검증
- `backend/app/services/firestore.py`: 필요한 때만 초기화하는 Firestore 연결
- `backend/scripts/check_firestore.py`: 명시적 옵션으로 실행하는 연결 검사
- `backend/scripts/import_migration.py`: CSV 전체 검증, 가져오기·저장 결과 대조 CLI
- `backend/app/services/migration_import.py`: 충돌 사전 검사와 생성 전용 묶음 저장
- `backend/app/routers/data.py`: 데이터 CRUD 4개와 summary API
- `backend/app/services/data.py`: Firestore CRUD·저장 데이터 무결성 검사
- `backend/app/services/summary.py`: DB·CSV와 분리된 통계 계산
- `backend/app/schemas/data.py`, `summary.py`: 엄격한 입력·응답 모델
- `backend/scripts/check_data_api.py`: 명시적 `--live`로 격리된 실제 API 검사
- `backend/app/routers/chat.py`, `conversations.py`: 채팅·대화 기록 API
- `backend/app/services/chat.py`, `openai_client.py`, `conversations.py`: 요약 주입·단일 AI 호출·조건부 대화 저장
- `backend/app/schemas/chat.py`, `conversations.py`: 입력 제한과 서버 메타데이터 응답
- `backend/scripts/check_chat.py`: 실제 Firestore+모의 AI와 별도 실제 OpenAI 검사
- `backend/data/source/`: 실제로 확인한 원본 CSV의 동일한 복사본
- `backend/tests/test_migration.py`: CSV 검증과 모의 저장·CLI 테스트
- `frontend/`: HTML/CSS/JavaScript 웹 화면, 공개 FastAPI 주소 설정과 공통 요청 함수

## Windows PowerShell에서 실행

아래 명령은 **프로젝트 루트**에서 실행합니다. `.venv` 활성화나 실행 정책 변경은 필요하지 않습니다.
이번 작업에서 가상환경 생성과 패키지 설치를 마쳤으므로 바로 실행할 수 있습니다.

```powershell
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

`Uvicorn running on http://127.0.0.1:8000` 메시지가 나오면 서버가 실행 중입니다.
명령을 실행한 PowerShell 창을 유지하고, 종료할 때는 그 창에서 `Ctrl+C`를 누릅니다.
이전 1~4단계의 검증용 서버는 종료했습니다. 사용자가 이미 실행 중인 서버는 그대로 유지하세요.
서버가 실행 중이지 않을 때만 위 명령으로 실행합니다.

- Swagger UI: <http://127.0.0.1:8000/docs>
- 서버 응답 확인: <http://127.0.0.1:8000/health>
- OpenAPI 문서: <http://127.0.0.1:8000/openapi.json>

`/docs`에서 `GET /health`를 펼치고 `Try it out` → `Execute`를 누르면
응답 코드 `200`과 `{"status":"ok"}`를 확인할 수 있습니다.

HTTP 응답만 확인하려면 **다른 PowerShell 창**에서 실행합니다.

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health'
```

8000번 포트 사용 중이라는 오류가 나오면 기존 프로세스를 종료하지 않고, 같은 프로젝트 루트에서
8001번 등 비어 있는 포트를 사용합니다.

```powershell
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001
```

8001번을 사용했다면 Swagger 주소도 `http://127.0.0.1:8001/docs`로 바뀝니다.

## 현재 가상환경의 의존성을 다시 설치해야 할 때

프로젝트 루트에서 아래 명령을 실행합니다. 패키지는 `.venv`에 설치됩니다.

```powershell
& '.\.venv\Scripts\python.exe' -m pip --isolated --disable-pip-version-check install --no-cache-dir -r '.\backend\requirements.txt'
```

`/health`와 `/docs` 실행에는 API 키나 서비스 계정 키가 필요하지 않습니다.
실행 검증과 브라우저 확인 근거는 [PROGRESS.md](PROGRESS.md)에 기록했습니다.

## Firestore 연결 준비와 검사

현재 상태는 **5단계 연결 준비 및 6단계 실제 연결 검증 완료**입니다.
2026-10-28에 명령줄 `--live` 검사 한 차례가 종료 코드 0으로 통과했습니다.
자세한 확인 근거는 [PROGRESS.md](PROGRESS.md)의 최신 기록에 있습니다.
공개 HTTP 연결 테스트 엔드포인트는 없습니다. 기존 서버를 종료하거나 재시작하지 않고
별도 PowerShell에서 아래 CLI를 실행할 수 있습니다.

사용자가 Firebase 콘솔에서 이번 과제용 프로젝트와 기본 `(default)` Firestore 데이터베이스를
준비하고 서비스 계정 키를 발급합니다. 키 파일은 **프로젝트와 OneDrive 밖**에 보관하세요.
키 내용을 채팅이나 소스에 붙여넣지 말고 `backend/.env`에 설정합니다.
기존 값이 있다면 유지하고 필요한 항목만 수정하세요. 항목별 설명은
[backend/.env.example](backend/.env.example)에 있습니다.

| 변수 | 설정 |
| --- | --- |
| `FIREBASE_PROJECT_ID` | 이번 과제용 Firebase 프로젝트의 실제 ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | 로컬 키 파일의 절대 경로 |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 배포 환경에서 사용할 수 있도록 구현한 JSON 문자열 설정. 로컬 파일 방식에서는 비워 둠 |

환경설정은 터미널 위치와 관계없이 `backend/.env`에서 읽습니다. 실제 프로세스 환경변수가
`.env`보다 우선하며 빈 값도 우선합니다. JSON 문자열이 비어 있지 않으면 파일 경로보다
우선하고, JSON 오류 시 파일이나 다른 자격증명으로 우회하지 않습니다. 이 JSON 변수는
SDK 자동 설정이 아니라 앱에서 직접 파싱합니다. 키의 `project_id`가 설정과 다르면 중단합니다.

연결 객체는 프로세스에서 최초 요청 시 초기화하고 재사용합니다. 초기화 후 설정은 해당
프로세스 수명 동안 고정됩니다. 다른 자격증명으로 초기화된 동일 이름의 앱을 임의로 채택하지 않습니다.
CLI는 실행할 때마다 새 프로세스이므로 수정한 설정을 새 검사에 적용할 수 있습니다.

프로젝트 루트에서 **외부 접속 없는 설정 검사**:

```powershell
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\check_firestore.py'
```

설정이 없으면 한 번 안내하고 종료합니다. 설정 검사 성공도 실제 연결 성공을 의미하지 않습니다.
키와 프로젝트·데이터베이스 준비를 마친 뒤 **실제 검사 1회**:

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\check_firestore.py' --live
```

`FIRESTORE_EMULATOR_HOST`가 설정돼 있으면 클라우드 검사와 혼동하지 않도록 중단합니다.
실제 검사는 `_connection_checks`에 무작위 ID 문서 1개를 생성하고 값 조회·일치를 확인한 뒤,
이번 실행의 소유 마커와 갱신 시각이 일치하는 문서만 삭제하고 삭제 결과를 조회합니다.
중간 실패에도 정리를 시도하며 기존 문서 충돌 시에는 삭제하지 않습니다.
정리를 확인하지 못하면 문서 경로와 정리 실패를 별도로 알립니다.
각 Firestore 요청은 5초 제한이고 자동 재시도는 없습니다.
검사 프로세스는 35초, 비정상 종료 후 한 차례 시도하는 정리는 20초로 제한합니다.
Windows 실행기와 실제 작업 프로세스가 함께 종료됐는지 확인한 뒤에만 후속 정리를 실행합니다.
종료 명령·회수 대기까지 포함한 설정상 최대 대기 합계는 약 75초입니다(프로세스 생성·OS 지연 제외).
프로세스 종료를 확인하지 못하면 추가 작업을 시작하지 않고 PID와 정리 미확인 상태를 알립니다.

종료 코드: `0` 성공(기본 실행은 로컬 설정 검사만), `1` 실제 검사 실패,
`2` 설정 필요 또는 실행 조건 불충족, `3` 테스트 문서 정리 실패·미확인.

컬렉션 목적은 `data`: 창원 인구이동 데이터, `conversations`: 대화 기록입니다.
5~6단계에서는 두 컬렉션에 데이터를 넣지 않았고, 7단계에서 `data`에 아래 월별 자료를 저장했습니다.
`conversations`에는 아직 데이터를 넣지 않았습니다.

키 없이 모의 테스트를 다시 실행하려면 프로젝트 루트에서 다음 명령을 사용합니다.
실제 Firebase 키와 네트워크는 사용하지 않으며 새 테스트 패키지는 필요하지 않습니다.

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s backend/tests -t backend -v
```

## 7단계 — 창원시 월별 순이동 CSV 가져오기

2026-10-28 검증 결과: **2016-01~2026-08의 128개월**, 신규 생성 128건, 충돌 0건,
저장 후 128건 전체 일치. 동일 파일 재실행은 신규 생성 0건·동일하여 건너뜀 128건입니다.
기존 연결 서비스와 기본 `(default)` 데이터베이스를 사용합니다.

### 실제 원본과 해석

원본 경로:
`C:\Users\user\OneDrive\바탕 화면\gajimaiso-changwon-starter\gajimaiso-changwon\data\changwon_migration_monthly_clean.csv`

보관 복사본: [backend/data/source/changwon_migration_monthly_clean.csv](backend/data/source/changwon_migration_monthly_clean.csv).
원본의 전입·전출 등 모든 열을 포함한 9,921바이트를 그대로 복사했습니다. 원본은 수정하지 않았습니다.
원본과 복사본의 SHA-256은 모두 다음과 같습니다.

```text
e9c97c21f17695520431434b2e7c587babe2caf4ba62c1d83153329c10570475
```

인코딩은 UTF-8 BOM(`utf-8-sig`), 구분자는 쉼표입니다. 실제 13개 열은 다음과 같습니다.

```text
month, region_code, region_name, total_inflow, total_outflow, net_migration,
within_city_movement, within_province_inflow, within_province_outflow,
interprovince_inflow, interprovince_outflow, external_inflow, external_outflow
```

전체 128행이 `region_code=48120`, `region_name=창원시`인 한 시계열입니다.
날짜 중복·누락 월·빈 값·비수치·NaN·무한대·소수 부분이 있는 인원수는 0건이며,
각 행의 `total_inflow - total_outflow = net_migration`도 일치합니다.
전체 기간을 사용하며 하위 지역을 합산하거나 전입·전출을 추가 데이터 포인트로 세지 않습니다.

출처는 **기존 프로젝트 README·정제 코드에서 확인한 기록**입니다.
KOSIS 국내인구이동통계 「시군구별 이동자수」, 표 ID `DT_1B26001_A01`, 단위 명으로 기록돼 있습니다.
기존 README에 기록된 [통계표 주소](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1B26001_A01)와
메타자료 표시 시각은 2026-10-15 17:42입니다. 이번에 통계표를 새로 내려받거나 최신성·개정 여부를 확인하지는 않았습니다.
기존 원자료 `data/raw/migration_raw.csv`의 지역 `48120`·항목 `T25` 추출값도 128개월 모두 이 CSV와 일치했습니다.

순이동은 전입에서 전출을 뺀 값이며, 출생·사망을 포함한 전체 인구 증감이 아닙니다.
연령·이동 사유·개인별 재전출 등 이 파일에 없는 내용은 설명할 수 없습니다.

### Firestore 변환 기준

| 원본·기준 | 저장 위치·값 |
| --- | --- |
| `month` (`YYYY-MM`) | `data/changwon-net-YYYY-MM`의 고정 문서 ID |
| `month` | `date`: `YYYY-MM-01` 문자열 |
| `net_migration` | `value`: 정수, 단위 명. 음수와 0도 유효 |
| 고정 설명 | `memo`: `창원시 월별 순이동자수(명)` |
| `region_code`, `region_name` | 창원시 전체 자료인지 검증하는 데 사용 |

**date의 `01`은 월별 자료를 저장하기 위한 대표일이며 실제 1일 하루치 관측값이 아닙니다.**
소수 부분이 있는 인원수는 반올림하지 않고 거부합니다. 전입·전출 등 나머지 원본 열은 복사본에 보존합니다.

### 실행 위치와 명령

다음 명령은 별도 PowerShell의 **프로젝트 루트**에서 실행합니다. 실행 중인 8000번 서버는 그대로 둡니다.
기본 CSV 경로는 스크립트 위치를 기준으로 위 보관 복사본을 가리킵니다.

```powershell
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'

# 기본 실행 또는 --dry-run: CSV 검증만 수행, Firebase 설정·키 로딩과 DB 접속 없음
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\import_migration.py' --dry-run

# 전체 검증·충돌 검사 후 신규 문서만 생성
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\import_migration.py' --apply

# 저장된 대상 전체를 읽어 CSV 변환 결과와 비교, 쓰기 없음
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\import_migration.py' --verify
```

`--source 'CSV 전체 경로'`로 확인된 다른 파일을 지정할 수 있습니다.
결과는 `.local/migration-모드.json`에 기록하며, 같은 기본 명령을 재실행하면 해당 결과 파일이 갱신됩니다.
`--report migration-check-2.json`처럼 파일명을 지정하면 결과를 따로 남길 수 있습니다.
종료 코드 `0`은 해당 모드의 성공, `2`는 입력·설정 문제, `1`은 저장·대조·네트워크 실패입니다.
dry-run 성공은 실제 저장 성공을 의미하지 않습니다.

전체 입력을 검증한 후 `data`를 한 번 조회해 충돌을 검사합니다. 조회 상한 10,000건을 넘으면
일부만 검사하고 쓰지 않고 중단합니다. 같은 ID의 `date/value/memo` 타입·값이 같으면 건너뛰며,
같은 ID의 다른 내용이나 다른 ID의 같은 월은 충돌로 중단합니다. 기존 추가 필드는 보존합니다.
신규 문서만 최대 400건씩 `create`로 저장하며 수정·삭제 기능은 없습니다.
Firestore RPC는 요청별 10초, 자동 재시도 없음으로 설정했습니다.
실패하면 확정 생성·미완료·생성 여부가 불확실한 항목을 나누어 보고하며 자동으로 재입력하지 않습니다.
다른 프로그램이 사전 검사 이후 다른 ID로 같은 월을 넣는 동시 작업까지 막는 구조는 아니므로
가져오기를 동시에 실행하지 않습니다.

실제 실행 명령·증거와 오프라인 테스트 73개 통과 기록은 [PROGRESS.md](PROGRESS.md)에 있습니다.
7단계 당시에는 데이터 CRUD·summary API를 구현하지 않았습니다. 아래 8~9단계에서 추가했습니다.
이후 OpenAI 호출 코드·대화 저장은 아래 10~12단계에서 추가했습니다. 프론트엔드와 배포는 아직 구현하지 않았습니다.

## 8~9단계 — 데이터 CRUD 및 저장값 기반 요약

현재 API는 기본 `(default)` DB의 `data` 컬렉션을 사용합니다. 공개 배포하지 않았으며
로컬 `127.0.0.1`에서 검증했습니다. 기존 8000번 서버는 자동 재시작하지 않았습니다.

| API | 성공 코드 | 동작 |
| --- | --- | --- |
| `POST /api/data` | 201 | 날짜로 고정 ID를 만들고 신규 문서 생성. 같은 월은 409 |
| `GET /api/data` | 200 | 날짜 오름차순 `{items, count}` 전체 목록 |
| `PUT /api/data/{id}` | 200 | 같은 월의 date/value/memo 전체 수정. 월 변경 422, 없는 문서 404 |
| `DELETE /api/data/{id}` | 204 | 존재하는 문서 1개 삭제. 본문 없음, 없는 문서 404 |
| `GET /api/data/summary` | 200 | 현재 저장 자료를 한 번 읽어 서버에서 요약 |

POST·PUT은 `date`, `value`, `memo` 모두 필수이며 추가 필드는 거부합니다.
`date`는 실제 유효한 `YYYY-MM-01` 문자열, `value`는 −2⁶³~2⁶³−1 범위의 정수입니다.
음수·0은 허용하지만 문자열 숫자·불리언·소수·NaN·무한대는 거부합니다.
`memo`는 빈 문자열을 허용하는 최대 500자 문자열입니다. 잘못된 입력은 422입니다.
DB 연결·설정 문제는 503, 저장 데이터 무결성 또는 예상하지 못한 오류는 500으로 반환하며
비밀값·내부 예외·입력 원문을 오류 응답에 넣지 않습니다.

저장 문서의 누락 필드·추가 필드·잘못된 타입·ID와 월 불일치는 조용히 제외하거나 보정하지 않습니다.
생성은 `create`, 수정·삭제는 마지막 수정 시각의 전제조건을 사용합니다. 동시 변경 충돌은 409입니다.
동기 Firestore 작업은 일반 `def` 라우터에서 처리하고, 각 RPC는 10초·자동 재시도 없음입니다.
초기 자료의 최소 100개 기준은 CRUD·summary에는 적용하지 않습니다.

### 요약과 해석

summary는 `metric/unit/frequency`, 기간·개수, 합계·평균·최댓값·최솟값·모든 극값 월,
최신 월, 최근 추세, 전체 기간의 누락 월, 해석상 제한을 반환합니다.
평균·차이는 표시할 때 소수점 둘째 자리까지 반올림하고, 추세 방향은 반올림 전 정확한 값으로 판정합니다.

최신 **저장 월**을 포함한 최근 12개월 평균에서 그 직전 12개월 평균을 뺍니다.
증가·감소·동일은 순이동 수치의 방향입니다. 최신 24개월 중 자료가 부족하거나 누락된 월이 있으면
`insufficient_data`와 null 비교값을 반환합니다. 최근 24개 행으로 대체하거나 0으로 채우지 않습니다.
그보다 오래된 누락은 전체 품질 목록에 표시하되 완전한 최근 비교 구간을 무효화하지 않습니다.
빈 데이터는 200, count=0, total=0, period/latest/average/max/min은 null이며 가짜 추세를 만들지 않습니다.

2026-10-28 실제 저장값과 CSV 독립 집계의 대조 결과:

| 항목 | 값 |
| --- | --- |
| 기간·개수 | 2016-01~2026-08, 128개월 |
| 합계·월평균 | −82,400명 / −643.75명 |
| 최댓값·월 | 430명 / 2021-06 |
| 최솟값·월 | −1,756명 / 2025-02 |
| 최근 12개월 | 2025-09~2026-08, 평균 −558.00명 |
| 직전 12개월 | 2024-09~2025-08, 평균 −551.42명 |
| 평균 차이·방향 | −6.58명, 순이동 수치 하락 |
| 누락 월 | 없음 |

이 수치는 검증 당시 저장값의 결과입니다. CRUD 이후에는 현재 저장값으로 다시 계산합니다.
순이동은 전입·전출 차이로 전체 인구 증감과 같지 않고, 최신 저장 월은 현재 달 실적이 아닙니다.
이 자료만으로 이동 원인·정책 효과를 확정할 수 없습니다. 음수의 상승은 순유출 규모 감소일 수 있으며
순유입 전환과 다릅니다. 사용자가 수정한 저장값은 원본 공식 통계와 달라질 수 있습니다.

### CORS와 로컬 확인

`ALLOWED_ORIGINS`는 쉼표로 구분하며 기본값은 `http://localhost:5500,http://127.0.0.1:5500`입니다.
`backend/.env`의 설정을 읽되 실제 프로세스 환경변수가 우선합니다. 명시적인 빈 값은 허용 출처를 비웁니다.
실제 `.env`의 기존 값은 변경하지 않았고 `.env.example`에 공개 가능한 예시만 추가했습니다.
CORS는 사용자 인증이 아니므로 공개 배포 전 쓰기 권한 보호가 필요합니다. 로그인은 아직 구현하지 않았습니다.

사용자 확인은 기존 8000번 서버를 유지한 채 **별도 PowerShell**에서 다음 명령으로 할 수 있습니다.
8001번은 이번 검증 후 종료하여 비워 두었습니다. 다른 프로세스가 이후 사용 중이면 다른 빈 포트를 사용하세요.

```powershell
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001
```

확인 주소: **http://127.0.0.1:8001/docs**.
기존 8000번 서버에 새 기능을 반영하려면 사용자가 그 서버 터미널에서 `Ctrl+C` 후
위 실행 명령의 포트를 `8000`으로 바꿔 재시작해야 합니다. 에이전트는 8000번 서버를 조작하지 않았습니다.
Swagger에서 POST·PUT·DELETE를 실행하면 실제 `data`가 변경됩니다. 원본을 보호하는 실제 쓰기 검사는
아래 격리 검사 도구를 사용합니다.

### 검사 명령과 범위

프로젝트 루트에서 외부 접속 없는 전체 테스트:

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s backend/tests -t backend -v
```

실제 Firestore 검사는 명시적 `--live`일 때만 실행합니다. 기본 실행은 안내 후 종료 코드 2로 종료합니다.

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\check_data_api.py' --live
```

도구는 `data`를 읽기만 하며 원본 CSV의 독립 계산과 API 응답을 대조합니다.
쓰기 테스트는 매번 무작위 `_data_api_checks_실행ID` 컬렉션에 서버 내부 의존성을 교체해
같은 API 라우터로 수행합니다. HTTP 요청에서 컬렉션을 고르는 기능은 없습니다.
이번 실행의 소유 표시·내용·수정 시각이 확인된 테스트 문서만 finally에서 정리하고 부재를 확인합니다.
실패와 정리 실패를 별도로 보고하며 원본 데이터를 가져오기 도구로 복구하지 않습니다.
결과는 `.local/data-api-live.json`에 남습니다. 실제 통합 검사와 모의 검사의 근거는 [PROGRESS.md](PROGRESS.md)에 구분했습니다.

## 10~12단계 — 초기 OpenAI 구현·검증 기록

2026-10-28 확인: **코드·모의 테스트와 실제 Firestore 기록 기능 검증 완료 / 실제 OpenAI 생성 실패**.
로컬 키 연결 후 기존 `--live-openai`로 실제 Responses 생성 요청을 **1회** 수행했으나,
앱의 HTTP 503 `openai_quota_unavailable`로 실패했습니다. 자동 재시도·모델 변경·추가 호출은 하지 않았습니다.
실제 AI 답변·토큰 사용량·시연용 대화 ID는 아직 없습니다.

| API | 성공 | 동작 |
| --- | --- | --- |
| `POST /api/chat` | 200 | 현재 요약 기반 답변을 생성하고 저장 확인 후 반환 |
| `POST /api/conversations` | 201 | 완성된 문답 쌍을 새 수동 대화로 저장, AI 호출 없음 |
| `GET /api/conversations` | 200 | 최신 수정순 목록, 메타데이터만 반환 |
| `GET /api/conversations/{id}` | 200 | 특정 대화의 전체 메시지·메타데이터 불러오기 |
| `DELETE /api/conversations/{id}` | 204 | 지정된 대화 한 건만 삭제, 본문 없음 |

대화 저장·목록·상세·삭제와 기존 API에는 OpenAI 키가 필요하지 않습니다.
채팅 입력은 `message`와 선택 `conversation_id`만 받습니다. 새 대화는 ID를 생략하거나 null로 지정하고,
이어가기는 서버가 발급한 UUID4 ID를 사용합니다. 클라이언트가 전체 이력·system 프롬프트·작성 시각·
모델 사용량을 지정할 수 없으며 추가 필드는 거부합니다.

### OpenAI 설정과 호출

공식 `openai==3.40.0`과 필요한 의존성만 `.venv`에 추가했습니다. 기존 46개 패키지 버전은
보존했고 `pip check`를 통과했습니다. 초기 구현 당시에는 `backend/.env`를 변경하지 않았으며,
이후 사용자 요청으로 기존 로컬 키를 이 파일에 등록했습니다. Firebase 설정은 보존했습니다.

| 환경변수 | 기본값·용도 |
| --- | --- |
| `OPENAI_API_KEY` | 기본 빈 값. 환경변수 또는 `backend/.env`에 사용자가 직접 설정 |
| `OPENAI_MODEL` | `gpt-5.4-mini` |
| `OPENAI_BASE_URL` | `https://copa.codyssey.kr/v1` — 코디세이 SDK용 주소, 다른 주소는 검증 단계에서 차단 |
| `OPENAI_MAX_OUTPUT_TOKENS` | 800, 허용 범위 1~4096 |
| `OPENAI_TIMEOUT_SECONDS` | 45, 0초 초과~120초 |

키를 채팅·로그·저장소에 넣지 마세요. 실제 프로세스 환경변수가 고정 경로 `backend/.env`보다 우선하며
명시적인 빈 값도 우선합니다. 키·모델·결제 설정을 자동 발급·변경하지 않습니다.
현재 사용자가 전달한 코디세이 공식 연결 안내의 `gpt-5.4-mini`만 허용합니다.
다른 모델은 503으로 중단하며 자동 모델·주소·제공자 전환은 없습니다.

공식 Python SDK의 `client.chat.completions.create(...)`를 한 번 호출합니다.
설정의 `base_url`을 SDK 생성 시 명시하며 최종 주소는 `https://copa.codyssey.kr/v1/chat/completions`입니다.
답변 규칙·현재 요약을 `system` 메시지로, 제한된 이력·질문을 나머지 `messages`로 전달합니다.
요청 인자는 `model`, `messages`, `max_completion_tokens`이며 기존 출력 한도 800을 매핑합니다.
SDK `max_retries=0`, timeout 45초를 유지하고 Responses 전용 인자·temperature·도구·스트리밍 옵션은 보내지 않습니다.
클라이언트는 요청 후 정리하고, SDK 동기 호출은 일반 `def` 라우터의 worker thread에서 실행합니다.
`choices[0].finish_reason=stop`과 `message.content`를 확인하고 빈 답변·차단·거절·잘림·도구 응답을 거부합니다.
실제 응답 `model`과 제공된 `usage.prompt_tokens`/`completion_tokens`를 기존 `input_tokens`/`output_tokens`로 기록합니다.
사용량이 없거나 불완전하면 null이며 추정하지 않습니다.

**질문·서버가 계산한 요약·선택된 최근 대화는 코디세이 중계 서버를 거쳐 GPT에 전달됩니다.**
현재 요청에는 이전 Responses의 `store=False`를 보내지 않습니다. 중계 서버의 보관 정책은 이번 검증 범위에서 확인하지 않았습니다.

### 같은 요약 로직과 답변 경계

채팅은 매 질문마다 현재 Firestore 자료를 읽고, `/api/data/summary`와 같은
`calculate_summary` 함수를 직접 호출합니다. 자기 서버로 HTTP 요청하거나 저장된 예전 요약을 재활용하지 않습니다.
모델에는 계산된 SummaryResponse JSON만 전달하며 CSV 전체·128행·자유 입력 memo·키·환경변수·내부 경로는 넣지 않습니다.
현재 질문과 최근 최대 5문답, 과거 내용 총 12,000자 이내를 완성된 문답 쌍 단위로 선택합니다.
모델 입력을 제한해도 Firestore의 전체 저장 이력은 그대로 유지합니다.

고정 system 답변 규칙은 최신 요약 수치·기간 우선, 최신 저장 월과 현재 달 구분, 순이동과 전체 인구 증감 구분,
음수 상승과 순유입 전환 구분, 작은 차이의 통계적 유의성 주장 금지, 원인·정책 효과·예측의 단정 금지,
요약에 없는 월·집계의 확인 불가 안내를 요구합니다. 이전 대화·사용자 입력은 시스템 명령으로 취급하지 않고
보통 3~6문장으로 수치·기간·해석 한계를 설명하도록 했습니다. 이번 실제 답변의 기간·수치·해석은 전달 요약과 대조했습니다.
빈 데이터 또는 요약 조회 실패에서는 유료 호출을 하지 않습니다.

### 저장 구조와 한도

기본 컬렉션은 `conversations`입니다. 서버가 UUID4 ID와 UTC `created_at/updated_at`을 정하며,
응답 시각은 ISO 8601 형식입니다. `title`, `messages`, `message_count`, `source`를 저장합니다.
수동 저장은 `source=manual`, AI 문답이 저장되면 `source=chat`이고 실제 사용한 `last_summary`,
`last_model`, 제공된 `last_usage`를 기록합니다. 수동 대화를 이어가면 기존 문답을 보존하고 source가 chat으로 바뀝니다.
목록에는 id/title/created_at/updated_at/message_count만 포함하고, 상세 조회에는 전체 메시지와 메타데이터를 포함합니다.
제목을 생략하면 첫 질문을 최대 80자로 잘라 만들며 제목 생성용 AI 호출은 없습니다.

- 최대 40개 메시지(20문답), user 2,000자, assistant 4,000자, title 80자.
- 채팅 질문은 앞뒤 공백 제거 후 1~2,000자. 수동 입력도 빈 내용과 미완성 문답을 거부합니다.
- user/assistant가 번갈아 나오는 완성된 문답만 허용하며 system/developer 역할은 거부합니다.
- 저장 payload의 UTF-8 JSON 크기는 **256 KiB** 이하입니다. 글자 종류에 따라 20문답 전에 크기 한도에 도달할 수 있습니다.
- 유료 호출 전에 최대 답변 크기까지 예약하여 한도를 검사합니다. 기록을 조용히 자르거나 삭제하지 않습니다.

새 대화는 `create`, 기존 대화는 읽을 때의 Firestore 갱신 시각을 조건으로 `update`합니다.
읽은 뒤 변경·삭제된 대화는 409로 처리하며 덮어쓰거나 재생성하지 않습니다.
GPT를 트랜잭션 재시도 콜백에서 실행하지 않습니다. 저장 후 다시 읽어 값이 일치해야 성공을 반환합니다.

| 실패 | 상태·처리 |
| --- | --- |
| 입력·역할·ID·메시지/크기 한도 | 422, 한도 도달 시 새 대화 안내 |
| 없는 대화 | 404 |
| 빈 데이터 | 409 `data_empty`, AI 호출 없음 |
| 키 누락·인증·모델·잔액/한도 설정 | 503, 구분되는 안전한 오류 코드 |
| 호출 빈도 제한 / AI timeout | 429 / 504, 자동 재호출 없음 |
| 빈 답변·실패·불완전·거절·초과 길이 | 502, 정상 대화로 저장하지 않음 |
| AI 생성 후 대화가 변경·삭제됨 | 409, `saved=false`, 자동 재호출 없음 |
| AI 생성 후 DB 저장 실패·미확인 | 503 `chat_save_failed`, `saved=false`, 자동 재호출 없음 |

저장 미확인은 실제 DB에 전혀 쓰이지 않았다는 보장이 아니므로 이력을 확인해야 합니다.
오류 응답·로그에는 키·입력 원문·원본 예외를 넣지 않습니다. 오류 로그는 고정 오류 코드와 요청 식별자만 남깁니다.

### 실행과 검증

기존 8000/8001 서버는 유지했습니다. 새 코드를 확인하려면 **별도 PowerShell의 프로젝트 루트**에서 실행합니다.
이번 8002 검증용 서버는 종료했습니다. 이후 8002가 사용 중이면 다른 빈 포트를 선택하세요.

```powershell
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002
```

Swagger: **http://127.0.0.1:8002/docs**. 기존 서버에 새 코드를 적용하려면 사용자가 해당 서버를 재시작해야 합니다.
로컬 키 인식은 해결됐습니다. 2026-10-28 개인 키 검사에서는 `/api/chat`이 503 `openai_quota_unavailable`을 반환했으며, 코디세이 키의 최신 결과는 문서 마지막에 구분했습니다.
실제 키는 본인이 로컬 `backend/.env` 또는 프로세스 환경변수에 설정하고 채팅으로 보내지 마세요.

```powershell
# 외부 접속 없는 전체 테스트
& '.\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s backend/tests -t backend -v

# 실제 Firestore + 모의 AI, 무작위 격리 컬렉션만 쓰고 이번 문서는 정리
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\check_chat.py' --live-firestore

# 최초 승인된 실제 검사 명령(이미 1회 시도함; 현재는 보호 기록으로 재시도 차단)
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\check_chat.py' --live-openai
```

실제 OpenAI 검사 질문은 “최신 저장 월 기준으로 최근 12개월과 직전 12개월의 월평균 순이동을 비교해줘.
전체 인구 증감이나 이동 원인까지 이 자료로 확정할 수 있는지도 알려줘.”입니다.
성공한 GPT 검증 대화는 `[코디세이 GPT 연결 검증]` 표시가 있는 제목으로 기본 conversations에 남기고, AI를 다시 부르지 않고 목록·상세를 확인합니다.
실제 답변 수치·기간·해석 한계는 반환된 요약과 직접 대조해야 합니다.
당시 개인 키 검사에서는 API 사용 한도·잔액 관련 오류로 답변을 받지 못해 수치·기간·해석 대조와
시연 대화 저장·목록·상세 복원 검증을 수행하지 못했습니다. 대화 ID와 실제 응답 모델·사용량은 없습니다.

한 번이라도 실제 생성을 시도하면 `.local/chat-openai-attempt.json`에 기록하고 이후 자동 시도를 차단합니다.
실패해도 모델 변경·재시도를 하지 않으며 추가 유료 호출은 별도 승인이 필요합니다.
키가 없으면 유료 호출·Firebase 검사·시도 기록 생성 없이 대기로 종료합니다.

기존 오프라인 263개, 실제 Firestore+모의 AI 격리 검증, 8002 HTTP 검사 통과 기록은 유지합니다.
이번에는 코드를 변경하지 않았으며 이 검사들을 반복하지 않았습니다.
원본 data 128건·기존 conversations는 보존했고 격리 문서 2건의 삭제 후 부재를 확인했습니다.
당시 실제 OpenAI 생성 요청 1회·정상 답변 0건이며, 당시 검사에서 data 128건과 기존 conversations 0건이
전후 동일했습니다. 실행 근거는 [.local/chat-openai-live.json](.local/chat-openai-live.json),
단계별 상태는 [PROGRESS.md](PROGRESS.md)에 기록했습니다.
키를 다시 발급하거나 재등록하지 말고 해당 API 조직·프로젝트의 사용 한도·잔액·결제 상태를 확인해야 합니다.
이번 기록만으로 어느 항목이 원인인지 단정할 수 없습니다. 보호 기록을 유지하며 추가 호출은 별도 승인 전 실행하지 않습니다.

**인증·사용량 제한을 적용하기 전까지 로컬 전용입니다.** 공개 배포 전 데이터 쓰기뿐 아니라
채팅 비용과 대화 목록·상세 조회 권한도 보호해야 합니다. 이번에는 로그인·프론트엔드·배포·Git 작업을 추가하지 않았습니다.

## 이전 Gemini 전환·실제 1회 검증 기록 — 현재 지시로 중단

아래는 취소된 전환 지시에 따른 과거 기록입니다. 현재 과제는 OpenAI이며 Gemini 구현·키 탐색·호출을 중단했습니다.
Gemini의 과거 성공은 GPT 연결 성공이나 이번 과제 10~12단계 완료 근거로 사용하지 않습니다.

2026-10-28 사용자 요청으로 지정한 기존 설정 파일의 Gemini 키를 `backend/.env`에 등록했습니다.
원본 설정 파일을 수정하지 않았고 기존 Firebase·OpenAI 설정도 보존했습니다.
키를 예제 파일에 넣거나 채팅·로그로 출력하면 안 됩니다. `backend/.env.example`의 키 항목은 빈 값입니다.

| 환경변수 | Gemini 전환 당시 설정(현재 사용하지 않음) |
| --- | --- |
| `AI_PROVIDER` | `gemini` (`openai`도 명시적으로 선택 가능, 미설정 기본값은 기존 호환을 위한 `openai`) |
| `GEMINI_API_KEY` | 기존 키 등록·로더 인식 확인, 값 비공개 |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `GEMINI_MAX_OUTPUT_TOKENS` | 800 |
| `GEMINI_TIMEOUT_SECONDS` | 45 |

모델은 [Google 공식 문서의 안정 버전](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)을 선택했습니다.
실제 1회 응답으로 해당 모델 이용을 확인했습니다. 잔여 할당량·최종 청구 금액을 확인한 것은 아니며 무료 사용을 보장하지 않습니다.
설정은 고정 `backend/.env`를 읽고 프로세스 환경변수가 우선합니다. `GOOGLE_API_KEY`나 다른 프로젝트를 자동 탐색하지 않습니다.
설정한 제공자가 실패해도 다른 제공자나 모델로 전환하지 않습니다.

공식 `google-genai==2.33.0`을 기존 `.venv`에 설치했습니다. 기존 52개 패키지 버전은 유지했고 `pip check`를 통과했습니다.
기존 `/api/chat`, 요약 계산, 최근 5문답/12,000자 제한과 대화 자동 저장·조회·삭제는 그대로 재사용합니다.
Gemini에는 고정 규칙과 요약을 `system_instruction`, 대화를 `contents`로 전달합니다.
네이티브 `generate_content` 한 번, SDK 총 시도 1회, 45초 timeout, 최대 출력 800토큰,
`thinking_level=MINIMAL`로 설정했습니다. 스트리밍·도구·자동 함수 호출은 사용하지 않습니다.
질문·요약·선택된 대화는 Google로 전송됩니다. OpenAI의 `store=False` 설정이 Gemini에 적용되는 것은 아닙니다.

정상 `STOP` 텍스트만 저장하며 차단·빈 값·불완전 응답은 안전한 오류로 처리합니다.
실제 `model_version`을 모델명으로 사용하고, 입력 토큰은 `prompt_token_count`, 출력 토큰은
`candidates_token_count`와 제공된 `thoughts_token_count`의 합으로 기록합니다. 필요한 사용량이 없으면 null입니다.
429 응답은 `gemini_rate_or_quota_limited`로 구분하며 상세 근거 없이 호출 빈도와 잔액 원인을 단정하지 않습니다.
저장 실패로 생성 요청을 반복하지 않습니다.

기존 검사 도구에 `--live-gemini`를 추가했으며 사용자의 별도 승인 후 아래 명령을 **1회 실행해 성공**했습니다.
시도 방지 파일을 유지하므로 이 명령을 다시 실행해 추가 생성하지 않습니다.

```powershell
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'
# 과거 실행 기록: 현재 지시에서는 Gemini 검사를 실행하지 않습니다.
& '.\.venv\Scripts\python.exe' -X utf8 '.\backend\scripts\check_chat.py' --live-gemini
```

Gemini 전용 `.local/chat-gemini-attempt.json`과 결과 파일을 사용하며 OpenAI의 시도 방지 파일·실패 보고서는 유지합니다.
정상 응답의 질문·답변·요약·사용량이 자동 저장 후 목록·상세 조회에서도 동일하게 복원되는 것을 확인했습니다.
`[연결 검증]` 시연 대화 ID: **`94ff2d2f-dc18-4f50-a0c6-0f933c13b57e`**. 이 한 건을 남겼습니다.
모델은 실제 응답의 `gemini-3.5-flash-lite`, 제공된 사용량은 **입력 796·출력 231토큰**입니다.

답변은 최신 월 2026-08, 최근 2025-09~2026-08 평균 -558.0명, 직전 2024-09~2025-08 평균 -551.42명,
차이 -6.58명을 정확히 사용했습니다. 전체 인구 증감과 순이동을 구분하고 원인·정책 효과 단정도 피했습니다.
두 평균이 음수이므로 정확히는 **월평균 순유출 규모가 6.58명 확대**됐습니다. 답변 괄호의 일반 표현을
이렇게 구체화했으며 문구 차이를 이유로 추가 생성하거나 저장된 답변을 수정하지 않았습니다.

원본 data는 **128→128건**, 전체 값·타입·생성·수정 시각의 해시가 일치했습니다.
기존 대화는 0건이었고 시연 1건만 추가됐으며 시연을 제외한 전후 내용은 동일합니다.
새 서버를 띄우거나 기존 사용자 서버를 조작하지 않았습니다.
관련 오프라인 검사 **103개**(새 검사 57개＋기존 회귀 46개)와 health/docs/OpenAPI 200은 준비 단계의 근거입니다.
이번에는 코드 수정과 테스트 반복 없이 실제 검사·답변 검토·문서 갱신만 했습니다.
근거: [실제 검사 결과](.local/chat-gemini-live.json), [답변 대조](.local/gemini-answer-review.json),
[이전 준비 결과](.local/gemini-preparation.json).

## 이전 GPT 경로 복구 기록 — 2026-10-28, 외부 호출 없는 검증

**GPT 구현·키 인식 완료, 실제 답변 검증은 결제·사용 한도 해결 대기**.
`backend/.env`와 `.env.example`의 기존 `AI_PROVIDER` 값만 `openai`로 변경했습니다.
기존 `OPENAI_API_KEY`, `OPENAI_MODEL=gpt-5.4-mini`, Firebase 설정과 나머지 설정을 보존했습니다.
호출 경로의 코드를 바꿀 필요가 없어 기존 Responses 구현을 그대로 사용합니다.

새 Python 프로세스에서 실제 설정 로더와 앱의 채팅 의존성 함수를 사용해
`openai` → `OpenAIService` 선택과 기존 키 인식을 확인했습니다. 이 확인에서는 네트워크 연결을 막았고
SDK 클라이언트도 생성하지 않았습니다. Gemini 서비스와 설정은 OpenAI 경로에서 사용하지 않습니다.
공식 `https://api.openai.com/v1` 주소, Responses API, 최대 출력 800토큰, timeout 45초,
SDK `max_retries=0`을 유지합니다. 오류가 나도 모델이나 제공자를 자동 전환하지 않습니다.

기존 모의 테스트 11개로 제공자 선택, 공식 호출 주소·재시도 제한, 요약 전달,
정상 응답·사용량 처리, 저장·복원·이어가기 및 저장 실패 후 재호출 차단을 확인했습니다.
실제 AI·DB 요청은 **0회**이며 기존 데이터·대화·검증 기록과 사용자 서버를 변경하지 않았습니다.
Gemini 코드·패키지는 이번 복구에 필요하지 않아 삭제하지 않고 비활성 상태로 남겼습니다.

남은 작업은 사용자가 API 결제·잔액 반영 완료를 알리고 **추가 GPT 1회 검증을 허용한 후** 진행합니다.
그 전에는 실제 GPT 요청, 자동 결제·충전·모델 변경을 하지 않습니다.
기존 실패 기록과 시도 방지 파일을 삭제하거나 우회하지 않습니다.
근거: [실제 앱 경로의 외부 호출 없는 확인](.local/openai-restored-path.json),
[복구·검증·기록 보존](.local/openai-restore-verification.json).

## 이전 코디세이 키의 OpenAI 직접 호출 실패 — 2026-10-29

사용자의 별도 1회 승인으로 새 `.venv` Python 프로세스에서 기존 `check_chat.py --live-openai`를 실행했습니다.
`AI_PROVIDER=openai`, 실제 앱의 `OpenAIService`, 공식 `https://api.openai.com/v1`의 Responses API,
요청 모델 `gpt-5.4-mini`, 최대 출력 800토큰·timeout 45초·SDK 재시도 0을 유지했습니다.
별도로 제공된 모델·접속 안내는 확인되지 않아 기존 설정을 변경하지 않았습니다.

- 실제 생성 요청 **1회, 실패**. 앱 HTTP **503** `openai_authentication_failed`와 제공자 HTTP **401** `invalid_api_key`를 구분해 기록했습니다.
- 실제 응답 모델·토큰 사용량·정상 답변은 제공되지 않았습니다. `saved=false`, 새 대화 ID 없음; GPT 답변 대조·자동 저장·목록·상세 복원은 미완료입니다.
- 전달한 요약은 최신 저장 월 2026-08 기준입니다. 최근 2025-09~2026-08 평균 -558.00명, 직전 2024-09~2025-08 평균 -551.42명과 해석 한계를 포함했습니다. 이것은 전달 자료이며 AI 답변이 아닙니다.
- 원본 `data` 128건과 기존 대화 1건은 ID·전체 값·생성/수정 시각의 전후 비교가 일치했습니다. 새 문서 쓰기·삭제와 사용자 서버 종료·재시작은 없었습니다.
- 검사 도구에 명시적 `--run-id`를 추가해 이번 승인만 별도 기록했습니다. 동일 ID의 방지 파일 또는 결과가 있으면 호출 전에 중단하며 자동 ID 생성·재시도·모델 변경·Gemini 전환은 없습니다.
- 관련 모의 테스트 **37개 통과**. 전체 263개를 반복하지 않았고 앱의 GPT·채팅·저장 코드는 변경하지 않았습니다.

실행 위치는 프로젝트 루트이며 실제 실행 명령은 다음과 같습니다. **이미 사용한 1회 승인 기록이므로 다시 생성 요청을 보내지 않습니다.**

```powershell
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'
& '.\.venv\Scripts\python.exe' -X utf8 -c 'import logging, runpy; logging.disable(logging.CRITICAL); runpy.run_path("backend/scripts/check_chat.py", run_name="__main__")' --live-openai --run-id codyssey-20261029-01
```

코디세이 지원 담당자에게 제공 키의 활성 상태와 공식 OpenAI API 주소용 키인지 확인이 필요합니다.
이번 오류만으로 폐기·오타·별도 접속 방식 중 원인을 특정할 수 없으며, 잔액 부족이나 개인 결제 필요로 판단하지 않습니다.
추가 생성 요청은 별도 허용 전 실행하지 않습니다. **10~12단계 전체 완료로 표시하지 않습니다.**

근거: [이번 실행 결과](.local/chat-openai-codyssey-20261029-01-live.json),
[이번 1회 방지 기록](.local/chat-openai-codyssey-20261029-01-attempt.json),
[사전 설정·과거 기록 해시](.local/codyssey-openai-preflight-20261029.json),
[실행 후 검토·기록 보존](.local/chat-openai-codyssey-20261029-01-review.json).

## 코디세이 중계 서버의 실제 GPT 검증 — 2026-10-29 최신 결과

사용자가 전달한 공식 안내에 따라 `OPENAI_BASE_URL=https://copa.codyssey.kr/v1`을 적용하고,
기존 `OpenAIService`의 호출·응답 변환만 Chat Completions로 바꿨습니다. 기존 키·Firebase·모델·출력 제한·timeout은 보존했습니다.
현재 데이터 요약·채팅·대화 저장 서비스는 그대로 사용했습니다.

- **이번 생성 요청 1회 성공**, `/responses` 요청 0회. 앱 `/api/chat` HTTP 200, `saved=true`.
- 실제 응답 모델 **gpt-5.4-mini**, 제공 사용량 **입력 736 / 출력 198토큰**.
- 최신 저장 월 2026-08, 최근 2025-09~2026-08 **-558.0명**, 직전 2024-09~2025-08 **-551.42명**, 차이 **-6.58명**으로 답변이 전달 요약과 일치했습니다.
- 전체 인구 증감과 순이동을 구분하고 현재 달 실적·이동 원인·정책 효과를 단정하지 않았습니다.
  답변은 '순이동 수치 하락'으로 표현했습니다. 두 기간 모두 순유출이며 월평균 순유출 규모가 약 6.58명 커졌다는 뜻을 직접 풀어 쓰지는 않았지만 방향·수치는 정확합니다. 원문은 그대로 보존했습니다.
- `[코디세이 GPT 연결 검증]` 표시의 시연 대화 **1건** 자동 저장·목록 확인·동일 질문/답변 상세 복원 성공.
  ID: `b3d5e4ba-9bda-46db-90d6-b012e071b5b6`.
- 원본 data **128건**과 기존 Gemini 대화 **1건**의 ID·내용·생성/수정 시각이 보존됐습니다. conversations는 새 시연만 추가되어 1→2건입니다.
- 관련 오프라인 검사 **121개 통과**. 실제 SDK의 모의 HTTP로 정확한 최종 URL·요청 본문·완료 판정·사용량·재시도 0을 확인했습니다.
- 과거 검증 기록 **12개 파일의 해시 일치**. 사용자 서버 종료·재시작, 키 재발급·재탐색, 추가 AI 요청, 프론트엔드·배포 작업 없음.

프로젝트 루트에서 실제 실행한 명령입니다. 이 실행 ID의 1회 승인은 사용됐으며 같은 ID 재실행은 호출 전에 차단됩니다.

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 -c 'import logging, runpy; logging.disable(logging.CRITICAL); runpy.run_path("backend/scripts/check_chat.py", run_name="__main__")' --live-openai --run-id codyssey-chat-20261029-01
```

**10~12단계 완료**: 실제 GPT 답변 내용 확인과 자동 저장·복원까지 통과했습니다. 로컬 백엔드 검증 범위의 완료이며 프론트엔드·배포 완료를 뜻하지 않습니다.
근거: [실제 결과·답변 원문](.local/chat-openai-codyssey-chat-20261029-01-live.json),
[답변 대조·보존 검토](.local/chat-openai-codyssey-chat-20261029-01-review.json),
[별도 1회 방지 기록](.local/chat-openai-codyssey-chat-20261029-01-attempt.json),
[설정·과거 기록 사전 확인](.local/codyssey-chat-completions-preflight-20261029.json).

## 13~14단계 로컬 웹 화면 — 2026-10-29

HTML/CSS/JavaScript만 사용한 요약·채팅·이전 대화·월별 데이터 관리 화면입니다. 프레임워크, 외부 폰트/아이콘, 새 패키지를 추가하지 않았습니다. 기존 백엔드 API·Firebase·코디세이 GPT 설정은 변경하지 않았습니다.

- 요약: `GET /api/data/summary`의 기간·개수·평균·최근/직전 12개월·차이·추세를 표시합니다. 통계 재계산 없이 `null`, 0, 빈 자료, 조회 실패를 구분합니다.
- 채팅: `POST /api/chat`만 사용하며 초기 화면·예시 선택·대화 조회는 AI를 호출하지 않습니다. 질문 최대 2,000자, IME 입력 보호, Enter 전송/Shift+Enter 줄바꿈, 중복 전송·응답 중 대화 전환 차단, 실패 입력 보존을 구현했습니다. `saved=true`일 때만 저장 완료로 표시합니다.
- 대화: `GET /api/conversations`, `GET/DELETE /api/conversations/{id}`. 서버 ID로 이어서 질문하고 제목 확인 후 삭제합니다. 별도 `POST /api/conversations`는 호출하지 않습니다. 실제 `last_model`을 표시하며 브라우저 저장소에는 선택한 대화 ID만 남깁니다.
- 자료: `GET/POST /api/data`, `PUT/DELETE /api/data/{id}`. 월을 시간대 변환 없이 `YYYY-MM-01`로 보내며 수정 중 월은 잠급니다. 삭제 전 월·값을 확인하고 성공 후 목록·요약을 다시 조회합니다. 메모 최대 500자, 정수만 허용하며 음수·0을 지원합니다. 브라우저의 정확한 정수 범위(±9,007,199,254,740,991)를 넘는 입력은 반올림하지 않고 차단합니다.
- 사용자·AI·제목·메모는 `textContent`로 표시합니다. 공통 요청 함수는 204 무본문, JSON이 아닌 오류, HTTP/네트워크 오류를 구분합니다. 읽기 15초·변경 25초·채팅 75초 제한이며 자동 재시도는 없습니다. 브라우저 시간초과가 서버 작업 취소를 의미하지 않으므로 완료 여부가 불명확하면 대화 기록을 확인하세요.

### 실행 위치와 주소

현재 `frontend/config.js`의 `API_BASE_URL`은 **http://127.0.0.1:8002**입니다. 코디세이 주소가 아니라 우리 FastAPI 주소입니다. 기존 8000번 서버는 그대로 유지했습니다. 검증 종료 시점에 아래 두 서버는 127.0.0.1에 실행 중임을 HTTP로 확인했습니다. 이미 실행 중이면 같은 명령을 중복 실행하지 마세요.

각각 별도의 PowerShell 창에서 프로젝트 루트로 이동한 뒤 실행합니다.

```powershell
# 창 1: 백엔드 (8002번이 비어 있을 때)
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'
& '.\.venv\Scripts\python.exe' -X utf8 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002
```

```powershell
# 창 2: frontend 폴더만 제공 (5500번이 비어 있을 때)
Set-Location -LiteralPath 'C:\Users\user\OneDrive\바탕 화면\gajimaiso-ai-assistant'
& '.\.venv\Scripts\python.exe' -X utf8 -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

- 화면: <http://127.0.0.1:5500/>
- API 문서: <http://127.0.0.1:8002/docs>
- 종료하려면 직접 실행한 해당 PowerShell 창에서 `Ctrl+C`를 누릅니다. 다른 사용자 서버는 종료하지 마세요.
- 다른 빈 포트를 쓰면 공개 `frontend/config.js`와 기존 백엔드의 정확한 허용 출처 설정도 그 주소에 맞춰야 합니다. CORS를 `*` 또는 `no-cors`로 우회하지 않습니다.

정적 루트에 비밀 파일·심볼릭 링크는 없습니다. `.env`와 키 TXT의 정적 요청이 모두 404인지 확인했습니다. 키나 backend 폴더를 웹 루트에 추가하지 마세요.

### 확인 범위와 남은 검증

- 실제 정상 백엔드 읽기: data 128건·summary·대화 2건·기존 GPT 시연 상세 200, health/docs/OpenAPI 200. CORS 허용 출처는 정확히 `http://127.0.0.1:5500`입니다.
- 실제 브라우저 + 격리 Firestore: 빈 자료 표시, 0·음수 추가 2건(201), 중복 월 409와 입력 보존, 목록·요약 갱신, 최신 월 정렬, 수정 중 월 잠금, HTML 형태 메모의 문자 표시를 확인했습니다. 원본 컬렉션에는 쓰지 않았습니다.
- 외부 연결 없는 테스트: 프론트엔드 순수 함수·가짜 HTTP 47개와 검증 도구 9개 통과. IME·중복 제출·204·422/409/404/503·비JSON·통신 실패·시간제한은 이 모의 검사 근거이며 모든 브라우저 동작을 검수했다는 뜻이 아닙니다.
- 브라우저 수정 확인 창에서 도구 연결이 끊겼고, 복구 도구가 현재 브라우저 URL을 안전하게 확인하지 못해 화면 조작을 중단했습니다. 수정/삭제 완료, 채팅 전송·저장·새로고침 복원, 나머지 오류 화면, 390px 모바일 검수는 미완료입니다. 1440px 초기 화면은 관찰했으나 최종 PC·모바일 검수 캡처 파일은 생성하지 못했습니다.
- **이번 추가 실제 AI 요청 0회, 새 시연 대화 0건**입니다. 브라우저 검증을 대신하는 직접 AI 호출은 하지 않았습니다. 앞선 10~12단계의 GPT 성공 기록은 유지됩니다.
- 격리 서버 8011은 종료했고 이번 테스트 문서 2건만 삭제·부재 확인했습니다. 최초 스냅샷 대비 원본 128건과 기존 대화 2건의 전체 값·생성/수정 시각이 보존됐습니다. [정리·보존 근거](.local/frontend-ui-isolated-20261029-cleanup.json)
- 브라우저에 격리 테스트의 수정 확인 창이 남아 있다면 **취소 후 화면을 새로고침**하세요. 현재 공개 설정은 정상 백엔드 8002번입니다. 실제 원본 수정·삭제 버튼을 검증용으로 누르지 마세요.

검증 근거: [실제 서버 읽기](.local/frontend-initial-read-check.json), [최종 서버 상태](.local/frontend-final-server-check.json), [프론트엔드 모의 검사](.local/frontend-unit-tests.json), [격리 실행 기록](.local/frontend-ui-isolated-20261029-report.json). 전체 13~14단계 완료로 기록하지 않습니다.

Vercel 배포는 후속 작업입니다. 공개 `API_BASE_URL` 빌드 설정으로 `config.js`를 생성하도록 연결할 수 있으나 정적 브라우저 코드가 서버 환경변수를 자동으로 읽지는 않습니다. 공개 배포 전 데이터 변경·대화 접근·AI 호출의 인증/권한 보호 및 코디세이 키의 배포 환경 사용 허용 범위를 확인해야 합니다. 이번에는 배포·GitHub 작업을 하지 않았습니다.

## 13~14단계 브라우저 검수 재개 — 2026-10-29

이 절은 앞선 미완료 브라우저 검수에 추가한 최신 결과입니다. **전체 완료는 아직 아닙니다.** 기존 5500·8002 서버를 종료하거나 재시작하지 않았습니다.

실제 브라우저에서 원본 128건·현재 요약·기존 GPT 대화 표시와 새로고침 후 동일 질문/답변 복원을 확인했습니다. 초기 콘솔 error 항목은 0개였습니다. 1440px PC와 390px 모바일에서 페이지 가로 넘침·버튼 겹침이 없었고, 모바일 대화 목록 접기/펼치기 및 데이터 폼·표 접근을 확인했습니다. 캡처는 [.local/verification-13-14/](.local/verification-13-14/)에 저장했습니다.

격리 Firestore와 모의 AI에서 추가201·중복409/입력 보존·목록/요약 갱신·월 잠금·수정 폼 취소·HTML 문자열 안전 표시를 확인했습니다. Enter 전송/Shift+Enter 줄바꿈, 로딩 중 보내기·새 대화·입력 차단, 모의 답변 자동 저장·새로고침 복원 및 같은 대화 이어가기(대화1건/메시지4개)도 확인했습니다. **실제 GPT 요청은 0회**이며 모의 AI가 2회 응답했습니다.

브라우저 기본 확인창은 대상 월과 변경값을 정확히 표시했지만, 도구의 confirm 수락과 직접 OK 버튼 조작이 시간초과로 끝났습니다. 격리 서버에 PUT/DELETE 요청이 도달하지 않았으므로 수정·삭제 완료를 성공으로 기록하지 않습니다. 앱 코드 오류로 확정하지 못해 HTML/JS/CSS를 변경하지 않았고, 이미 통과한 47개/9개 테스트도 이유 없이 반복하지 않았습니다. 서버중단·422·503 등의 실제 오류 화면과 실제 브라우저 GPT 생성도 미확인입니다.

이번 격리 서버는 stdin `stop`으로 정상 종료(코드0)했습니다. 이번 소유 데이터2건과 모의 대화1건만 정리하고 부재를 확인했습니다. 최초 스냅샷 대비 원본 data128건·기존 대화2건의 ID·내용·생성/수정시각이 모두 동일합니다. `frontend/config.js`는 정상 주소8002로 복원했으며, 프론트5500·백엔드8002의 HTTP200을 다시 확인했습니다. 기존8000도 유지했습니다.

- [PC 1440px 캡처](.local/verification-13-14/desktop-1440.jpg)
- [모바일 390px 채팅 캡처](.local/verification-13-14/mobile-390-chat.jpg)
- [모바일 390px 데이터 캡처](.local/verification-13-14/mobile-390-data.jpg)
- [브라우저 결과·원본 보존 근거](.local/verification-13-14/browser-resume-results.json)
- [격리 요청·정상 정리 보고서](.local/frontend-ui-isolated-resume-20261029-report.json)
- [남은 확인창 수동 검수 순서](.local/verification-13-14/MANUAL_CHECK.md) — 아직 수행 결과가 아닌 절차입니다. 원본 128건이 표시되는 정상 화면에서 수정·삭제 검증을 하지 마세요.

키·Firebase·모델 변경, 패키지 설치, 배포·GitHub 작업은 없습니다. 남은 핵심 확인창 동작을 검증하기 전까지 13~14단계 전체 미완료를 유지합니다.

## 13~14단계 최종 추가 검수 — 2026-10-29

이 절이 최신 결과입니다. **실제 GPT 화면·저장·복원과 오류 안내는 확인됐으며, 브라우저 확인창 승인 3항목만 수동 확인 대기입니다.** 13~14단계 전체 완료로 표시하지 않습니다.

- 격리 Firestore API·DB 검사 **13/13 통과**: 자료 수정 -12→-15, 목록·평균 -6→-7.5 갱신, 자료 삭제 후 실제 부재·빈 요약, 모의 대화 삭제 후 목록 부재·상세404를 확인했습니다. 이는 브라우저 확인창 승인 결과와 구분합니다.
- 실제 브라우저에서 소수 입력 거절, 중복 월409, 삭제된 대화404, 서버 연결 실패, 모의 GPT 실패502 안내를 확인했습니다. 실패 질문은 남고 저장 완료로 표시되지 않았습니다. 확인창 사전 이벤트 핸들러가 도구에 없어 이전 시간초과 방식을 반복하지 않았습니다.
- **코디세이 중계 서버를 통한 OpenAI GPT 호출 1회 성공**: `gpt-5.4-mini`, 입력711·출력221토큰. 지정 질문의 로딩·중복 전송 차단·답변·자동 저장·목록·새로고침·이전 대화 선택 후 동일 문답 복원을 확인했습니다. 답변의 최신 월2026-08/-813명, 두 기간 평균 -558/-551.42명 등은 전달 요약과 일치합니다.
- 새 시연 대화: `4bc508f3-e079-40d6-9174-4157e5a5e79f`, 제목 `[화면 연결 검증] 저장된 최신 월을 기준으로 최근 창원시 순이동 추세를 간단히 설명해줘.`. 원본128건과 기존 대화2건의 전체 값·생성/수정시각 해시는 동일하며, 새 시연1건을 더해 대화는 총3건입니다.
- 앱 소스·스타일·키·Firebase 설정 변경 없음. 기존 검사 도구의 승인 질문만 이번 프로세스에서 지정했고 1회 제한을 유지했습니다. 전체 테스트는 반복하지 않았습니다. 검증용 서버와 임시 자료는 정상 정리했으며 공개 API 주소는8002로 복원했습니다. 기존5500·8002·8000 서버는 유지했습니다.

근거: [API·DB 결과](.local/verification-13-14/final-api-results.json), [브라우저 결과](.local/verification-13-14/final-browser-results.json), [실제 GPT·보존 보고서](.local/frontend-ui-final-live-20261029-report.json), [정리·최종 서버 상태](.local/verification-13-14/final-results.json), [복원 화면](.local/verification-13-14/final-gpt-restored.jpg).

남은 수동 확인은 **격리 자료 수정 승인·자료 삭제 승인·격리 대화 삭제 승인**입니다. [버튼 순서와 기대 결과](.local/verification-13-14/MANUAL_CHECK.md)의 최신 안내를 사용하세요. 실제 GPT를 다시 호출할 필요는 없습니다. Render·Vercel 배포와 GitHub 작업은 진행하지 않았습니다.


## 13~14단계 UI/UX 통합 완료 — 2026-10-29

**13~14단계 완료.** 남아 있던 확인창3항목은 사용자의 실제 격리 브라우저 확인으로 통과했고, 이번 문구·스타일 변경 후 검수도 완료했습니다. 이전 자동화 시간초과 이력을 삭제하거나 자동화 성공으로 바꾸지 않았습니다.

- **사용자 확인:** 2042-02를 -12→-15로 수정해 평균 -6→-7.5 반영, 해당 자료 삭제로 목록2→1, 모의 질문 삭제로 이전 질문1→0, 삭제 완료 안내 표시.
- **추가 읽기 검증:** 격리 서버 기록의 PUT200·DELETE204 두 건, 남은2042-01/0명·평균0·질문0건 확인. 검사 서버 정상 종료와 소유 임시 자료 정리 후 원본128건·실제 질문 기록3건의 값/생성/수정시각 해시 동일.
- **디자인:** 실제 기존 가지마이소의 청록/짙은 글자/종이색 배경, 시스템 폰트, 작은 모서리·평면 카드를 계승했습니다. 통계4열→모바일2열과 기존 앱 구성을 유지했습니다. 입력 폼 규칙은 참고 사이트에 없으므로 앱의 기존 동작을 유지했습니다. [실제 파일 비교](.local/verification-13-14/ui-integration/DESIGN_REVIEW.md)
- **확정 문구:** 브랜드 ‘가지마이소’, 상단/시작 화면의 ‘가’ 아이콘 제거, ‘무엇이 궁금한가요?’, ASK AI, ‘AI에게 질문하기’, ‘질문하기’, ‘새 질문’, ‘이전 질문’, ‘질문 삭제’ 및 오류/완료 안내 통일. Hero는 ‘CHANGWON · POPULATION MOVEMENT’, ‘창원 인구이동 현황을 한눈에’, 지정 보조 설명 그대로 적용했습니다. 월별 순이동과 전체 인구 증감 구분 안내는 남겼습니다.
- **이번 검사:** 프론트엔드 회귀47/47 통과. 실제1440px/390px 화면에서 새 문구·정렬·가로 넘침 없음·버튼 글자·간격·입력창 접근 확인. 모바일 자료 수정/삭제 버튼44×44px. 질문 예시/Shift+Enter, PC/모바일 기존 질문 불러오기, 새로고침 동일 복원 확인. 최종 콘솔 오류0. 이번 실제 GPT 호출0회.
- **보존:** conversations API/모델/컬렉션과 api.js/config.js 변경 없음. Firebase·코디세이·키·기존 사용자 서버 변경 없음. 참고 프로젝트6개 파일 해시 동일. 정상 화면은 <http://127.0.0.1:5500/>, API 문서는 <http://127.0.0.1:8002/docs>입니다. 임시5501/8011은 검수 종료 후 닫았습니다.

최종 캡처: [PC 메인](.local/verification-13-14/ui-integration/pc-1440-main.jpg), [PC 질문](.local/verification-13-14/ui-integration/pc-1440-question.jpg), [모바일 메인](.local/verification-13-14/ui-integration/mobile-390-main.jpg), [모바일 질문](.local/verification-13-14/ui-integration/mobile-390-question.jpg), [모바일 입력](.local/verification-13-14/ui-integration/mobile-390-input.jpg), [모바일 자료 관리](.local/verification-13-14/ui-integration/mobile-390-data.jpg).

근거: [사용자 확인과 API 기록](.local/verification-13-14/ui-integration/manual-confirmation.json), [이번47개 검사](.local/verification-13-14/ui-integration/frontend-tests.json), [실제 화면 결과](.local/verification-13-14/ui-integration/browser-results.json), [원본/참고 파일 보존](.local/verification-13-14/ui-integration/preservation.json).

배포 전에는 공개 접근의 인증/권한 보호, 배포 환경의 비밀 설정·정확한 CORS/프론트 API 주소 및 코디세이 키 사용 조건을 확인하고 배포 후 검증해야 합니다. 이 작업에서는 Render·Vercel 배포, GitHub 푸시, 신규 기능 개발을 하지 않았습니다.


## 15단계 보안·배포 준비 및 추가 UI 수정

- `QUESTION / 새 질문 / 질문을 보내면 현재 저장 자료로 답변합니다.` 상단 안내 블록을 제거했습니다. 질문 삭제 버튼은 이전 질문 목록 아래에 유지합니다.
- 기존 질문 불러오기·새로고침 복원·새 질문 전환을 실제 브라우저에서 확인했습니다. 추가 GPT 호출은 0회입니다. 이번 PC 캡처는 실제 폭 1482px이며, 화면 크기 도구가 적용되지 않아 모바일 재검수는 하지 못했습니다. 기존 13~14단계 모바일 검수 기록과 구분합니다.
- 인증·요청 제한 및 관련 API 모의 테스트 80개, 프론트 테스트 47개 통과. 새 로컬 서버 HTTP 검증 통과 후 해당 프로세스만 종료했습니다.
- [비공개 GitHub 저장소](https://github.com/jojunsu98/gajimaiso-ai-assistant)에 초기 커밋 `1c78ea2` 업로드 및 원격 일치를 확인했습니다. 추적·스테이징·전체 커밋 blob 검사에서 실제 비밀값 미검출. .env·키 TXT·.venv·.local·로그는 제외됩니다.
- 원본 128건과 기존 질문 3건 목록 응답의 작업 전후 해시 일치. DB 쓰기·GPT 호출 없음. 기존 사용자 서버 유지.
- [Render 실행·환경변수·인증 연동 안내](DEPLOY_RENDER.md). Render 로그인은 완료됐으나 GitHub 앱의 저장소 접근 승인 및 실제 서비스 환경변수 입력·배포 검증은 남아 있습니다. **15단계 미완료**입니다.


### Render 연결 후 실제 배포 확인 — 2026-10-29

- 사용자가 GitHub 연결을 완료한 뒤 이미 생성된 Free/Singapore 서비스 `srv-dbhdk7afngtc73bck570`을 발견하여 재사용했습니다. 중복 서비스를 생성하지 않았습니다.
- 공개 백엔드 https://gajimaiso-ai-assistant.onrender.com 및 Swagger https://gajimaiso-ai-assistant.onrender.com/docs 확인. health/docs/openapi HTTP200, 실제 Swagger 제목·Authorize·보호 경로 보안 표시 확인.
- 초기 data/summary는 503 `database_unavailable`, 보호 요청은 403 `access_not_configured`: 비밀값 미설정 상태를 안전하게 차단하며 연결 성공으로 표시하지 않음.
- 실제 서비스의 자동 배포를 Off로 변경하고 시작 명령에 `--workers 1 --no-access-log`, 헬스체크 `/health` 설정. 공개 환경변수9개 저장 후 재빌드 `dep-dbhdmlafngtc73bcq80g` Live 확인. 배포 로그에서 해당 시작 명령 확인.
- 로컬 `.env` 기존 바이트를 보존하고 접근 인증 전용 APP_ACCESS_TOKEN을 추가 준비. Render의 서비스 계정 JSON·코디세이 키·같은 접근 토큰은 사용자 직접 입력 대기. 실제 키 값을 출력·커밋하지 않음.
- 이번 연결 후 작업의 실제 AI 호출0회, 실제 DB 쓰기0회. 사용자 로컬 서버 종료·재시작 없음. 전체 테스트 반복 실행 없음. 기존 원본 보존 결과 유지.
- 근거: `.local/verification-15/render-public-check.json`, `render-swagger.jpg`, `render-secret-form.jpg`, `access-token-setup.json`. 공개 URL의 서버 실행과 외부 서비스 연결 완료는 구분하며 15단계 미완료 유지. 16단계는 시작하지 않음.
