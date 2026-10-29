"""Offline service tests: in-memory SDK doubles, never a Firebase client."""

from copy import deepcopy
from dataclasses import dataclass
import unittest

from google.api_core.exceptions import (
    AlreadyExists,
    DeadlineExceeded,
    FailedPrecondition,
    NotFound,
    PermissionDenied,
    ServiceUnavailable,
)

from app.schemas.data import DataWrite
from app.services.data import DataService, DataServiceError, RPC_TIMEOUT_SECONDS


def values(month="2026-01", value=-5, memo="검증용"):
    return {"date": f"{month}-01", "value": value, "memo": memo}


def record_id(month="2026-01"):
    return f"changwon-net-{month}"


@dataclass
class Snapshot:
    id: str
    payload: object
    exists: bool = True
    update_time: object = 1

    def to_dict(self):
        return deepcopy(self.payload)


class FakeReference:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.id = document_id

    def _before(self, operation, kwargs):
        self.collection.calls.append((operation, self.id, kwargs))
        failure = self.collection.failures.get(operation)
        if failure is not None:
            raise failure
        hook = self.collection.hooks.pop(operation, None)
        if hook:
            hook(self.collection, self.id)

    def get(self, **kwargs):
        self._before("document_get", kwargs)
        if self.id not in self.collection.documents:
            return Snapshot(self.id, None, exists=False, update_time=None)
        return Snapshot(
            self.id,
            deepcopy(self.collection.documents[self.id]),
            update_time=self.collection.versions[self.id],
        )

    def create(self, payload, **kwargs):
        self._before("create", kwargs)
        if self.id in self.collection.documents:
            raise AlreadyExists("private error detail")
        self.collection.documents[self.id] = deepcopy(payload)
        self.collection.versions[self.id] = 1

    def update(self, payload, *, option, **kwargs):
        self._before("update", {"option": option, **kwargs})
        if self.id not in self.collection.documents:
            raise NotFound("private error detail")
        if option["last_update_time"] != self.collection.versions[self.id]:
            raise FailedPrecondition("private error detail")
        self.collection.documents[self.id].update(deepcopy(payload))
        self.collection.versions[self.id] += 1

    def delete(self, *, option, **kwargs):
        self._before("delete", {"option": option, **kwargs})
        if self.id not in self.collection.documents:
            raise FailedPrecondition("private error detail")
        if option["last_update_time"] != self.collection.versions[self.id]:
            raise FailedPrecondition("private error detail")
        del self.collection.documents[self.id]
        del self.collection.versions[self.id]


class FakeCollection:
    def __init__(self, documents):
        self.documents = deepcopy(documents)
        self.versions = {document_id: 1 for document_id in documents}
        self.calls = []
        self.failures = {}
        self.hooks = {}
        self.extra_snapshots = []

    def document(self, document_id):
        return FakeReference(self, document_id)

    def get(self, **kwargs):
        self.calls.append(("collection_get", None, kwargs))
        if "collection_get" in self.failures:
            raise self.failures["collection_get"]
        return [
            Snapshot(document_id, payload, update_time=self.versions[document_id])
            for document_id, payload in self.documents.items()
        ] + self.extra_snapshots


class FakeClient:
    def __init__(self, documents=None):
        self.storage = FakeCollection(documents or {})
        self.collection_names = []

    def collection(self, name):
        self.collection_names.append(name)
        return self.storage

    def write_option(self, **kwargs):
        return kwargs


