"""Pure summary tests; synthetic records are never sent to Firestore."""

from types import SimpleNamespace
import unittest

from pydantic import ValidationError

from app.schemas.summary import SummaryMetrics
from app.services.summary import LIMITATIONS, calculate_summary


def records(values, start="2024-09"):
    year, month = map(int, start.split("-"))
    start_index = (year - 1) * 12 + month - 1
    result = []
    for offset, value in enumerate(values):
        year_zero, month_zero = divmod(start_index + offset, 12)
        stamp = f"{year_zero + 1:04d}-{month_zero + 1:02d}"
        result.append(SimpleNamespace(
            id=f"changwon-net-{stamp}", date=f"{stamp}-01", value=value, memo="",
        ))
    return result


class SummaryTests(unittest.TestCase):
    def test_empty_data_has_explicit_nulls_and_zero_total(self):
        summary = calculate_summary([])
        self.assertEqual(summary.count, 0)
        self.assertIsNone(summary.period)
        self.assertIsNone(summary.latest)
        self.assertEqual(summary.metrics.model_dump(), {
            "total": 0, "average": None, "max": None, "min": None,
            "max_months": [], "min_months": [],
        })
        self.assertEqual(summary.trend.status, "insufficient_data")
        self.assertIsNone(summary.trend.recent_period)
        self.assertIsNone(summary.trend.previous_period)
        self.assertIsNone(summary.trend.difference)
        self.assertEqual(summary.quality.missing_months, [])

    def test_single_negative_record_has_no_minimum_count_rule(self):
        summary = calculate_summary(records([-7]))
        self.assertEqual(summary.count, 1)
        self.assertEqual(summary.metrics.total, -7)
        self.assertEqual(summary.metrics.average, -7.0)
        self.assertEqual(summary.metrics.max, -7)
        self.assertEqual(summary.metrics.min, -7)
        self.assertEqual(summary.metrics.max_months, ["2024-09"])
        self.assertEqual(summary.metrics.min_months, ["2024-09"])
        self.assertEqual(summary.latest.model_dump(), {"month": "2024-09", "value": -7})
        self.assertEqual(summary.trend.status, "insufficient_data")
        self.assertIn("부족", summary.trend.description)

    def test_zero_is_a_valid_value(self):
        summary = calculate_summary(records([0] * 24))
        self.assertEqual(summary.metrics.total, 0)
        self.assertEqual(summary.metrics.average, 0.0)
        self.assertEqual(summary.trend.status, "unchanged")
        self.assertEqual(summary.trend.difference, 0.0)

    def test_negative_improvement_is_increase(self):
        summary = calculate_summary(records([-100] * 12 + [-50] * 12))
        self.assertEqual(summary.trend.status, "increase")
        self.assertEqual(summary.trend.previous_average, -100.0)
        self.assertEqual(summary.trend.recent_average, -50.0)
        self.assertEqual(summary.trend.difference, 50.0)
        self.assertIn("순이동 수치가 상승", summary.trend.description)
        self.assertNotIn("순유입", summary.trend.description)

    def test_negative_worsening_is_decrease(self):
        summary = calculate_summary(records([-50] * 12 + [-100] * 12))
        self.assertEqual(summary.trend.status, "decrease")
        self.assertEqual(summary.trend.difference, -50.0)

    def test_different_monthly_values_with_equal_means_are_unchanged(self):
        summary = calculate_summary(records([-1] * 12 + [-2, 0] * 6))
        self.assertEqual(summary.trend.status, "unchanged")
        self.assertEqual(summary.trend.recent_average, -1.0)
        self.assertEqual(summary.trend.previous_average, -1.0)

    def test_all_tied_extreme_months_are_sorted(self):
        summary = calculate_summary(list(reversed(records([-2, -1, -2, -1]))))
        self.assertEqual(summary.metrics.max, -1)
        self.assertEqual(summary.metrics.max_months, ["2024-10", "2024-12"])
        self.assertEqual(summary.metrics.min_months, ["2024-09", "2024-11"])
        self.assertEqual(summary.period.model_dump(), {"start": "2024-09", "end": "2024-12"})

    def test_trend_is_anchored_to_latest_stored_month_not_today(self):
        summary = calculate_summary(records(range(24), start="2000-02"))
        self.assertEqual(summary.trend.recent_period.model_dump(), {"start": "2001-02", "end": "2002-01"})
        self.assertEqual(summary.trend.previous_period.model_dump(), {"start": "2000-02", "end": "2001-01"})
        self.assertEqual(summary.latest.month, "2002-01")

    def test_expected_snapshot_windows_are_calculated_from_latest(self):
        summary = calculate_summary(records([1] * 24))
        self.assertEqual(summary.trend.recent_period.model_dump(), {"start": "2025-09", "end": "2026-08"})
        self.assertEqual(summary.trend.previous_period.model_dump(), {"start": "2024-09", "end": "2025-08"})

    def test_recent_window_gap_prevents_comparison_even_with_more_than_24_rows(self):
        data = records([2] * 36, start="2023-09")
        del data[20]
        summary = calculate_summary(data)
        self.assertEqual(summary.count, 35)
        self.assertEqual(summary.metrics.total, 70)
        self.assertEqual(summary.quality.missing_months, ["2025-05"])
        self.assertEqual(summary.trend.status, "insufficient_data")
        self.assertIsNone(summary.trend.recent_average)
        self.assertIsNone(summary.trend.previous_average)
        self.assertIsNone(summary.trend.difference)
        self.assertIn("비교 구간 안", summary.trend.description)
        self.assertIn("2025-05", summary.trend.description)

    def test_older_gap_is_reported_but_does_not_invalidate_complete_window(self):
        data = records([2] * 36, start="2023-09")
        del data[5]
        summary = calculate_summary(data)
        self.assertEqual(summary.quality.missing_months, ["2024-02"])
        self.assertEqual(summary.trend.status, "unchanged")
        self.assertIn("비교 구간 이전", summary.trend.description)
        self.assertIn("최근 24개월 구간은 연속", summary.trend.description)

    def test_older_and_recent_gaps_are_distinguished(self):
        data = records([2] * 36, start="2023-09")
        data = [r for i, r in enumerate(data) if i not in (5, 20)]
        summary = calculate_summary(data)
        self.assertEqual(summary.quality.missing_months, ["2024-02", "2025-05"])
        self.assertEqual(summary.trend.status, "insufficient_data")
        self.assertIn("비교 구간 안", summary.trend.description)
        self.assertIn("비교 구간 이전", summary.trend.description)

    def test_twenty_three_months_are_insufficient(self):
        summary = calculate_summary(records([1] * 23))
        self.assertEqual(summary.trend.status, "insufficient_data")
        self.assertEqual(summary.quality.missing_months, [])
        self.assertIsNone(summary.trend.difference)
        self.assertIn("1개월이 부족", summary.trend.description)

    def test_average_and_difference_display_round_to_two_places(self):
        summary = calculate_summary(records([0] * 12 + [1] + [0] * 11))
        self.assertEqual(summary.metrics.average, 0.04)
        self.assertEqual(summary.trend.recent_average, 0.08)
        self.assertEqual(summary.trend.difference, 0.08)
        self.assertEqual(summary.trend.status, "increase")

    def test_direction_does_not_lose_small_difference_at_large_integer_scale(self):
        large = 2 ** 63 - 2
        values = [large] * 24
        values[-1] += 1
        summary = calculate_summary(records(values))
        self.assertEqual(summary.metrics.total, large * 24 + 1)
        self.assertEqual(summary.trend.status, "increase")
        self.assertEqual(summary.trend.difference, 0.08)
        # Display floats can coincide at this magnitude; direction remains exact.
        self.assertEqual(summary.trend.previous_average, summary.trend.recent_average)

    def test_fresh_input_is_reflected_without_a_cache(self):
        data = records([1] * 24)
        before = calculate_summary(data)
        data[-1].value = -11
        after = calculate_summary(data)
        self.assertEqual(before.metrics.total, 24)
        self.assertEqual(after.metrics.total, 12)
        self.assertEqual(after.latest.value, -11)
        self.assertEqual(before.trend.status, "unchanged")
        self.assertEqual(after.trend.status, "decrease")

    def test_valid_early_year_boundary_does_not_crash(self):
        summary = calculate_summary(records([1], start="0001-01"))
        self.assertEqual(summary.period.start, "0001-01")
        self.assertEqual(summary.trend.status, "insufficient_data")
        self.assertIsNone(summary.trend.recent_period)
        self.assertIsNone(summary.trend.previous_period)
        self.assertIsNone(summary.trend.difference)
        self.assertIn("날짜 범위", summary.trend.description)

    def test_first_complete_window_in_year_two_is_valid(self):
        summary = calculate_summary(records([1] * 24, start="0001-01"))
        self.assertEqual(summary.trend.status, "unchanged")
        self.assertEqual(summary.trend.previous_period.start, "0001-01")
        self.assertEqual(summary.trend.recent_period.start, "0002-01")

    def test_all_five_limitations_and_metric_identity_are_present(self):
        summary = calculate_summary(records([1]))
        self.assertEqual(summary.metric, "창원시 월별 순이동자수")
        self.assertEqual(summary.frequency, "monthly")
        self.assertEqual(summary.unit, "명")
        self.assertEqual(summary.limitations, list(LIMITATIONS))
        self.assertEqual(len(summary.limitations), 5)

    def test_duplicate_month_is_not_silently_collapsed(self):
        data = records([1])
        with self.assertRaisesRegex(ValueError, "duplicate_month"):
            calculate_summary(data + data)

    def test_integer_response_fields_reject_bool_and_float(self):
        for invalid in (True, 1.0, "1"):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                SummaryMetrics(total=invalid, average=1, max=1, min=1,
                               max_months=[], min_months=[])


if __name__ == "__main__":
    unittest.main()
