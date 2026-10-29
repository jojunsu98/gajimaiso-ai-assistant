"""Response contracts for a summary of the currently stored monthly records."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class SummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MonthPeriod(SummaryModel):
    start: str = Field(description="시작 월(YYYY-MM)")
    end: str = Field(description="종료 월(YYYY-MM)")


class SummaryMetrics(SummaryModel):
    total: StrictInt = Field(description="존재하는 월별 순이동자수의 합계(명)")
    average: float | None = Field(description="월평균 순이동자수, 소수점 둘째 자리까지")
    max: StrictInt | None = Field(description="월별 순이동 최댓값; 음수일 수도 있음")
    min: StrictInt | None = Field(description="월별 순이동 최솟값")
    max_months: list[str] = Field(description="최댓값을 기록한 모든 월")
    min_months: list[str] = Field(description="최솟값을 기록한 모든 월")


class LatestMonth(SummaryModel):
    month: str = Field(description="최신 저장 월(YYYY-MM), 현재 달과 다를 수 있음")
    value: StrictInt


class TrendSummary(SummaryModel):
    method: Literal["latest_12m_mean_vs_previous_12m_mean"] = (
        "latest_12m_mean_vs_previous_12m_mean"
    )
    status: Literal["increase", "decrease", "unchanged", "insufficient_data"]
    recent_period: MonthPeriod | None
    previous_period: MonthPeriod | None
    recent_average: float | None
    previous_average: float | None
    difference: float | None
    description: str


class SummaryQuality(SummaryModel):
    missing_months: list[str] = Field(description="전체 저장 기간의 시작~종료 월 사이 누락 월")


class SummaryResponse(SummaryModel):
    metric: Literal["창원시 월별 순이동자수"] = "창원시 월별 순이동자수"
    unit: Literal["명"] = "명"
    frequency: Literal["monthly"] = "monthly"
    period: MonthPeriod | None
    count: StrictInt = Field(ge=0, description="현재 저장된 월별 자료 개수")
    metrics: SummaryMetrics
    latest: LatestMonth | None
    trend: TrendSummary
    quality: SummaryQuality
    limitations: list[str]
