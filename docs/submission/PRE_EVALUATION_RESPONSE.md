# 네이토 사전평가 보완 — 2026-11-04

사용자가 제공한 12:37:07 평가 결과는 **13/18(72%)**, 실패 항목은 **1·4·5·6·11**입니다. 아래는 소스와 기존 실행 기록을 다시 대조한 보완 내역이며, 재평가 점수나 통과 확정이 아닙니다. 남은 사전평가 1회는 실행하지 않았습니다. 평가 안내에 따라 이미지에만 의존하지 않고 Markdown과 코드로 근거를 제공합니다.

## 18개 항목 대조

| 항목 | 기존 판정 | 보완 및 확인 가능한 근거 |
| --- | --- | --- |
| 1 배포 URL | FAIL | README 첫 부분에 Vercel·Render·Swagger 주소. [build.mjs](../../frontend/build.mjs)가 빌드 환경변수로 운영 config.js 생성. 소스 config.js는 로컬 개발 전용이며 운영 URL 누락이 아님 |
| 2 Swagger 예시 | PASS | [요약 스키마](../../backend/app/schemas/summary.py), [채팅 스키마](../../backend/app/schemas/chat.py)에 OpenAPI examples 추가. 아래 요청/응답 설명 참조 |
| 3 CRUD 저장 실패 | PASS | [app.js](../../frontend/app.js)의 saveData: 성공 응답 후에만 폼 초기화·목록/요약 갱신. 실패 시 입력 보존·오류 안내·조작 잠금 해제. 불명확한 결과는 조회 후 판단 |
| 4 요약 주입 | FAIL | [ChatService.chat](../../backend/app/services/chat.py)의 calculate_summary → instructions → ai_service.generate, [OpenAIService.generate](../../backend/app/services/openai_client.py)의 system 메시지. README에 핵심 코드 발췌 |
| 5 자동 저장 | FAIL | 같은 ChatService에서 create_chat/append_chat 후 saved=True 반환. [실제 Render GPT 기록](evidence/render-gpt-2026-10-29.json): 요청1회·저장 true·상세 일치·목록1회 확인 |
| 6 모바일 CSS | FAIL | [styles.css](../../frontend/styles.css)에 1000·760·420px 및 접근 입력용600px 미디어 쿼리 존재. README에 규칙 발췌. [기존 화면 검증](evidence/responsive-browser-2026-10-29.json) 재사용 |
| 7 의존성 주입 | PASS | 아래 더미 예시와 [test_chat_api.py](../../backend/tests/test_chat_api.py)의 FakeAI·FakeClient·dependency_overrides 연결 위치 설명 |
| 8 컬렉션 설계 | PASS | 아래 data/conversations 분리·권한·크기·백업 미확인 범위 설명 |
| 9 스키마 연결 | PASS | GET summary는 요청 본문 없음. POST chat은 message/conversation_id만 전달. OpenAPI examples와 아래 프론트 연결 예시 |
| 10 주입 담당 | PASS | 프론트는 질문만 전송하며 백엔드가 최신 저장 자료를 읽어 요약 주입. 클라이언트 제공 통계를 신뢰하지 않음 |
| 11 주입 장단점·비용 | FAIL | README에 토큰 절감 원리·정보 손실·갱신 시점·오답 가능성·실제 제한값과 비용 한계 추가 |
| 12 순수 요약 API | PASS | SummaryResponse OpenAPI 예시 추가. [summary.py](../../backend/app/services/summary.py)는 DB·AI 호출 없는 순수 계산 |
| 13 자동 저장 실패 | PASS | 아래 saved=false·이전 질문 조회·자동 GPT 재호출 금지·복구 제한 설명 |
| 14 배포 환경변수 | PASS | README에 Render/Vercel 설정 순서·위치 명시. [상세 Render 안내](../../DEPLOY_RENDER.md) |
| 15 콜드스타트 | PASS | README의65초 조회 대기·수동 조회 재시도. /health 사전 조회 가능. 주기적 워밍·GPT 자동 재시도는 구현하지 않음 |
| 16 CORS | PASS | README에 로컬·Vercel 실제 origin 목록. 와일드카드 불허, CORS는 인증 대체 수단이 아님 |
| 17 검증·XSS | PASS | 아래 textContent 렌더링과 서버의 공통422 응답 설명. 임의의 특수문자 삭제는 하지 않음 |
| 18 요약 변경 지점 | PASS | 아래 _trend의12개월·24개월 구간 및 변경 시 함께 수정할 스키마·표시·검사 위치 설명 |

