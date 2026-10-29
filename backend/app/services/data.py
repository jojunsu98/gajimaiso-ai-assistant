"""Bounded Firestore CRUD operations for monthly migration records."""

from functools import wraps

from pydantic import ValidationError

from app.schemas.data import DataRecord, DataWrite


RPC_TIMEOUT_SECONDS = 10
_FIELDS = {"date", "value", "memo"}


class DataServiceError(RuntimeError):
    """An HTTP-safe category and fixed message, never an SDK exception string."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def _integrity_error():
    return DataServiceError(
        500, "data_integrity_error", "저장된 월별 데이터 형식에 오류가 있습니다."
    )


def _not_found():
    return DataServiceError(404, "data_not_found", "해당 월별 데이터가 없습니다.")


def _duplicate():
    return DataServiceError(409, "duplicate_month", "같은 월의 데이터가 이미 있습니다.")


def _safe_operation(method):
    @wraps(method)
    def guarded(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except DataServiceError:
            raise
        except Exception as error:
            # Import transport modules only when needed; this module never
            # initializes Firebase or reads credential settings.
            from google.api_core.exceptions import GoogleAPICallError, RetryError
            from google.auth.exceptions import GoogleAuthError
            from grpc import RpcError
            from requests.exceptions import RequestException

            from app.config import FirebaseError

            if isinstance(
                error,
                (
                    GoogleAPICallError,
                    RetryError,
                    GoogleAuthError,
                    RpcError,
                    RequestException,
                    FirebaseError,
                    TimeoutError,
                    ConnectionError,
                ),
            ):
                raise DataServiceError(
                    503,
                    "database_unavailable",
                    "데이터베이스에 연결할 수 없습니다. 연결 설정과 상태를 확인하세요.",
                ) from None
            raise DataServiceError(
                500, "internal_error", "데이터 처리 중 오류가 발생했습니다."
            ) from None

    return guarded


def _document_id(record_date: str) -> str:
    return f"changwon-net-{record_date[:7]}"


def _decode_payload(snapshot) -> DataWrite:
    payload = snapshot.to_dict()
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise _integrity_error()
    try:
        return DataWrite.model_validate(payload)
    except (ValidationError, TypeError, ValueError):
        raise _integrity_error() from None


def _decode(snapshot) -> DataRecord:
    """Fail on malformed stored data instead of excluding or coercing it."""
    payload = _decode_payload(snapshot)
    try:
        record = DataRecord.model_validate({**payload.model_dump(), "id": snapshot.id})
    except (ValidationError, TypeError, ValueError):
        raise _integrity_error() from None
    if record.id != _document_id(record.date):
        raise _integrity_error()
    return record


class DataService:
    """Use the existing client with a server-selected collection only.

    The non-default collection argument exists for isolated integration tests;
    an HTTP request must never control it.
    """

    def __init__(self, client, collection_name: str = "data"):
        self.client = client
        self.collection_name = collection_name

    def _collection(self):
        return self.client.collection(self.collection_name)

    def _read_records(self):
        snapshots = self._collection().get(retry=None, timeout=RPC_TIMEOUT_SECONDS)
        records = [_decode(snapshot) for snapshot in snapshots]
        return records

    @staticmethod
    def _validate_unique(records):
        months = [record.date[:7] for record in records]
        if len(set(months)) != len(months):
            raise _integrity_error()

    @_safe_operation
    def list_data(self) -> list[DataRecord]:
        records = self._read_records()
        self._validate_unique(records)
        return sorted(records, key=lambda record: record.date)

    @_safe_operation
    def create_data(self, payload: DataWrite) -> DataRecord:
        from google.api_core.exceptions import AlreadyExists

        # One collection read finds a duplicate month even if an older document
        # used a different ID. Other malformed records block creation safely.
        snapshots = list(self._collection().get(retry=None, timeout=RPC_TIMEOUT_SECONDS))
        stored_payloads = [_decode_payload(snapshot) for snapshot in snapshots]
        if any(stored.date == payload.date for stored in stored_payloads):
            raise _duplicate()
        records = [_decode(snapshot) for snapshot in snapshots]
        self._validate_unique(records)
        document_id = _document_id(payload.date)
        values = payload.model_dump()
        try:
            self._collection().document(document_id).create(
                values, retry=None, timeout=RPC_TIMEOUT_SECONDS
            )
        except AlreadyExists:
            # create() also protects against a simultaneous request that passed
            # the preceding read before this document existed.
            raise _duplicate() from None
        return DataRecord(id=document_id, **values)

    def _existing(self, document_id):
        reference = self._collection().document(document_id)
        snapshot = reference.get(retry=None, timeout=RPC_TIMEOUT_SECONDS)
        if not snapshot.exists:
            raise _not_found()
        record = _decode(snapshot)
        if record.id != document_id or snapshot.update_time is None:
            raise _integrity_error()
        return reference, snapshot, record

    def _changed_after_read(self, reference):
        # A failed update-time precondition must not be reported as success.
        # One bounded reread distinguishes a concurrent removal from an edit.
        snapshot = reference.get(retry=None, timeout=RPC_TIMEOUT_SECONDS)
        if not snapshot.exists:
            raise _not_found() from None
        raise DataServiceError(
            409,
            "concurrent_modification",
            "다른 요청이 데이터를 변경했습니다. 현재 값을 확인한 뒤 다시 요청하세요.",
        ) from None

    @_safe_operation
    def update_data(self, document_id: str, payload: DataWrite) -> DataRecord:
        from google.api_core.exceptions import FailedPrecondition, NotFound

        reference, snapshot, existing = self._existing(document_id)
        if payload.date != existing.date or document_id != _document_id(payload.date):
            raise DataServiceError(
                422,
                "month_change_not_supported",
                "기존 문서의 월은 변경할 수 없습니다. 문서 ID와 같은 월을 입력하세요.",
            )
        # The last-update precondition implies existence and prevents an upsert
        # or an overwrite of a concurrent change between the read and write.
        option = self.client.write_option(last_update_time=snapshot.update_time)
        values = payload.model_dump()
        try:
            reference.update(
                values, option=option, retry=None, timeout=RPC_TIMEOUT_SECONDS
            )
        except NotFound:
            raise _not_found() from None
        except FailedPrecondition:
            self._changed_after_read(reference)
        return DataRecord(id=document_id, **values)

    @_safe_operation
    def delete_data(self, document_id: str) -> None:
        from google.api_core.exceptions import FailedPrecondition, NotFound

        reference, snapshot, _ = self._existing(document_id)
        option = self.client.write_option(last_update_time=snapshot.update_time)
        try:
            reference.delete(
                option=option, retry=None, timeout=RPC_TIMEOUT_SECONDS
            )
        except NotFound:
            raise _not_found() from None
        except FailedPrecondition:
            self._changed_after_read(reference)
