"""Explicit live API check: production data is read-only, CRUD is isolated.

Run with --live only after the offline suite succeeds. No normal test discovery
or a no-argument invocation initializes Firebase or contacts the network.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
SOURCE = BACKEND_ROOT / "data" / "source" / "changwon_migration_monthly_clean.csv"
REPORT = PROJECT_ROOT / ".local" / "data-api-live.json"
REQUEST_TIMEOUT = 10
sys.path.insert(0, str(BACKEND_ROOT))


class LiveCheckError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise LiveCheckError(code)


def month_index(month):
    return int(month[:4]) * 12 + int(month[5:7]) - 1


def month_string(index):
    year, zero_month = divmod(index, 12)
    return f"{year:04d}-{zero_month + 1:02d}"


def independent_source_summary(source=SOURCE):
    """Independent oracle: standard csv/Fraction, never the app's summary function."""
    source = Path(source)
    payload = source.read_bytes()
    rows = list(csv.DictReader(payload.decode("utf-8-sig").splitlines()))
    expected = {}
    for row in rows:
        month = row["month"]
        require(row["region_code"] == "48120" and row["region_name"] == "창원시", "source_region_mismatch")
        require(month_string(month_index(month)) == month, "source_month_invalid")
        require(month not in expected, "source_duplicate_month")
        value = int(row["net_migration"])
        expected[month] = {"id": "changwon-net-" + month, "date": month + "-01", "value": value, "memo": "창원시 월별 순이동자수(명)"}
    require(len(expected) == 128, "source_count_changed")
    months = sorted(expected)
    values = [expected[month]["value"] for month in months]
    maximum, minimum = max(values), min(values)
    last = month_index(months[-1])
    recent_months = [month_string(index) for index in range(last - 11, last + 1)]
    previous_months = [month_string(index) for index in range(last - 23, last - 11)]
    require(all(month in expected for month in recent_months + previous_months), "source_recent_window_incomplete")
    recent = Fraction(sum(expected[month]["value"] for month in recent_months), 12)
    previous = Fraction(sum(expected[month]["value"] for month in previous_months), 12)
    difference = recent - previous
    summary = {
        "metric": "창원시 월별 순이동자수", "unit": "명", "frequency": "monthly",
        "period": {"start": months[0], "end": months[-1]}, "count": len(months),
        "metrics": {
            "total": sum(values), "average": float(round(Fraction(sum(values), len(values)), 2)),
            "max": maximum, "min": minimum,
            "max_months": [month for month in months if expected[month]["value"] == maximum],
            "min_months": [month for month in months if expected[month]["value"] == minimum],
        },
        "latest": {"month": months[-1], "value": values[-1]},
        "trend": {
            "method": "latest_12m_mean_vs_previous_12m_mean",
            "status": "increase" if difference > 0 else "decrease" if difference < 0 else "unchanged",
            "recent_period": {"start": recent_months[0], "end": recent_months[-1]},
            "previous_period": {"start": previous_months[0], "end": previous_months[-1]},
            "recent_average": float(round(recent, 2)), "previous_average": float(round(previous, 2)),
            "difference": float(round(difference, 2)),
        },
        "quality": {"missing_months": [month_string(index) for index in range(month_index(months[0]), last + 1) if month_string(index) not in expected]},
    }
    return [expected[month] for month in months], summary, hashlib.sha256(payload).hexdigest()


def _typed(value):
    """Represent full snapshot contents without exposing those contents in a report."""
    if isinstance(value, dict):
        return {"dict": [[key, _typed(value[key])] for key in sorted(value)]}
    if isinstance(value, (list, tuple)):
        return {type(value).__name__: [_typed(item) for item in value]}
    if isinstance(value, datetime):
        return {type(value).__name__: {
            "isoformat": value.isoformat(),
            "nanosecond": getattr(value, "nanosecond", value.microsecond * 1000),
        }}
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    return {type(value).__name__: repr(value)}


