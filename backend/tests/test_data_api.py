"""HTTP contract tests; all data and services are local in-memory fakes."""

import contextlib
import copy
import io
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.config import FirebaseError, load_allowed_origins
from app.main import create_app
from app.security import require_access, limit_chat
from app.routers.data import get_data_service
from app.schemas.data import DataRecord
from app.services.data import DataServiceError


SECRET = "offline-sensitive-value-not-for-responses"


class FakeDataService:
    """Only a dependency override used by tests; never a production fallback."""

    def __init__(self):
        self.records = {}
        self.reads = 0

    def list_data(self):
        self.reads += 1
        return [DataRecord(**copy.deepcopy(row)) for row in sorted(
            self.records.values(), key=lambda row: row["date"]
        )]

    def create_data(self, payload):
        document_id = "changwon-net-" + payload.date[:7]
        if document_id in self.records:
            raise DataServiceError(409, "duplicate_month", "이미 존재하는 월입니다.")
        row = {"id": document_id, **payload.model_dump()}
        self.records[document_id] = row
        return DataRecord(**copy.deepcopy(row))

    def update_data(self, document_id, payload):
        if document_id not in self.records:
            raise DataServiceError(404, "data_not_found", "자료가 없습니다.")
        if document_id != "changwon-net-" + payload.date[:7]:
            raise DataServiceError(422, "month_change_not_supported", "월 변경은 지원하지 않습니다.")
        row = {"id": document_id, **payload.model_dump()}
        self.records[document_id] = row
        return DataRecord(**copy.deepcopy(row))

    def delete_data(self, document_id):
        if document_id not in self.records:
            raise DataServiceError(404, "data_not_found", "자료가 없습니다.")
        del self.records[document_id]


