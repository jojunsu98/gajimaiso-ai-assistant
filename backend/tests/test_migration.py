"""CSV import validation and storage tests; fixtures stay local and use no keys."""

import copy
import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import import_migration as migration
from app.services import migration_import as migration_store


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FIELDS = ["month", "region_code", "region_name", "net_migration"]
EXPECTED_MEMO = "창원시 월별 순이동자수(명)"


def monthly_fixture(count=128):
    """Synthetic, consecutive local fixture: never submitted to Firestore."""
    rows = []
    for offset in range(count):
        year, month_zero = divmod(2016 * 12 + offset, 12)
        rows.append({
            "month": f"{year:04d}-{month_zero + 1:02d}",
            "region_code": "48120",
            "region_name": "창원시",
            "net_migration": str(offset - 64),
        })
    return rows


class MigrationValidationTests(unittest.TestCase):
    def setUp(self):
        local_dir = PROJECT_ROOT / ".local"
        local_dir.mkdir(exist_ok=True)
        self.temp_dir = tempfile.TemporaryDirectory(
            prefix="migration-offline-test-", dir=local_dir
        )
        self.addCleanup(self.temp_dir.cleanup)
        self.temp_path = Path(self.temp_dir.name)
        self.counter = 0

    def write_csv(self, rows=None, fields=None, encoding="utf-8-sig"):
        rows = monthly_fixture() if rows is None else rows
        fields = list(rows[0]) if fields is None and rows else fields
        fields = REQUIRED_FIELDS if fields is None else fields
        self.counter += 1
        path = self.temp_path / f"fixture-{self.counter}.csv"
        with path.open("w", encoding=encoding, newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def assert_invalid(self, rows=None, fields=None, path=None):
        if path is None:
            path = self.write_csv(rows, fields)
        with self.assertRaises(migration.MigrationValidationError) as caught:
            migration.validate_csv(path)
        self.assertTrue(caught.exception.code)
        return caught.exception

    def test_full_period_is_preserved_with_exact_output_schema(self):
        source = self.write_csv()
        before = source.read_bytes()
        result = migration.validate_csv(source)
        records = result["records"]
        self.assertEqual(len(records), 128)
        self.assertIn("metadata", result)
        self.assertIn("quality", result)
        self.assertEqual(records[0], {
            "id": "changwon-net-2016-01",
            "date": "2016-01-01",
            "value": -64,
            "memo": EXPECTED_MEMO,
        })
        self.assertEqual(records[-1], {
            "id": "changwon-net-2026-08",
            "date": "2026-08-01",
            "value": 63,
            "memo": EXPECTED_MEMO,
        })
        self.assertEqual(len({r["id"] for r in records}), 128)
        self.assertTrue(all(type(r["value"]) is int for r in records))
        self.assertTrue(all(set(r) == {"id", "date", "value", "memo"} for r in records))
        self.assertEqual(source.read_bytes(), before)

    def test_input_order_does_not_change_chronological_output(self):
        rows = monthly_fixture()
        result = migration.validate_csv(self.write_csv(list(reversed(rows))))
        self.assertEqual(result["records"][0]["date"], "2016-01-01")
        self.assertEqual(result["records"][-1]["date"], "2026-08-01")
        self.assertEqual([r["value"] for r in result["records"]], list(range(-64, 64)))

    def test_one_hundred_distinct_months_are_sufficient(self):
        result = migration.validate_csv(self.write_csv(monthly_fixture(100)))
        self.assertEqual(len(result["records"]), 100)

    def test_fewer_than_one_hundred_months_are_rejected(self):
        self.assert_invalid(monthly_fixture(99))

    def test_duplicate_month_is_rejected_instead_of_deduplicated(self):
        rows = monthly_fixture()
        rows.append(copy.deepcopy(rows[10]))
        self.assert_invalid(rows)

    def test_conflicting_duplicate_month_is_rejected(self):
        rows = monthly_fixture()
        row = copy.deepcopy(rows[10])
        row["net_migration"] = "999"
        rows.append(row)
        self.assert_invalid(rows)

    def test_missing_middle_month_is_rejected_instead_of_filled(self):
        rows = monthly_fixture()
        del rows[40]
        self.assert_invalid(rows)

    def test_missing_required_column_is_rejected(self):
        for field in REQUIRED_FIELDS:
            with self.subTest(field=field):
                rows = monthly_fixture()
                for row in rows:
                    del row[field]
                self.assert_invalid(rows)

    def test_empty_required_cells_are_rejected(self):
        for field in REQUIRED_FIELDS:
            with self.subTest(field=field):
                rows = monthly_fixture()
                rows[20][field] = ""
                self.assert_invalid(rows)

    def test_unknown_column_with_empty_cell_is_rejected(self):
        rows = monthly_fixture()
        for row in rows:
            row["source_note"] = "present"
        rows[25]["source_note"] = ""
        self.assert_invalid(rows)

    def test_date_format_and_calendar_month_are_strict(self):
        invalid_dates = ["2016-1", "2016/01", "2016-01-01", "2016-00", "2016-13", "0000-01"]
        for value in invalid_dates:
            with self.subTest(value=value):
                rows = monthly_fixture()
                rows[0]["month"] = value
                self.assert_invalid(rows)

    def test_other_region_code_is_rejected_without_aggregation(self):
        for value in ("48", "48110", "48160", "48190"):
            with self.subTest(value=value):
                rows = monthly_fixture()
                rows[20]["region_code"] = value
                self.assert_invalid(rows)

    def test_other_region_name_is_rejected(self):
        rows = monthly_fixture()
        rows[20]["region_name"] = "경상남도"
        self.assert_invalid(rows)

    def test_negative_zero_and_integral_decimal_net_values_are_allowed(self):
        rows = monthly_fixture()
        for row, value in zip(rows, ["-25", "0", "1.0", "-2.000"]):
            row["net_migration"] = value
        result = migration.validate_csv(self.write_csv(rows))
        self.assertEqual([r["value"] for r in result["records"][:4]], [-25, 0, 1, -2])

    def test_noninteger_and_nonfinite_values_are_rejected(self):
        invalid_values = ["1.5", "NaN", "sNaN", "Infinity", "-Infinity", "Inf", "abc"]
        for value in invalid_values:
            with self.subTest(value=value):
                rows = monthly_fixture()
                rows[20]["net_migration"] = value
                self.assert_invalid(rows)

    def test_optional_original_numeric_fields_are_also_validated(self):
        fields = [
            "total_inflow", "total_outflow", "within_city_movement",
            "within_province_inflow", "within_province_outflow",
            "interprovince_inflow", "interprovince_outflow",
            "external_inflow", "external_outflow",
        ]
        for field in fields:
            for bad_value in ("", "1.5", "NaN", "-1"):
                with self.subTest(field=field, value=bad_value):
                    rows = monthly_fixture()
                    for row in rows:
                        row[field] = "100"
                    rows[20][field] = bad_value
                    self.assert_invalid(rows)

    def test_header_only_csv_is_rejected(self):
        self.assert_invalid([], fields=REQUIRED_FIELDS)

    def test_duplicate_header_is_rejected(self):
        path = self.write_csv()
        content = path.read_text(encoding="utf-8-sig")
        path.write_text(content.replace(
            "month,region_code,region_name,net_migration",
            "month,region_code,month,net_migration", 1
        ), encoding="utf-8-sig")
        self.assert_invalid(path=path)

    def test_short_and_long_data_rows_are_rejected(self):
        for suffix in (",unexpected", None):
            with self.subTest(suffix=suffix):
                path = self.write_csv()
                lines = path.read_text(encoding="utf-8-sig").splitlines()
                lines[10] = lines[10] + suffix if suffix else lines[10].rsplit(",", 1)[0]
                path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
                self.assert_invalid(path=path)

    def run_offline_cli(self, args, rows=None):
        source = self.write_csv(rows)
        output = io.StringIO()
        # Keep all reports inside this test's temporary folder; never overwrite
        # the user's actual migration reports. Patching the factory prevents
        # credentials or an external client from being loaded if a regression
        # accidentally changes the CLI's branch ordering.
        with (
            patch.object(migration, "PROJECT_ROOT", self.temp_path),
            patch("app.services.firestore.get_firestore_client") as get_client,
            contextlib.redirect_stdout(output),
        ):
            exit_code = migration.main(["--source", str(source), *args])
        get_client.assert_not_called()
        summary = json.loads(output.getvalue())
        report = json.loads(Path(summary["report"]).read_text(encoding="utf-8"))
        self.assertFalse(report["database_accessed"])
        return exit_code, summary, report

    def test_cli_default_mode_does_not_load_firestore_client(self):
        exit_code, summary, report = self.run_offline_cli([])
        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["mode"], "dry-run")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["expected"], 128)
        self.assertEqual(report["created"], 0)

    def test_cli_explicit_dry_run_does_not_load_firestore_client(self):
        exit_code, summary, report = self.run_offline_cli(["--dry-run"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["mode"], "dry-run")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["created"], 0)

    def test_cli_apply_invalid_csv_stops_before_loading_firestore_client(self):
        rows = monthly_fixture()
        rows[-1]["net_migration"] = "1.5"
        exit_code, summary, report = self.run_offline_cli(["--apply"], rows)
        self.assertEqual(exit_code, 2)
        self.assertEqual(summary["mode"], "apply")
        self.assertEqual(report["status"], "validation_error")
        self.assertEqual(report["error_code"], "fractional_number")