def _production_snapshot(client):
    snapshots = client.collection("data").get(retry=None, timeout=REQUEST_TIMEOUT)
    result = [{"id": item.id, "data": _typed(item.to_dict()),
               "create_time": _typed(item.create_time), "update_time": _typed(item.update_time)} for item in snapshots]
    return sorted(result, key=lambda item: item["id"])


def _digest(snapshot):
    return hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _safe_error(error):
    if isinstance(error, LiveCheckError):
        return error.code
    return {
        "FirebaseError": "firebase_configuration_or_connection",
        "DeadlineExceeded": "request_timeout", "TimeoutError": "request_timeout",
        "PermissionDenied": "permission_denied", "Unauthenticated": "unauthenticated",
        "ServiceUnavailable": "database_unavailable", "TransportError": "database_unavailable",
        "NotFound": "not_found", "FailedPrecondition": "write_condition_failed",
    }.get(type(error).__name__, "unexpected_error_details_suppressed")


def _cleanup_owned(client, document, allowed_payloads):
    """Cleanup checks exact run-token payload and a last-update precondition."""
    try:
        snapshot = document.get(retry=None, timeout=REQUEST_TIMEOUT)
        if not snapshot.exists:
            return {"ok": True, "absent": True, "fallback_delete_used": False}
        actual = snapshot.to_dict()
        if not any(_typed(actual) == _typed(payload) for payload in allowed_payloads) or snapshot.update_time is None:
            return {"ok": False, "absent": False, "error": "test_document_ownership_not_confirmed"}
        option = client.write_option(last_update_time=snapshot.update_time)
        document.delete(option=option, retry=None, timeout=REQUEST_TIMEOUT)
        absent = not document.get(retry=None, timeout=REQUEST_TIMEOUT).exists
        return {"ok": absent, "absent": absent, "fallback_delete_used": True,
                **({"error": "test_document_remains"} if not absent else {})}
    except Exception as error:
        return {"ok": False, "absent": None, "error": _safe_error(error)}


def _compare_summary(actual, expected):
    for key in ("metric", "unit", "frequency", "period", "count", "metrics", "latest", "quality"):
        require(_typed(actual.get(key)) == _typed(expected[key]), "summary_" + key + "_mismatch")
    for key, value in expected["trend"].items():
        require(_typed(actual.get("trend", {}).get(key)) == _typed(value), "summary_trend_" + key + "_mismatch")
    require(isinstance(actual["trend"].get("description"), str) and bool(actual["trend"]["description"]), "summary_description_missing")
    require(isinstance(actual.get("limitations"), list) and len(actual["limitations"]) >= 5 and all(isinstance(item, str) and item for item in actual["limitations"]), "summary_limitations_missing")


