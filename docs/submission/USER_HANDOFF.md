# 사용자가 마지막으로 확인할 사항

## 1. 저장소 공개 전환

사용자가 직접 진행하기로 한 작업입니다. `jojunsu98/gajimaiso-ai-assistant` 공개 전환 후 로그아웃한 창에서 README와 필수 캡처3개가 열리는지 확인하세요. 이번 작업 중 조회 시점에는 private였고 에이전트가 공개 범위를 바꾸지는 않았습니다.

실제 키·서비스 계정 파일·.env·.local 전체를 추가하지 마세요. 새 제출 파일은 비밀값/대표 키 패턴 및 이미지 육안 검사를 마쳤으며 기존 이력 검증은 과거 근거를 재사용했습니다.

## 2. 보호 기능 평가 방식

저장소 공개와 웹 앱 접근 권한은 별개입니다. 자료·요약은 공개지만 이전 질문·새 질문·자료 변경에는 관리 접근 토큰이 필요합니다.

담당자가 캡처·코드·직접 화면 시연으로 평가하는지, 보호 기능 직접 접속도 요구하는지 확인하세요. 직접 접속이 필요할 때만 담당자의 비공개 전달 경로와 제공 범위를 확인합니다. 이 토큰은 원본 수정/삭제도 가능한 단일 관리 권한이므로 공개 README·댓글·채팅에 쓰지 않습니다. GPT 키나 Firebase 서비스 계정 키를 평가자에게 제공할 필요는 없습니다.

## 3. 실제 제출

학습 사이트의 과제 제출 화면에서 아래 링크·캡처를 등록하고 접수 완료 표시를 확인하세요. 현재 대화에는 제출 폼 주소가 없어 자동 제출하지 않았습니다.

- GitHub: https://github.com/jojunsu98/gajimaiso-ai-assistant
- 웹: https://gajimaiso-ai-assistant.vercel.app
- 백엔드: https://gajimaiso-ai-assistant.onrender.com
- Swagger: https://gajimaiso-ai-assistant.onrender.com/docs
- 캡처1: `06-gpt-summary-live-2026-11-04.jpg`
- 캡처2: `08-crud-create-result-2026-11-04.jpg`
- 캡처3: `07-history-restored-live-2026-11-04.jpg`

캡처 경로는 `docs/submission/screenshots/`입니다. 별도 파일명 규정은 제공된 원문에 없으므로 제출 화면이 지정한 경우에만 적용합니다. 접수 완료 화면/제출 번호를 보관한 뒤20단계를 완료로 표시하세요.

## 제출 설명문

가지마이소창원 AI 비서는 창원시 월별 순이동128건을 Firestore에 저장하고, 서버 요약을 GPT 시스템 프롬프트에 주입해 답변하는 웹 서비스입니다. FastAPI 백엔드는 Render, HTML/CSS/JavaScript 프론트엔드는 Vercel에 배포했습니다. 자료 CRUD·요약, 실제 GPT 응답과 자동 저장, 이전 대화 불러오기를 구현·검증했습니다. 채팅·복원 캡처는 운영 사이트의 기존 실제 GPT 답변을 불러온 것이며, CRUD 캡처는 원본 보호를 위한 실제 Firestore 격리 컬렉션의 추가 결과입니다. 자료 조회는 공개이고 보호 기능은 관리 접근 토큰을 사용합니다.
