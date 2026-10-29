"""Validate the whole monthly CSV; access Firestore only with an explicit mode."""

import argparse
import codecs
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_SOURCE = BACKEND_ROOT / "data" / "source" / "changwon_migration_monthly_clean.csv"
MEMO = "창원시 월별 순이동자수(명)"
REQUIRED_COLUMNS = {"month", "region_code", "region_name", "net_migration"}
NUMERIC_COLUMNS = {
    "total_inflow", "total_outflow", "net_migration", "within_city_movement",
    "within_province_inflow", "within_province_outflow", "interprovince_inflow",
    "interprovince_outflow", "external_inflow", "external_outflow",
}


class MigrationValidationError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _fail(code, message):
    raise MigrationValidationError(code, message)


def _integer(value, row_number, column):
    try:
        number = Decimal(value)
    except InvalidOperation:
        _fail("invalid_number", f"{row_number}행 {column}: 숫자가 아닙니다.")
    if not number.is_finite():
        _fail("nonfinite_number", f"{row_number}행 {column}: NaN·무한대는 허용하지 않습니다.")
    if number != number.to_integral_value():
        _fail("fractional_number", f"{row_number}행 {column}: 소수 부분이 있는 값입니다.")
    if not -(2**63) <= number < 2**63:
        _fail("integer_range", f"{row_number}행 {column}: 정수 저장 범위를 벗어났습니다.")
    if column != "net_migration" and number < 0:
        _fail("negative_count", f"{row_number}행 {column}: 이동자수는 음수일 수 없습니다.")
    return int(number)