def run_live():
    """Exactly one live run; production data is only read, never repaired/imported."""
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.routers.data import get_data_service
    from app.services.data import DataService
    from app.services.firestore import get_firestore_client

    result = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "ok": False,
              "production_read": {"ok": False}, "independent_summary": {"ok": False},
              "isolated_crud": {"ok": False}, "cleanup": {"ok": True, "not_needed": True},
              "production_preserved": {"ok": False}}
    client = None
    before = None
    document = None
    creation_attempted = False
    allowed_payloads = []
    try:
        expected_records, expected_summary, source_hash = independent_source_summary()
        result["source_sha256"] = source_hash
        client = get_firestore_client()
        before = _production_snapshot(client)
        require(len(before) == len(expected_records), "production_count_before_mismatch")
        result["production_before"] = {"count": len(before), "sha256_including_metadata": _digest(before)}
        app = create_app()
        service = DataService(client)
        app.dependency_overrides[get_data_service] = lambda: service
        with TestClient(app, raise_server_exceptions=False) as http:
            response = http.get("/api/data")
            require(response.status_code == 200, "production_get_http_failed")
            body = response.json()
            require(_typed(body) == _typed({"items": expected_records, "count": len(expected_records)}), "production_records_or_types_mismatch")
            result["production_read"] = {"ok": True, "http_status": 200, "count": len(expected_records), "sorted_and_all_fields_match": True}
            response = http.get("/api/data/summary")
            require(response.status_code == 200, "production_summary_http_failed")
            actual_summary = response.json()
            _compare_summary(actual_summary, expected_summary)
            result["independent_summary"] = {"ok": True, "http_status": 200, "oracle": "independent csv and Fraction calculation"}
            result["summary"] = actual_summary

            run_id = uuid4().hex
            collection = "_data_api_checks_" + run_id
            service = DataService(client, collection_name=collection)
            document_id = "changwon-net-2099-01"
            document = client.collection(collection).document(document_id)
            require(not document.get(retry=None, timeout=REQUEST_TIMEOUT).exists, "test_document_already_exists")
            initial = {"date": "2099-01-01", "value": -11, "memo": "API 연결 검증 " + run_id}
            changed = {**initial, "value": 0}
            allowed_payloads = [initial, changed]
            result["isolated_crud"] = {"ok": False, "collection": collection, "document_id": document_id, "stages": []}
            stages = result["isolated_crud"]["stages"]
            creation_attempted = True
            response = http.post("/api/data", json=initial)
            require(response.status_code == 201, "isolated_create_http_failed")
            require(_typed(response.json()) == _typed({"id": document_id, **initial}), "isolated_create_payload_mismatch")
            stages.append({"operation": "POST", "status": 201})
            response = http.get("/api/data")
            require(response.status_code == 200 and _typed(response.json()) == _typed({"items": [{"id": document_id, **initial}], "count": 1}), "isolated_read_failed")
            stages.append({"operation": "GET", "status": 200})
            response = http.put("/api/data/" + document_id, json=changed)
            require(response.status_code == 200 and _typed(response.json()) == _typed({"id": document_id, **changed}), "isolated_update_failed")
            stages.append({"operation": "PUT", "status": 200})
            response = http.get("/api/data/summary")
            require(response.status_code == 200, "isolated_summary_http_failed")
            body = response.json()
            require(body["count"] == 1 and body["metrics"]["total"] == 0 and body["latest"] == {"month": "2099-01", "value": 0} and body["trend"]["status"] == "insufficient_data", "isolated_summary_not_updated")
            stages.append({"operation": "summary", "status": 200})
            response = http.delete("/api/data/" + document_id)
            require(response.status_code == 204 and response.content == b"", "isolated_delete_failed")
            stages.append({"operation": "DELETE", "status": 204})
            response = http.get("/api/data")
            require(response.status_code == 200 and response.json() == {"items": [], "count": 0}, "isolated_api_not_empty_after_delete")
            require(not document.get(retry=None, timeout=REQUEST_TIMEOUT).exists, "isolated_document_remains_after_delete")
            stages.append({"operation": "absence_check", "ok": True})
            result["isolated_crud"]["ok"] = True
    except Exception as error:
        result["error"] = _safe_error(error)
    finally:
        if creation_attempted and document is not None:
            result["cleanup"] = _cleanup_owned(client, document, allowed_payloads)
        if client is not None and before is not None:
            try:
                after = _production_snapshot(client)
                result["production_preserved"] = {
                    "ok": before == after, "before_count": len(before), "after_count": len(after),
                    "before_sha256_including_metadata": _digest(before), "after_sha256_including_metadata": _digest(after),
                    "comparison": "all document IDs, typed payloads, create_time and update_time",
                }
                if before != after:
                    result.setdefault("error", "production_changed_during_check")
            except Exception as error:
                result["production_preserved"] = {"ok": False, "error": _safe_error(error)}
    result["ok"] = all(result[key]["ok"] for key in ("production_read", "independent_summary", "isolated_crud", "cleanup", "production_preserved")) and "error" not in result
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="실제 data는 읽기만 검사하고 CRUD는 격리 컬렉션에서 검사합니다.")
    parser.add_argument("--live", action="store_true", help="명시적으로 실제 Firestore 검사를 한 차례 실행")
    args = parser.parse_args(argv)
    if not args.live:
        print("실제 DB 검사는 --live 옵션이 필요합니다. 기본 실행에서는 Firebase에 연결하지 않습니다.")
        return 2
    result = run_live()
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