class DataServiceTests(unittest.TestCase):
    def make_service(self, documents=None, collection_name="data"):
        client = FakeClient(documents)
        return DataService(client, collection_name), client.storage, client

    def assert_service_error(self, status, code, function, *args):
        with self.assertRaises(DataServiceError) as caught:
            function(*args)
        self.assertEqual(caught.exception.status_code, status)
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn("private error detail", str(caught.exception))
        return caught.exception

    def test_normal_crud_and_strict_stored_payload(self):
        service, storage, _ = self.make_service()
        created = service.create_data(DataWrite(**values(value=-10)))
        self.assertEqual(created.model_dump(), {"id": record_id(), **values(value=-10)})
        self.assertEqual(storage.documents[record_id()], values(value=-10))
        changed = service.update_data(record_id(), DataWrite(**values(value=0, memo="")))
        self.assertEqual(changed.value, 0)
        self.assertEqual(changed.memo, "")
        self.assertEqual(service.list_data(), [changed])
        self.assertIsNone(service.delete_data(record_id()))
        self.assertEqual(service.list_data(), [])

    def test_list_is_ascending_with_single_collection_read(self):
        service, storage, _ = self.make_service({
            record_id("2026-03"): values("2026-03", 0),
            record_id("2026-01"): values("2026-01", -1),
        })
        self.assertEqual([row.date for row in service.list_data()], ["2026-01-01", "2026-03-01"])
        self.assertEqual(storage.calls, [("collection_get", None, {"retry": None, "timeout": RPC_TIMEOUT_SECONDS})])

    def test_empty_and_one_record_are_allowed(self):
        service, _, _ = self.make_service()
        self.assertEqual(service.list_data(), [])
        service.create_data(DataWrite(**values()))
        self.assertEqual(len(service.list_data()), 1)

    def test_server_selected_isolated_collection_is_used(self):
        service, _, client = self.make_service(collection_name="_data_api_checks_local_test")
        service.create_data(DataWrite(**values()))
        service.list_data()
        self.assertTrue(client.collection_names)
        self.assertEqual(set(client.collection_names), {"_data_api_checks_local_test"})

    def test_all_rpc_calls_have_timeout_and_no_automatic_retry(self):
        service, storage, _ = self.make_service()
        service.create_data(DataWrite(**values()))
        service.update_data(record_id(), DataWrite(**values(value=0)))
        service.delete_data(record_id())
        for operation, _, kwargs in storage.calls:
            with self.subTest(operation=operation):
                self.assertIsNone(kwargs["retry"])
                self.assertEqual(kwargs["timeout"], RPC_TIMEOUT_SECONDS)
        writes = [call for call in storage.calls if call[0] in {"update", "delete"}]
        self.assertTrue(all("last_update_time" in call[2]["option"] for call in writes))

    def test_duplicate_month_is_409_without_write(self):
        service, storage, _ = self.make_service({record_id(): values()})
        before = deepcopy(storage.documents)
        self.assert_service_error(409, "duplicate_month", service.create_data, DataWrite(**values(value=20)))
        self.assertEqual(storage.documents, before)
        self.assertFalse(any(call[0] == "create" for call in storage.calls))

    def test_same_month_under_another_id_is_409_without_write(self):
        service, storage, _ = self.make_service({"legacy-id": values()})
        self.assert_service_error(409, "duplicate_month", service.create_data, DataWrite(**values()))
        self.assertEqual(set(storage.documents), {"legacy-id"})

    def test_concurrent_create_cannot_overwrite(self):
        service, storage, _ = self.make_service()
        def concurrent_create(collection, document_id):
            collection.documents[document_id] = values(value=77)
            collection.versions[document_id] = 1
        storage.hooks["create"] = concurrent_create
        self.assert_service_error(409, "duplicate_month", service.create_data, DataWrite(**values()))
        self.assertEqual(storage.documents[record_id()]["value"], 77)

    def test_missing_update_does_not_upsert(self):
        service, storage, _ = self.make_service()
        self.assert_service_error(404, "data_not_found", service.update_data, record_id(), DataWrite(**values()))
        self.assertEqual(storage.documents, {})
        self.assertFalse(any(call[0] == "update" for call in storage.calls))

    def test_missing_delete_is_404_without_delete_call(self):
        service, storage, _ = self.make_service()
        self.assert_service_error(404, "data_not_found", service.delete_data, record_id())
        self.assertFalse(any(call[0] == "delete" for call in storage.calls))

    def test_month_change_is_422_without_writes(self):
        service, storage, _ = self.make_service({record_id(): values()})
        self.assert_service_error(422, "month_change_not_supported", service.update_data, record_id(), DataWrite(**values("2026-02")))
        self.assertEqual(storage.documents, {record_id(): values()})
        self.assertFalse(any(call[0] == "update" for call in storage.calls))

    def test_delete_removes_only_requested_document(self):
        service, storage, _ = self.make_service({record_id(): values(), record_id("2026-02"): values("2026-02")})
        service.delete_data(record_id())
        self.assertEqual(storage.documents, {record_id("2026-02"): values("2026-02")})

    def test_concurrent_removal_before_update_returns_404(self):
        service, storage, _ = self.make_service({record_id(): values()})
        storage.hooks["update"] = lambda collection, document_id: collection.documents.pop(document_id)
        self.assert_service_error(404, "data_not_found", service.update_data, record_id(), DataWrite(**values(value=10)))
        self.assertNotIn(record_id(), storage.documents)

    def test_concurrent_removal_before_delete_does_not_report_success(self):
        service, storage, _ = self.make_service({record_id(): values()})
        storage.hooks["delete"] = lambda collection, document_id: collection.documents.pop(document_id)
        self.assert_service_error(404, "data_not_found", service.delete_data, record_id())
        self.assertEqual(sum(call[0] == "document_get" for call in storage.calls), 2)

    def test_concurrent_edits_are_not_overwritten_or_deleted(self):
        for operation in ("update", "delete"):
            with self.subTest(operation=operation):
                service, storage, _ = self.make_service({record_id(): values()})
                def edit(collection, document_id):
                    collection.documents[document_id]["value"] = 55
                    collection.versions[document_id] += 1
                storage.hooks[operation] = edit
                args = (record_id(), DataWrite(**values(value=8))) if operation == "update" else (record_id(),)
                self.assert_service_error(409, "concurrent_modification", getattr(service, f"{operation}_data"), *args)
                self.assertEqual(storage.documents[record_id()]["value"], 55)

    def test_invalid_stored_fields_are_not_coerced_or_dropped(self):
        bad_rows = [
            values(value=True), values(value=1.0), values(value="1"),
            values(value=float("nan")), values(value=float("inf")),
            values(value=2**63), values(memo=None), values(memo="x" * 501),
            {**values(), "date": "2026-01-02"}, {**values(), "date": "2026-13-01"},
            {**values(), "date": "2026-1-01"}, {**values(), "extra": "x"},
            {"date": "2026-01-01", "value": 1}, None,
        ]
        for bad_row in bad_rows:
            with self.subTest(payload_type=type(bad_row).__name__):
                service, _, _ = self.make_service({record_id(): bad_row})
                self.assert_service_error(500, "data_integrity_error", service.list_data)

    def test_invalid_id_or_duplicate_month_causes_integrity_error(self):
        service, _, _ = self.make_service({"different-id": values()})
        self.assert_service_error(500, "data_integrity_error", service.list_data)
        service, storage, _ = self.make_service({record_id(): values()})
        storage.extra_snapshots.append(Snapshot(record_id(), values()))
        self.assert_service_error(500, "data_integrity_error", service.list_data)

    def test_invalid_other_document_blocks_create(self):
        service, storage, _ = self.make_service({"bad-id": values("2025-12")})
        self.assert_service_error(500, "data_integrity_error", service.create_data, DataWrite(**values()))
        self.assertEqual(set(storage.documents), {"bad-id"})

    def test_invalid_existing_document_blocks_update_and_delete(self):
        for method in ("update_data", "delete_data"):
            with self.subTest(method=method):
                service, storage, _ = self.make_service({record_id(): values(value="1")})
                args = (record_id(), DataWrite(**values())) if method == "update_data" else (record_id(),)
                self.assert_service_error(500, "data_integrity_error", getattr(service, method), *args)
                self.assertFalse(any(call[0] in {"update", "delete"} for call in storage.calls))

    def test_transport_errors_are_sanitized_503(self):
        for failure in (
            ServiceUnavailable("private error detail"),
            DeadlineExceeded("private error detail"),
            PermissionDenied("private error detail"),
            TimeoutError("private error detail"),
        ):
            with self.subTest(failure_type=type(failure).__name__):
                service, storage, _ = self.make_service()
                storage.failures["collection_get"] = failure
                self.assert_service_error(503, "database_unavailable", service.list_data)

    def test_write_transport_failure_is_not_reported_as_success(self):
        service, storage, _ = self.make_service()
        storage.failures["create"] = DeadlineExceeded("private error detail")
        self.assert_service_error(503, "database_unavailable", service.create_data, DataWrite(**values()))
        self.assertEqual(storage.documents, {})

    def test_unexpected_error_is_sanitized_500(self):
        service, storage, _ = self.make_service()
        storage.failures["collection_get"] = RuntimeError("private error detail")
        self.assert_service_error(500, "internal_error", service.list_data)


if __name__ == "__main__":
    unittest.main()