## API 예시와 프론트 연결

OpenAPI examples는 **형식 설명용 가상 값**이며 실제 GPT 생성 기록이 아닙니다. 요약 예시는2042-02~2044-01의 가상24개월 자료(앞12개월 -15명, 뒤12개월 -12명)이며 운영 자료128건과 구분합니다. 채팅 요청/응답 예시의 가상 날짜2044-01도 실제 운영 통계가 아닙니다.

```http
GET /api/data/summary
```

본문·쿼리 파라미터 없이 현재 저장 자료 요약을 받습니다. 응답 필드는 metric/unit/frequency/period/count/metrics/latest/trend/quality/limitations이며 전체 예시는 [SummaryResponse](../../backend/app/schemas/summary.py)에 있습니다. 빈 DB에서 채팅하면 data_empty(409)로 GPT 호출 전에 차단합니다.

```json
{"message":"최근 저장된 데이터의 추세와 해석 한계를 알려줘.","conversation_id":null}
```

이 본문을 인증된 `POST /api/chat`으로 보냅니다. 이어가기는 기존 대화 UUID를 사용합니다. 아래는 문서용 가상 응답입니다.

```json
{
  "conversation_id": "00000000-0000-4000-8000-000000000001",
  "reply": "문서용 가상 예시: 2044-01 자료 1건은 -12명이며 24개월 비교 자료가 부족합니다.",
  "saved": true,
  "data_period": {"start": "2044-01", "end": "2044-01"},
  "model": "gpt-5.4-mini",
  "usage": {"input_tokens": 100, "output_tokens": 40}
}
```

[frontend/app.js](../../frontend/app.js)에서 요약은 `api('/api/data/summary')`의 period/count/trend 등을 표시하고, 채팅은 아래처럼 질문과 ID만 보냅니다. 화면의 summary를 요청에 넣지 않아도 서버에서 다시 계산하므로 요약 주입이 누락된 것이 아닙니다.

```javascript
const response = await api("/api/chat", {
  method: "POST", kind: "chat",
  body: { message: question, conversation_id: conversationId }
});
```

## 저장 실패와 재시도 규격

- 자료 추가/수정: 서버 성공 전에 목록을 낙관적으로 변경하지 않습니다. 실패 시 기존 목록·폼 입력을 유지하고 finally에서 버튼 잠금을 풉니다. 성공 후 조회 실패는 조회 오류로 표시되므로 자료를 재생성하지 말고 목록·요약을 새로 조회합니다.
- 자료 요청 시간초과/연결 오류: 이미 저장되었을 가능성을 안내하며 목록을 먼저 확인합니다. 같은 월 중복 생성은409로 차단합니다.
- GPT 생성 성공 후 저장 확인 실패:503 `chat_save_failed`, 최상위 `saved:false`; 충돌은409 `conversation_changed`, `saved:false`입니다. 서버는 저장 확인 전 성공 응답을 보내지 않습니다.
- 프론트는 이전 질문 목록을 새로 조회하도록 안내하고 GPT를 자동 재호출하지 않습니다. 브라우저 시간초과만으로 서버 저장 실패를 단정하지 않습니다. 저장된 기록이 없으면 생성 답변을 복구하는 별도 큐/재저장 API는 없으며, 새 질문은 새 과금 요청일 수 있습니다.
- [main.py](../../backend/app/main.py)의422는 `detail.code=validation_error`와 고정 한국어 안내를 반환합니다. 원본 입력·예외·비밀값은 오류 응답에 반영하지 않습니다. 프론트의 명확한 로컬 검증 안내와 서버 오류 코드별 안전한 안내를 사용합니다.

## 의존성 주입과 오프라인 더미

[routers/chat.py](../../backend/app/routers/chat.py)의 get_chat_service는 데이터·대화 서비스를 Depends로 받아 ChatService에 전달합니다. 아래는 실제 [test_chat_api.py](../../backend/tests/test_chat_api.py)의 구성에서 발췌한 연결 예시입니다. 이 문서 작업에서 기존 모의 GPT 검사를 재실행하지 않았습니다.

```python
self.firebase = FakeClient()  # 테스트 파일의 메모리 저장소
self.conversations = ConversationService(self.firebase)
self.data = FakeDataService()
self.ai = FakeAI()  # generate가 AIResult를 반환하고 네트워크를 사용하지 않음
self.chat = ChatService(self.conversations, self.data, self.ai)
self.app.dependency_overrides[get_chat_service] = lambda: self.chat
```

