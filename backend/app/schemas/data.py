"""Strict monthly observation contracts shared by the API and storage service."""

from datetime import date as calendar_date
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DataWrite(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    date: str = Field(
        pattern=r"^[0-9]{4}-[0-9]{2}-01$",
        description="유효한 YYYY-MM-01 문자열. 01은 월 대표일이며 하루치 관측값이 아닙니다.",
    )
    value: int = Field(
        ge=-(2**63), le=2**63 - 1,
        description="월별 순이동자수(명), 64비트 정수. 음수와 0 허용, 문자열·불리언·소수 거부.",
    )
    memo: str = Field(max_length=500, description="필수 문자열, 빈 문자열 허용, 최대 500자.")

    @field_validator("date")
    @classmethod
    def valid_month_date(cls, value: str) -> str:
        try:
            parsed = calendar_date.fromisoformat(value)
        except ValueError:
            raise ValueError("유효한 YYYY-MM-01 날짜가 필요합니다.") from None
        if parsed.day != 1:
            raise ValueError("월 대표일 01만 허용합니다.")
        return value


class DataRecord(DataWrite):
    id: str = Field(pattern=r"^changwon-net-[0-9]{4}-[0-9]{2}$", description="날짜의 월로 정해지는 문서 ID.")

    @model_validator(mode="after")
    def consistent_month(self):
        if self.id != f"changwon-net-{self.date[:7]}":
            raise ValueError("문서 ID와 날짜의 월이 일치해야 합니다.")
        return self


class DataList(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    items: list[DataRecord]
    count: int = Field(ge=0)


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    detail: ErrorDetail
