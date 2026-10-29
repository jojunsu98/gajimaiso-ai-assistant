"""Synchronous routes keep blocking Firestore I/O in FastAPI's worker threads."""

from typing import Annotated
from fastapi import APIRouter, Depends, Path, Response

from app.config import FirebaseError
from app.schemas.data import DataList, DataRecord, DataWrite, ErrorResponse
from app.schemas.summary import SummaryResponse
from app.services.data import DataService, DataServiceError
from app.services.summary import calculate_summary
from app.security import require_access


def get_data_service() -> DataService:
    # Keep app startup, /health, /docs, and OpenAPI independent of Firebase keys.
    try:
        from app.services.firestore import get_firestore_client
        return DataService(get_firestore_client())
    except FirebaseError:
        raise DataServiceError(503, "database_unavailable", "데이터베이스 연결 또는 서버 설정을 확인해야 합니다.") from None
    except Exception:
        raise DataServiceError(500, "internal_error", "요청 처리 중 서버 오류가 발생했습니다.") from None


router = APIRouter(
    prefix="/api/data", tags=["월별 인구이동 데이터"],
    responses={
        422: {"model": ErrorResponse, "description": "입력 형식 오류 또는 지원하지 않는 월 변경"},
        503: {"model": ErrorResponse, "description": "DB 연결 불가 또는 서버 설정 오류"},
        500: {"model": ErrorResponse, "description": "저장 데이터 무결성 오류 또는 예상하지 못한 오류"},
    },
)
Service = Annotated[DataService, Depends(get_data_service)]
DocumentId = Annotated[str, Path(pattern=r"^changwon-net-[0-9]{4}-(0[1-9]|1[0-2])$", description="변경할 수 없는 월별 문서 ID")]


@router.post("", status_code=201, response_model=DataRecord, summary="월별 기록 생성", dependencies=[Depends(require_access)],
             description="날짜로 문서 ID를 결정하며 기존 같은 월이 있으면 덮어쓰지 않습니다.",
             responses={409: {"model": ErrorResponse, "description": "같은 월이 이미 존재"}})
def create_data(payload: DataWrite, service: Service):
    return service.create_data(payload)


@router.get("", response_model=DataList, summary="월별 기록 전체 조회",
            description="날짜 오름차순으로 현재 저장 자료 전체와 실제 개수를 반환합니다.")
def list_data(service: Service):
    items = service.list_data()
    return DataList(items=items, count=len(items))


@router.get("/summary", response_model=SummaryResponse, summary="현재 저장 자료 요약",
            description="DB를 한 번 읽어 합계·평균·극값·누락 월 및 최신 월 기준 12개월 평균 비교를 계산합니다.")
def data_summary(service: Service):
    return calculate_summary(service.list_data())


@router.put("/{id}", response_model=DataRecord, summary="기존 월별 기록 전체 수정", dependencies=[Depends(require_access)],
            description="date/value/memo를 모두 받습니다. 월 변경과 없는 문서의 신규 생성은 지원하지 않습니다.",
            responses={404: {"model": ErrorResponse, "description": "문서 없음"},
                       409: {"model": ErrorResponse, "description": "다른 요청과 수정 충돌"}})
def update_data(id: DocumentId, payload: DataWrite, service: Service):
    return service.update_data(id, payload)


@router.delete("/{id}", status_code=204, response_class=Response, summary="월별 기록 1개 삭제", dependencies=[Depends(require_access)],
               responses={404: {"model": ErrorResponse, "description": "문서 없음"},
                          409: {"model": ErrorResponse, "description": "다른 요청과 삭제 충돌"}})
def delete_data(id: DocumentId, service: Service):
    service.delete_data(id)
    return Response(status_code=204)
