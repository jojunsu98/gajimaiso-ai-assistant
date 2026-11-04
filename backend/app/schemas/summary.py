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
    # Synthetic 24-month example; never read from the production database.
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "examples": [
            {'metric': '창원시 월별 순이동자수',
             'unit': '명',
             'frequency': 'monthly',
             'period': {'start': '2042-02', 'end': '2044-01'},
             'count': 24,
             'metrics': {'total': -324,
                         'average': -13.5,
                         'max': -12,
                         'min': -15,
                         'max_months': ['2043-02',
                                        '2043-03',
                                        '2043-04',
                                        '2043-05',
                                        '2043-06',
                                        '2043-07',
                                        '2043-08',
                                        '2043-09',
                                        '2043-10',
                                        '2043-11',
                                        '2043-12',
                                        '2044-01'],
                         'min_months': ['2042-02',
                                        '2042-03',
                                        '2042-04',
                                        '2042-05',
                                        '2042-06',
                                        '2042-07',
                                        '2042-08',
                                        '2042-09',
                                        '2042-10',
                                        '2042-11',
                                        '2042-12',
                                        '2043-01']},
             'latest': {'month': '2044-01', 'value': -12},
             'trend': {'method': 'latest_12m_mean_vs_previous_12m_mean',
                       'status': 'increase',
                       'recent_period': {'start': '2043-02', 'end': '2044-01'},
                       'previous_period': {'start': '2042-02', 'end': '2043-01'},
                       'recent_average': -12.0,
                       'previous_average': -15.0,
                       'difference': 3.0,
                       'description': '최신 저장 월 2044-01을 기준으로 최근 12개월과 직전 12개월 평균을 비교합니다. 최근 '
                                      '2043-02~2044-01와 직전 2042-02~2043-01의 평균 차이를 반올림 전에 판정한 결과, 순이동 수치가 '
                                      '상승했습니다. 최근 24개월 구간은 연속합니다.'},
             'quality': {'missing_months': []},
             'limitations': ['순이동은 전입과 전출의 차이이며 전체 인구 증감과 동일하지 않음',
                             '최신 저장 월까지의 분석이며 현재 달 실적을 의미하지 않음',
                             '이 데이터만으로 이동 원인이나 특정 정책 효과를 확정할 수 없음',
                             '음수의 상승은 순유출 규모 감소일 수 있으며 순유입 전환과 다름',
                             '사용자가 수정한 저장값은 원본 공식 통계와 달라질 수 있음']}
        ]
    })
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