인증 의존성 해제는 해당 오프라인 테스트 안에서만 적용합니다. 운영 앱에는 적용하지 않습니다. SDK 경계 더미는 [test_openai_client.py](../../backend/tests/test_openai_client.py)의 `OpenAIService(settings, client=Mock())` 주입을 참고합니다.

## Firestore 컬렉션과 운영 범위

- `data`: 월별 문서 ID `changwon-net-YYYY-MM`, date/value/memo. 같은 월 중복을 create로 막고 월 변경을 허용하지 않습니다. 매번 현재 저장값 전체를 읽어 요약하므로128건 규모에서는 단순하지만 큰 데이터에서는 읽기 비용·지연이 증가합니다.
- `conversations`: 서버 UUID별 문답 배열과 생성/수정시각, 마지막 요약·모델·사용량. 새 대화 create, 기존 대화는 갱신시각 조건부 update로 충돌을 감지합니다. 한 문서에서 문답 쌍을 유지하기 쉽지만 문서 크기·동시 수정 제약이 있어 메시지 수/256KiB payload 제한과 생성 전 저장 여유 검사를 둡니다.
- 서버만 컬렉션을 선택합니다. HTTP 입력으로 컬렉션명을 받지 않습니다. 격리 검증은 별도 서버 구성으로 테스트 전용 컬렉션을 주입합니다. 백업이나 운영 복제본으로 취급하지 않습니다.
- Firebase Admin은 서버의 서비스 계정 권한으로 동작하므로 브라우저의 Firestore 규칙만으로 보호된다고 가정하지 않습니다. HTTP 변경/대화 API에 관리 토큰을 적용하며 사용자별 권한 분리는 없습니다.
- 이 저장소의 증거로 자동 백업·PITR·복제 정책·IAM 최소권한 설정의 활성화를 확인할 수 없습니다. 운영 확장 시 관리 콘솔에서 별도 확인할 사항입니다. 내보내기와 복원 훈련도 이번에 실행하지 않았습니다.

## XSS·입력 처리

질문·답변·메모는 [app.js](../../frontend/app.js)의 element 함수에서 `textContent`로 삽입합니다. HTML로 해석하거나 `innerHTML`에 사용자 문자열을 넣지 않으며, 한국어·기호를 무조건 삭제하는 방식은 사용하지 않습니다. 날짜/정수/길이/역할/ID는 Pydantic과 프론트에서 확인합니다. 메모는 GPT에 주입하지 않고 서버가 만든 집계 지표만 사용합니다. 향후 Markdown/HTML 렌더러를 추가한다면 별도의 HTML 정화 정책이 필요합니다.

## 요약 계산을 바꾸는 위치

[services/summary.py](../../backend/app/services/summary.py)의 `_trend`에서 `recent_start=latest-11`, `previous_start=latest-23`, 각 평균의 분모12로 두 구간을 정합니다. 현재 환경변수로 비교 기간을 조절하는 기능은 없습니다. 변경하려면 이 계산과 [schemas/summary.py](../../backend/app/schemas/summary.py)의 method Literal·설명·OpenAPI 예시, 프론트의12개월 안내, [test_summary.py](../../backend/tests/test_summary.py)의 구간/누락월 기대값을 함께 변경해야 합니다. 최신 저장 월 기준·누락값 미보간·반올림 전 증감 판정은 유지해야 할 계약입니다.

## 검증 범위

공개 저장소/README/이미지의 비로그인 접근은 이번에 직접 확인했습니다. 기존 GPT·CRUD·모바일 검사는 앞선 성공 기록을 재사용했습니다. 추가한 OpenAPI 예시는 네트워크 연결을 차단한 상태에서 생성 문서의 요청/응답3개를 모델로 검증했고, 가상 요약은 순수 계산 결과와 일치했습니다. 최초 null 예시의 필드가 생성 문서에서 누락되는 문제는 완전한 가상 예시로 수정한 뒤 재검증했습니다.

이후 `7a87f1f1cc7cc2c86c222754ed195e381fac6bcd`를 기존 Render 서비스에 수동 배포해 **Deploy succeeded / Live**를 확인했습니다. 공개 `/openapi.json` HTTP200과 예시3개가 검증된 로컬 문서와 일치합니다. [검증 결과](pre-evaluation-verification-2026-11-04.json), [배포 완료 화면](screenshots/09-openapi-deployed-2026-11-04.jpg). 이번 보완의 GPT 호출·DB 읽기/쓰기는0회이고 기존 비밀값·환경변수는 변경하지 않았습니다. 사전평가 재실행·동료평가 요청·최종 제출 접수는 수행하지 않았습니다.