class DataAPITests(unittest.TestCase):
    def setUp(self):
        with patch("app.main.load_allowed_origins", return_value=[
            "http://localhost:5500", "http://127.0.0.1:5500"
        ]):
            self.app = create_app()
        # Business contracts use explicit test overrides; security has its own tests.
        self.app.dependency_overrides[require_access] = lambda: None
        self.app.dependency_overrides[limit_chat] = lambda: None
        self.service = FakeDataService()
        self.app.dependency_overrides[get_data_service] = lambda: self.service
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def payload(self, **overrides):
        return {"date": "2026-08-01", "value": -20, "memo": "월별 자료", **overrides}

    def test_crud_status_and_full_response_contract(self):
        payload = self.payload()
        response = self.client.post("/api/data", json=payload)
        self.assertEqual(201, response.status_code)
        record = {"id": "changwon-net-2026-08", **payload}
        self.assertEqual(record, response.json())
        self.assertEqual({"items": [record], "count": 1}, self.client.get("/api/data").json())
        changed = self.payload(value=0, memo="")
        response = self.client.put("/api/data/changwon-net-2026-08", json=changed)
        self.assertEqual(200, response.status_code)
        self.assertEqual({"id": record["id"], **changed}, response.json())
        response = self.client.delete("/api/data/changwon-net-2026-08")
        self.assertEqual(204, response.status_code)
        self.assertEqual(b"", response.content)
        self.assertEqual({"items": [], "count": 0}, self.client.get("/api/data").json())

    def test_list_is_sorted_and_count_is_not_fixed(self):
        for month in ("2026-08", "2025-01", "2026-02"):
            self.assertEqual(201, self.client.post("/api/data", json=self.payload(date=month + "-01")).status_code)
        body = self.client.get("/api/data").json()
        self.assertEqual(3, body["count"])
        self.assertEqual(["2025-01-01", "2026-02-01", "2026-08-01"], [row["date"] for row in body["items"]])

    def test_negative_zero_and_int64_boundaries_are_accepted(self):
        for value in (-5, 0, -(2**63), 2**63 - 1):
            with self.subTest(value=value):
                self.service.records.clear()
                response = self.client.post("/api/data", json=self.payload(value=value))
                self.assertEqual(201, response.status_code)
                self.assertIs(type(response.json()["value"]), int)

    def test_invalid_dates_are_rejected_without_writes(self):
        for value in ("2026-8-01", "2026-08-02", "2026-02-29", "2024-02-30", "2026-00-01", "2026-13-01", "2026-08", "2026-08-01T00:00:00", " 2026-08-01", 20260801, None):
            with self.subTest(value=value):
                self.assertEqual(422, self.client.post("/api/data", json=self.payload(date=value)).status_code)
        self.assertEqual({}, self.service.records)

    def test_invalid_values_are_rejected_without_coercion(self):
        for value in ("1", "-2", True, False, 1.0, 1.5, None, 2**63, -(2**63) - 1):
            with self.subTest(value=value):
                self.assertEqual(422, self.client.post("/api/data", json=self.payload(value=value)).status_code)
        self.assertEqual({}, self.service.records)

    def test_nonfinite_json_values_are_safe_422(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            body = '{"date":"2026-08-01","value":' + token + ',"memo":""}'
            response = self.client.post("/api/data", content=body, headers={"Content-Type": "application/json"})
            self.assertEqual(422, response.status_code)
            self.assertNotIn(token, response.text)
        self.assertEqual({}, self.service.records)

    def test_memo_type_length_and_empty_string(self):
        for memo in (None, 1, True, "가" * 501):
            with self.subTest(kind=type(memo).__name__):
                self.assertEqual(422, self.client.post("/api/data", json=self.payload(memo=memo)).status_code)
        self.assertEqual(201, self.client.post("/api/data", json=self.payload(memo="가" * 500)).status_code)
        self.assertEqual(200, self.client.put("/api/data/changwon-net-2026-08", json=self.payload(memo="")).status_code)

    def test_required_and_extra_fields_rejected_for_post_and_put(self):
        self.client.post("/api/data", json=self.payload())
        cases = []
        for field in ("date", "value", "memo"):
            candidate = self.payload()
            del candidate[field]
            cases.append(candidate)
        cases.append(self.payload(extra=SECRET))
        for candidate in cases:
            with self.subTest(fields=list(candidate)):
                for method, path in (("post", "/api/data"), ("put", "/api/data/changwon-net-2026-08")):
                    response = getattr(self.client, method)(path, json=candidate)
                    self.assertEqual(422, response.status_code)
                    self.assertNotIn(SECRET, response.text)

    def test_duplicate_create_is_409_and_preserves_record(self):
        self.client.post("/api/data", json=self.payload())
        response = self.client.post("/api/data", json=self.payload(value=999))
        self.assertEqual(409, response.status_code)
        self.assertEqual(-20, self.client.get("/api/data").json()["items"][0]["value"])

    def test_missing_update_and_delete_are_404(self):
        self.assertEqual(404, self.client.put("/api/data/changwon-net-2026-08", json=self.payload()).status_code)
        self.assertEqual(404, self.client.delete("/api/data/changwon-net-2026-08").status_code)

    def test_put_month_change_rejected_and_original_preserved(self):
        self.client.post("/api/data", json=self.payload())
        response = self.client.put("/api/data/changwon-net-2026-08", json=self.payload(date="2026-09-01"))
        self.assertEqual(422, response.status_code)
        self.assertEqual("2026-08-01", self.client.get("/api/data").json()["items"][0]["date"])

    def test_summary_reflects_crud_immediately_with_one_read_each(self):
        response = self.client.get("/api/data/summary")
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, response.json()["count"])
        self.assertEqual(1, self.service.reads)
        self.client.post("/api/data", json=self.payload(value=-20))
        self.assertEqual(-20, self.client.get("/api/data/summary").json()["metrics"]["total"])
        self.client.put("/api/data/changwon-net-2026-08", json=self.payload(value=0))
        body = self.client.get("/api/data/summary").json()
        self.assertEqual(0, body["metrics"]["total"])
        self.assertEqual(1, body["count"])
        self.client.delete("/api/data/changwon-net-2026-08")
        self.assertEqual(0, self.client.get("/api/data/summary").json()["count"])
        self.assertEqual(4, self.service.reads)

    def test_empty_summary_has_no_fabricated_observations(self):
        body = self.client.get("/api/data/summary").json()
        self.assertEqual(0, body["count"])
        self.assertIsNone(body["period"])
        self.assertIsNone(body["latest"])
        self.assertEqual(0, body["metrics"]["total"])
        for key in ("average", "max", "min"):
            self.assertIsNone(body["metrics"][key])
        self.assertEqual([], body["metrics"]["max_months"])
        self.assertEqual([], body["metrics"]["min_months"])
        self.assertEqual("insufficient_data", body["trend"]["status"])

    def test_cors_allowed_origins_and_required_methods(self):
        for origin in ("http://localhost:5500", "http://127.0.0.1:5500"):
            for method in ("GET", "POST", "PUT", "DELETE"):
                response = self.client.options("/api/data", headers={"Origin": origin, "Access-Control-Request-Method": method, "Access-Control-Request-Headers": "content-type"})
                self.assertEqual(200, response.status_code)
                self.assertEqual(origin, response.headers.get("access-control-allow-origin"))

    def test_cors_disallowed_origin_is_not_granted(self):
        headers = {"Origin": "https://untrusted.invalid", "Access-Control-Request-Method": "POST"}
        response = self.client.options("/api/data", headers=headers)
        self.assertEqual(400, response.status_code)
        self.assertNotIn("access-control-allow-origin", response.headers)
        response = self.client.get("/api/data", headers={"Origin": headers["Origin"]})
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_health_docs_and_openapi_remain_available(self):
        self.assertEqual({"status": "ok"}, self.client.get("/health").json())
        self.assertEqual(200, self.client.get("/docs").status_code)
        response = self.client.get("/openapi.json")
        self.assertEqual(200, response.status_code)
        document = response.json()
        for path in ("/health", "/api/data", "/api/data/{id}", "/api/data/summary"):
            self.assertIn(path, document["paths"])
        self.assertEqual({"get", "post"}, set(document["paths"]["/api/data"]))
        self.assertIn("schemas", document["components"])

    def test_service_unavailable_response_is_safe(self):
        self.service.list_data = lambda: (_ for _ in ()).throw(DataServiceError(503, "database_unavailable", "데이터베이스에 연결할 수 없습니다."))
        response = self.client.get("/api/data")
        self.assertEqual(503, response.status_code)
        self.assertNotIn(SECRET, response.text)

    def test_unexpected_exception_response_hides_internal_values(self):
        self.service.list_data = lambda: (_ for _ in ()).throw(RuntimeError(SECRET))
        response = self.client.get("/api/data")
        self.assertEqual(500, response.status_code)
        self.assertNotIn(SECRET, response.text)
        self.assertNotIn("RuntimeError", response.text)

    def test_configuration_error_is_safe_and_health_is_independent(self):
        self.app.dependency_overrides.clear()
        with patch("app.services.firestore.get_firestore_client", side_effect=FirebaseError("missing_credentials")):
            response = self.client.get("/api/data")
            self.assertEqual(503, response.status_code)
            self.assertNotIn("private_key", response.text)
            self.assertEqual(200, self.client.get("/health").status_code)
            self.assertEqual(200, self.client.get("/docs").status_code)

    def test_live_checker_requires_explicit_flag_without_database_access(self):
        from scripts import check_data_api
        with patch.object(check_data_api, "run_live") as live, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(2, check_data_api.main([]))
        live.assert_not_called()