def validate_csv(path):
    """Return validated records and metadata without loading Firebase or writing files.

    Every row must be the 48120 Changwon whole-city series. Missing, repeated,
    conflicting or invalid observations stop the import; none are filled or dropped.
    """
    path = Path(path).resolve()
    try:
        raw = path.read_bytes()
    except OSError:
        _fail("source_unreadable", "CSV 파일을 읽을 수 없습니다. 지정 경로와 권한을 확인하세요.")
    encodings = ["utf-8-sig"] if raw.startswith(codecs.BOM_UTF8) else ["utf-8", "cp949"]
    content = None
    for encoding in encodings:
        try:
            content = raw.decode(encoding, errors="strict")
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        _fail("invalid_encoding", "지원 인코딩(UTF-8, CP949)으로 엄격하게 읽을 수 없습니다.")
    try:
        dialect = csv.Sniffer().sniff(content[:65536], delimiters=",;\t|")
        rows = list(csv.reader(io.StringIO(content, newline=""), dialect, strict=True))
    except csv.Error:
        _fail("invalid_csv", "CSV 구분자 또는 행 형식이 잘못됐습니다.")
    if not rows or not rows[0]:
        _fail("empty_csv", "CSV 헤더와 데이터가 필요합니다.")
    columns = rows[0]
    if any(not column.strip() for column in columns) or len(set(columns)) != len(columns):
        _fail("invalid_header", "열 이름이 비어 있거나 중복됐습니다.")
    if not REQUIRED_COLUMNS.issubset(columns):
        _fail("missing_columns", "month, region_code, region_name, net_migration 열이 필요합니다.")

    records_by_month = {}
    for row_number, cells in enumerate(rows[1:], start=2):
        if len(cells) != len(columns):
            _fail("row_width", f"{row_number}행: 헤더와 열 개수가 다릅니다.")
        if any(not value.strip() for value in cells):
            _fail("empty_cell", f"{row_number}행: 빈 값이 있습니다.")
        row = dict(zip(columns, cells))
        if row["region_code"] != "48120" or row["region_name"] != "창원시":
            _fail("wrong_region", f"{row_number}행: 창원시 전체(48120) 자료가 아닙니다.")
        month = row["month"]
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}", month) is None:
            _fail("invalid_month", f"{row_number}행: month는 YYYY-MM 형식이어야 합니다.")
        try:
            month_date = date(int(month[:4]), int(month[5:]), 1)
        except ValueError:
            _fail("invalid_month", f"{row_number}행: 유효한 연월이 아닙니다.")
        if month in records_by_month:
            _fail("duplicate_month", f"{row_number}행: 중복 월이 있습니다. 자동 병합하지 않습니다.")
        numbers = {
            column: _integer(row[column], row_number, column)
            for column in sorted(NUMERIC_COLUMNS.intersection(columns))
        }
        if {"total_inflow", "total_outflow"}.issubset(numbers):
            if numbers["total_inflow"] - numbers["total_outflow"] != numbers["net_migration"]:
                _fail("net_mismatch", f"{row_number}행: 전입-전출과 순이동 값이 다릅니다.")
        records_by_month[month] = {
            "id": f"changwon-net-{month}",
            "date": month_date.isoformat(),
            "value": numbers["net_migration"],
            "memo": MEMO,
        }
    months = sorted(records_by_month)
    if len(months) < 100:
        _fail("insufficient_months", f"서로 다른 유효 월이 {len(months)}개입니다. 최소 100개가 필요합니다.")
    month_numbers = [int(month[:4]) * 12 + int(month[5:]) - 1 for month in months]
    missing_count = month_numbers[-1] - month_numbers[0] + 1 - len(months)
    if missing_count:
        _fail("missing_months", f"시작·종료 월 사이에 {missing_count}개 누락 월이 있습니다. 보간하지 않습니다.")
    records = [records_by_month[month] for month in months]
    return {
        "metadata": {
            "source": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
            "encoding": encoding, "delimiter": dialect.delimiter, "columns": columns,
            "total_rows": len(rows) - 1, "valid_months": len(records),
            "start_month": months[0], "end_month": months[-1],
            "region_code": "48120", "region_name": "창원시", "unit": "명",
            "series": "월별 순이동자수", "representative_day": "01",
        },
        "quality": {
            "duplicate_months": 0, "missing_months": 0, "empty_cells": 0,
            "invalid_dates": 0, "nonnumeric_values": 0, "nonfinite_values": 0,
            "fractional_values": 0, "wrong_regions": 0,
        },
        "records": records,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="창원시 월별 순이동 CSV 검증 및 생성 전용 가져오기")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="CSV 검증만 수행 (기본값, DB 접속 없음)")
    modes.add_argument("--apply", action="store_true", help="검증 후 data 컬렉션에 신규 문서만 생성")
    modes.add_argument("--verify", action="store_true", help="저장된 대상 전체를 읽어 CSV와 비교 (쓰기 없음)")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="확인된 CSV 경로")
    parser.add_argument("--report", help=".local에 기록할 결과 JSON 파일명 (경로 제외)")
    args = parser.parse_args(argv)
    mode = "apply" if args.apply else "verify" if args.verify else "dry-run"
    report_name = args.report or f"migration-{mode}.json"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.json", report_name):
        parser.error("--report는 경로를 포함하지 않는 JSON 파일명이어야 합니다.")
    report_dir = PROJECT_ROOT / ".local"
    try:
        report_dir.mkdir(exist_ok=True)
        report_stream = (report_dir / report_name).open("w", encoding="utf-8", newline="\n")
    except OSError:
        print("결과 파일을 준비하지 못했습니다. DB 작업은 시작하지 않았습니다.")
        return 2

    report = {"mode": mode, "recorded_at_utc": datetime.now(timezone.utc).isoformat()}
    exit_code = 0
    try:
        validated = validate_csv(args.source)
        records = validated.pop("records")
        report.update(validated)
        if mode == "dry-run":
            report.update(status="ok", expected=len(records), created=0, skipped=0,
                          conflicts=[], verified_count=0, database_accessed=False)
        else:
            # No settings/credential imports occur until the entire input passes.
            if str(BACKEND_ROOT) not in sys.path:
                sys.path.insert(0, str(BACKEND_ROOT))
            from app.config import FirebaseError
            from app.services.firestore import get_firestore_client
            from app.services.migration_import import store_records, verify_records

            try:
                client = get_firestore_client()
            except FirebaseError as exc:
                report.update(status="configuration_error", error_code=exc.code)
                exit_code = 2
            else:
                operation = store_records if mode == "apply" else verify_records
                report.update(operation(client, records), database_accessed=True)
                exit_code = 0 if report["status"] == "ok" else 1
    except MigrationValidationError as exc:
        report.update(status="validation_error", error_code=exc.code, message=str(exc),
                      database_accessed=False)
        exit_code = 2
    except Exception:
        # SDK/transport exception strings are deliberately never printed or saved.
        report.update(status="execution_error", error_code="unexpected_execution_failure")
        exit_code = 1
    finally:
        with report_stream:
            json.dump(report, report_stream, ensure_ascii=False, indent=2)
            report_stream.write("\n")

    summary_keys = ("mode", "status", "expected", "created", "skipped", "verified_count",
                    "uncertain_count", "error_code", "message", "errors")
    summary = {key: report[key] for key in summary_keys if key in report}
    summary["conflict_count"] = len(report.get("conflicts", []))
    summary["missing_count"] = len(report.get("missing", []))
    summary["report"] = str(report_dir / report_name)
    print(json.dumps(summary, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