class FakeSnapshot:
    def __init__(self, document_id, payload=None):
        self.id = document_id
        self.exists = payload is not None
        self.payload = copy.deepcopy(payload)

    def to_dict(self):
        return copy.deepcopy(self.payload)


class FakeReference:
    def __init__(self, document_id):
        self.id = document_id


class FakeCollection:
    def __init__(self, client):
        self.client = client

    def limit(self, count):
        self.client.limit_count = count
        return self

    def get(self, *, retry, timeout):
        self.client.requests.append(("get", retry, timeout))
        if self.client.fail_preflight:
            raise RuntimeError("offline-only-sensitive-marker")
        return [
            FakeSnapshot(document_id, payload)
            for document_id, payload in list(self.client.documents.items())[:self.client.limit_count]
        ]

    def document(self, document_id):
        return FakeReference(document_id)


class FakeBatch:
    """Intentionally supports create only, never set, update or delete."""

    def __init__(self, client):
        self.client = client
        self.pending = []

    def create(self, reference, payload):
        self.pending.append((reference.id, copy.deepcopy(payload)))

    def commit(self, *, retry, timeout):
        self.client.requests.append(("commit", retry, timeout))
        self.client.commit_count += 1
        # Simulate a concurrent creator after the preflight snapshot.
        for document_id, payload in self.client.racing_documents.items():
            self.client.documents[document_id] = copy.deepcopy(payload)
        if any(document_id in self.client.documents for document_id, _ in self.pending):
            raise RuntimeError("offline-only-sensitive-marker")
        if (
            self.client.fail_commit_after is not None
            and self.client.commit_count == self.client.fail_commit_number
        ):
            for document_id, payload in self.pending[:self.client.fail_commit_after]:
                self.client.documents[document_id] = copy.deepcopy(payload)
            raise RuntimeError("offline-only-sensitive-marker")
        for document_id, payload in self.pending:
            self.client.documents[document_id] = copy.deepcopy(payload)
        return [object() for _ in self.pending]