class CorsConfigTests(unittest.TestCase):
    def test_unconfigured_origins_are_only_local_5500(self):
        with patch.dict("os.environ", {}, clear=True), patch("app.config.dotenv_values", return_value={}):
            self.assertEqual(["http://localhost:5500", "http://127.0.0.1:5500"], load_allowed_origins())

    def test_comma_list_is_trimmed_deduplicated_and_process_env_wins(self):
        with patch.dict("os.environ", {"ALLOWED_ORIGINS": " http://localhost:5500, ,http://localhost:5500,http://127.0.0.1:5501 "}, clear=True), patch("app.config.dotenv_values", return_value={"ALLOWED_ORIGINS": "https://file.invalid"}):
            self.assertEqual(["http://localhost:5500", "http://127.0.0.1:5501"], load_allowed_origins())

    def test_empty_process_setting_disables_origins(self):
        with patch.dict("os.environ", {"ALLOWED_ORIGINS": ""}, clear=True), patch("app.config.dotenv_values", return_value={"ALLOWED_ORIGINS": "https://file.invalid"}):
            self.assertEqual([], load_allowed_origins())

    def test_settings_read_failure_does_not_expand_origins(self):
        with patch("app.config.dotenv_values", side_effect=OSError(SECRET)):
            self.assertEqual([], load_allowed_origins())


class LiveCheckerSafetyTests(unittest.TestCase):
    def setUp(self):
        from scripts import check_data_api
        self.checker = check_data_api
        self.client = MagicMock()
        self.document = MagicMock()
        self.payload = {"date": "2099-01-01", "value": -11, "memo": "isolated-run-token"}

    def snapshot(self, exists=True, payload=None):
        item = MagicMock()
        item.exists = exists
        item.to_dict.return_value = self.payload if payload is None else payload
        item.update_time = "mock-update-time"
        return item

    def test_cleanup_absent_document_never_deletes(self):
        self.document.get.return_value = self.snapshot(exists=False)
        result = self.checker._cleanup_owned(self.client, self.document, [self.payload])
        self.assertTrue(result["ok"])
        self.document.delete.assert_not_called()

    def test_cleanup_only_owned_payload_uses_update_time_precondition(self):
        self.document.get.side_effect = [self.snapshot(), self.snapshot(exists=False)]
        result = self.checker._cleanup_owned(self.client, self.document, [self.payload])
        self.assertTrue(result["ok"])
        self.client.write_option.assert_called_once_with(last_update_time="mock-update-time")
        self.document.delete.assert_called_once_with(option=self.client.write_option.return_value, retry=None, timeout=10)

    def test_cleanup_unexpected_payload_is_preserved(self):
        self.document.get.return_value = self.snapshot(payload={**self.payload, "memo": "different-owner"})
        result = self.checker._cleanup_owned(self.client, self.document, [self.payload])
        self.assertFalse(result["ok"])
        self.assertEqual("test_document_ownership_not_confirmed", result["error"])
        self.document.delete.assert_not_called()

    def test_cleanup_failure_is_reported_without_exception_text(self):
        self.document.get.side_effect = RuntimeError(SECRET)
        result = self.checker._cleanup_owned(self.client, self.document, [self.payload])
        self.assertFalse(result["ok"])
        self.assertNotIn(SECRET, str(result))

    def test_cleanup_absence_is_verified_after_delete(self):
        self.document.get.return_value = self.snapshot()
        result = self.checker._cleanup_owned(self.client, self.document, [self.payload])
        self.assertFalse(result["ok"])
        self.assertEqual("test_document_remains", result["error"])

    def test_snapshot_type_comparison_distinguishes_bool_float_int(self):
        self.assertNotEqual(self.checker._typed(1), self.checker._typed(1.0))
        self.assertNotEqual(self.checker._typed(1), self.checker._typed(True))


if __name__ == "__main__":
    unittest.main()
