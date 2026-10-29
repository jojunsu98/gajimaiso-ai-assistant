"""Pure calculations over validated records; no CSV, database, cache or clock."""

from fractions import Fraction
from typing import TYPE_CHECKING

from app.schemas.summary import (
    LatestMonth,
    MonthPeriod,
    SummaryMetrics,
    SummaryQuality,
    SummaryResponse,
    TrendSummary,
)

if TYPE_CHECKING:
    from app.schemas.data import DataRecord


LIMITATIONS = (
    "순이동은 전입과 전출의 차이이며 전체 인구 증감과 동일하지 않음",
    "최신 저장 월까지의 분석이며 현재 달 실적을 의미하지 않음",
    "이 데이터만으로 이동 원인이나 특정 정책 효과를 확정할 수 없음",
    "음수의 상승은 순유출 규모 감소일 수 있으며 순유입 전환과 다름",
    "사용자가 수정한 저장값은 원본 공식 통계와 달라질 수 있음",
)


def _month_index(date: str) -> int:
    return (int(date[:4]) - 1) * 12 + int(date[5:7]) - 1


def _month_name(index: int) -> str:
    year_zero, month_zero = divmod(index, 12)
    return f"{year_zero + 1:04d}-{month_zero + 1:02d}"


def _period(start: int, end: int) -> MonthPeriod | None:
    # Python dates have no year zero. Keep unrepresentable windows explicit.
    if start < 0:
        return None
    return MonthPeriod(start=_month_name(start), end=_month_name(end))


def _display(value: Fraction) -> float:
    # Fraction keeps both arithmetic and rounding independent of float precision.
    return float(round(value, 2))


def _trend(values: dict[int, int], missing: list[int]) -> TrendSummary:
    if not values:
        return TrendSummary(
            status="insufficient_data", recent_period=None, previous_period=None,
            recent_average=None, previous_average=None, difference=None,
            description="저장된 월별 자료가 없어 최근 12개월과 직전 12개월 평균을 비교할 수 없습니다.",
        )

    latest = max(values)
    first = min(values)
    recent_start = latest - 11
    previous_start = latest - 23
    recent_period = _period(recent_start, latest)
    previous_period = _period(previous_start, recent_start - 1)
    missing_window = [i for i in range(max(0, previous_start), latest + 1) if i not in values]
    older_missing = [i for i in missing if i < previous_start]
    basis = f"최신 저장 월 {_month_name(latest)}을 기준으로 최근 12개월과 직전 12개월 평균을 비교합니다."

    if previous_start < 0 or missing_window:
        reasons = []
        if previous_start < 0:
            reasons.append("비교 구간이 유효한 날짜 범위(0001년 이후)보다 앞서므로 24개월 자료가 부족합니다")
        before_first = [i for i in missing_window if i < first]
        internal_missing = [i for i in missing_window if i >= first]
        if before_first:
            reasons.append(f"저장 시작 월 이전의 자료 {len(before_first)}개월이 부족합니다")
        if internal_missing:
            names = ", ".join(_month_name(i) for i in internal_missing)
            reasons.append(f"최근 24개월 비교 구간 안에 누락 월이 있습니다: {names}")
        if older_missing:
            reasons.append(f"별도로 비교 구간 이전에도 누락 월 {len(older_missing)}개가 있습니다")
        return TrendSummary(
            status="insufficient_data", recent_period=recent_period,
            previous_period=previous_period, recent_average=None,
            previous_average=None, difference=None,
            description=f"{basis} {'; '.join(reasons)}. 누락값을 채우지 않고 비교값을 제공하지 않습니다.",
        )

    recent = Fraction(sum(values[i] for i in range(recent_start, latest + 1)), 12)
    previous = Fraction(sum(values[i] for i in range(previous_start, recent_start)), 12)
    difference = recent - previous
    if difference > 0:
        status, direction = "increase", "순이동 수치가 상승했습니다"
    elif difference < 0:
        status, direction = "decrease", "순이동 수치가 하락했습니다"
    else:
        status, direction = "unchanged", "두 구간의 평균이 동일합니다"
    assert recent_period is not None and previous_period is not None
    description = (
        f"{basis} 최근 {recent_period.start}~{recent_period.end}와 "
        f"직전 {previous_period.start}~{previous_period.end}의 평균 차이를 "
        f"반올림 전에 판정한 결과, {direction}. 최근 24개월 구간은 연속합니다."
    )
    if older_missing:
        description += f" 비교 구간 이전의 누락 월 {len(older_missing)}개는 quality.missing_months에 표시합니다."
    return TrendSummary(
        status=status, recent_period=recent_period, previous_period=previous_period,
        recent_average=_display(recent), previous_average=_display(previous),
        difference=_display(difference), description=description,
    )


def calculate_summary(records: list["DataRecord"]) -> SummaryResponse:
    """Summarize validated monthly records from one current-data read."""
    values: dict[int, int] = {}
    for record in records:
        month = _month_index(record.date)
        if month in values:
            # The storage service also checks this. Never hide duplicate months.
            raise ValueError("duplicate_month")
        values[month] = record.value

    count = len(values)
    if not count:
        return SummaryResponse(
            period=None, count=0,
            metrics=SummaryMetrics(total=0, average=None, max=None, min=None,
                                   max_months=[], min_months=[]),
            latest=None, trend=_trend(values, []),
            quality=SummaryQuality(missing_months=[]), limitations=list(LIMITATIONS),
        )

    months = sorted(values)
    first, latest = months[0], months[-1]
    missing = [i for i in range(first, latest + 1) if i not in values]
    total = sum(values.values())
    maximum, minimum = max(values.values()), min(values.values())
    return SummaryResponse(
        period=_period(first, latest), count=count,
        metrics=SummaryMetrics(
            total=total, average=_display(Fraction(total, count)),
            max=maximum, min=minimum,
            max_months=[_month_name(i) for i in months if values[i] == maximum],
            min_months=[_month_name(i) for i in months if values[i] == minimum],
        ),
        latest=LatestMonth(month=_month_name(latest), value=values[latest]),
        trend=_trend(values, missing),
        quality=SummaryQuality(missing_months=[_month_name(i) for i in missing]),
        limitations=list(LIMITATIONS),
    )