class FakeFirestore:
    """In-process storage double with no SDK, credentials or network access."""

    def __init__(self, documents=None):
        self.documents = copy.deepcopy(documents or {})
        self.requests = []
        self.collection_names = []
        self.batches = []
        self.limit_count = 0
        self.commit_count = 0
        self.fail_preflight = False
        self.fail_commit_after = None
        self.fail_commit_number = 1
        self.fail_readback = False
        self.racing_documents = {}

    def collection(self, name):
        self.collection_names.append(name)
        if name != "data":
            raise AssertionError("Unexpected collection access")
        return FakeCollection(self)

    def batch(self):
        batch = FakeBatch(self)
        self.batches.append(batch)
        return batch

    def get_all(self, references, *, retry, timeout):
        self.requests.append(("get_all", retry, timeout))
        if self.fail_readback:
            raise RuntimeError("offline-only-sensitive-marker")
        return [FakeSnapshot(ref.id, self.documents.get(ref.id)) for ref in references]


def storage_fixture():
    return [
        {
            "id": f"changwon-net-2026-{month:02d}",
            "date": f"2026-{month:02d}-01",
            "value": value,
            "memo": EXPECTED_MEMO,
        }
        for month, value in [(1, -25), (2, 0), (3, 12)]
    ]


def payload(record):
    return {key: record[key] for key in ("date", "value", "memo")}


