from fastapi import APIRouter

router = APIRouter(tags=["서버 상태"])


@router.get(
    "/health",
    summary="서버 응답 확인",
    description="서버 자체의 응답만 확인합니다. Firebase나 AI 연결 성공을 의미하지 않습니다.",
)
def get_health() -> dict[str, str]:
    return {"status": "ok"}