class MigrationStorageTests(unittest.TestCase):
    def test_new_records_use_create_only_and_verify_exact_values(self):
        records = storage_fixture()
        client = FakeFirestore()
        result = migration_store.store_records(client, records)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["created"], 3)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(client.documents, {r["id"]: payload(r) for r in records})
        check = migration_store.verify_records(client, records)
        self.assertEqual(check["status"], "ok")
        self.assertEqual(check["verified_count"], 3)
        self.assertTrue(client.requests)
        for operation, retry, timeout in client.requests:
            with self.subTest(operation=operation):
                self.assertIsNone(retry)
                self.assertGreater(timeout, 0)
                self.assertLessEqual(timeout, 10)

    def test_second_identical_import_skips_without_writing(self):
        records = storage_fixture()
        client = FakeFirestore({r["id"]: payload(r) for r in records})
        before = copy.deepcopy(client.documents)
        result = migration_store.store_records(client, records)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["skipped"], 3)
        self.assertEqual(client.commit_count, 0)
        self.assertEqual(client.documents, before)

    def test_same_id_different_value_prevents_all_writes(self):
        records = storage_fixture()
        existing = payload(records[1])
        existing["value"] = 100
        client = FakeFirestore({records[1]["id"]: existing})
        before = copy.deepcopy(client.documents)
        result = migration_store.store_records(client, records)
        self.assertEqual(result["status"], "conflict")
        self.assertTrue(result["conflicts"])
        self.assertEqual(client.commit_count, 0)
        self.assertEqual(client.documents, before)

    def test_other_id_with_same_month_prevents_all_writes(self):
        records = storage_fixture()
        client = FakeFirestore({"legacy-month-document": payload(records[1])})
        before = copy.deepcopy(client.documents)
        result = migration_store.store_records(client, records)
        self.assertEqual(result["status"], "conflict")
        self.assertTrue(result["conflicts"])
        self.assertEqual(client.commit_count, 0)
        self.assertEqual(client.documents, before)

    def test_boolean_is_not_treated_as_equal_to_integer_zero(self):
        records = storage_fixture()
        existing = payload(records[1])
        existing["value"] = False
        client = FakeFirestore({records[1]["id"]: existing})
        result = migration_store.store_records(client, records)
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(client.commit_count, 0)

    def test_preflight_failure_does_not_create_any_documents(self):
        client = FakeFirestore()
        client.fail_preflight = True
        result = migration_store.store_records(client, storage_fixture())
        self.assertEqual(result["status"], "network_error")
        self.assertEqual(client.commit_count, 0)
        self.assertEqual(client.documents, {})
        self.assertNotIn("offline-only-sensitive-marker", str(result))

    def test_failed_commit_reports_readback_without_retrying_write(self):
        records = storage_fixture()
        client = FakeFirestore()
        client.fail_commit_after = 1
        result = migration_store.store_records(client, records)
        self.assertEqual(result["status"], "network_error")
        self.assertEqual(client.commit_count, 1)
        self.assertEqual(set(client.documents), {records[0]["id"]})
        self.assertEqual(result["created_ids"], [])
        self.assertIn(records[0]["id"], result["present_after_error_ids"])
        self.assertIn(records[0]["id"], result["uncertain_ids"])
        self.assertEqual(set(result["remaining_ids"]), {r["id"] for r in records[1:]})
        self.assertNotIn("offline-only-sensitive-marker", str(result))
        self.assertEqual(sum(op == "get_all" for op, _, _ in client.requests), 1)

    def test_later_batch_failure_keeps_acknowledged_creations_separate(self):
        records = []
        for offset in range(405):
            year, month_zero = divmod(1990 * 12 + offset, 12)
            month = f"{year:04d}-{month_zero + 1:02d}"
            records.append({
                "id": f"changwon-net-{month}", "date": f"{month}-01",
                "value": offset - 200, "memo": EXPECTED_MEMO,
            })
        client = FakeFirestore()
        client.fail_commit_number = 2
        client.fail_commit_after = 0
        result = migration_store.store_records(client, records)
        self.assertEqual(result["status"], "network_error")
        self.assertEqual(client.commit_count, 2)
        self.assertEqual(result["created"], 400)
        self.assertEqual(result["created_ids"], [r["id"] for r in records[:400]])
        self.assertEqual(set(result["remaining_ids"]), {r["id"] for r in records[400:]})
        self.assertEqual(len(client.documents), 400)
        self.assertTrue(all(len(batch.pending) <= 400 for batch in client.batches))

    def test_failed_commit_and_failed_readback_preserve_uncertainty(self):
        records = storage_fixture()
        client = FakeFirestore()
        client.fail_commit_after = 1
        client.fail_readback = True
        result = migration_store.store_records(client, records)
        self.assertEqual(result["status"], "network_error")
        self.assertEqual(client.commit_count, 1)
        self.assertEqual(result["uncertain_count"], len(records))
        self.assertEqual(set(result["uncertain_ids"]), {r["id"] for r in records})
        self.assertNotIn("offline-only-sensitive-marker", str(result))

    def test_concurrent_create_does_not_overwrite_existing_value(self):
        records = storage_fixture()
        client = FakeFirestore()
        existing = payload(records[0])
        existing["value"] = 777
        client.racing_documents[records[0]["id"]] = existing
        result = migration_store.store_records(client, records)
        self.assertNotEqual(result["status"], "ok")
        self.assertEqual(client.documents[records[0]["id"]]["value"], 777)
        self.assertEqual(client.commit_count, 1)

    def test_verify_reports_missing_document(self):
        records = storage_fixture()
        client = FakeFirestore({r["id"]: payload(r) for r in records[:-1]})
        result = migration_store.verify_records(client, records)
        self.assertEqual(result["status"], "verification_failed")
        self.assertIn(records[-1]["id"], result["missing"])
        self.assertEqual(client.commit_count, 0)

    def test_verify_rejects_changed_value_type_and_memo(self):
        records = storage_fixture()
        for field, value in [("value", 100), ("value", -25.0), ("memo", "changed")]:
            with self.subTest(field=field, value=value):
                client = FakeFirestore({r["id"]: payload(r) for r in records})
                client.documents[records[0]["id"]][field] = value
                result = migration_store.verify_records(client, records)
                self.assertEqual(result["status"], "verification_failed")
                self.assertTrue(result["conflicts"])
                self.assertEqual(client.commit_count, 0)


if __name__ == "__main__":
    unittest.main()
