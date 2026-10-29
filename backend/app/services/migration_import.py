"""Create-only Firestore import with a complete, bounded conflict preflight.

This module does not initialize Firebase or load credentials.  Callers must
validate the entire CSV before supplying records and explicitly choose to call
the functions below with their existing Firestore client.
"""

from datetime import date, datetime
import re


MEMO = "창원시 월별 순이동자수(명)"
RPC_TIMEOUT_SECONDS = 10
MAX_EXISTING_DOCUMENTS = 10_000
BATCH_SIZE = 400
_MONTH_PREFIX = re.compile(r"^(\d{4})-(\d{2})(?:$|-)")
_RECORD_DATE = re.compile(r"^\d{4}-\d{2}-01$")
_PAYLOAD_FIELDS = ("date", "value", "memo")


def _report(expected):
    return {
        "status": "ok",
        "expected": expected,
        "created": 0,
        "created_confirmed": 0,
        "created_ids": [],
        "skipped": 0,
        "conflicts": [],
        "missing": [],
        "verified_count": 0,
        "uncertain_count": 0,
        "uncertain_ids": [],
        "present_after_error_ids": [],
        "remaining_ids": [],
        "errors": [],
    }


def _month(value):
    """Recognize a month conservatively, without normalizing stored values."""
    if isinstance(value, (datetime, date)):
        return f"{value.year:04d}-{value.month:02d}"
    if not isinstance(value, str):
        return None
    match = _MONTH_PREFIX.match(value)
    if match is None:
        return None
    try:
        parsed = date(int(match[1]), int(match[2]), 1)
    except ValueError:
        return None
    return f"{parsed.year:04d}-{parsed.month:02d}"


def _validated_records(records):
    """Defend the storage boundary even when called without the CSV CLI."""
    expected = {}
    conflicts = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            conflicts.append({"code": "invalid_input_record", "index": index})
            continue
        record_date = record.get("date")
        record_month = _month(record_date)
        if (
            type(record_date) is not str
            or not _RECORD_DATE.fullmatch(record_date)
            or record_month is None
            or type(record.get("value")) is not int
            or not -(2**63) <= record["value"] < 2**63
            or record.get("memo") != MEMO
            or record.get("id") != f"changwon-net-{record_month}"
        ):
            conflicts.append({"code": "invalid_input_record", "index": index})
            continue
        record_id = record["id"]
        if record_id in expected:
            conflicts.append({"code": "duplicate_input_month", "month": record_month})
            continue
        expected[record_id] = {field: record[field] for field in _PAYLOAD_FIELDS}
    if not records:
        conflicts.append({"code": "empty_input"})
    return expected, conflicts


def _same_payload(actual, expected):
    """Extra fields are preserved, but required fields must match in type/value."""
    return isinstance(actual, dict) and all(
        type(actual.get(field)) is type(expected[field])
        and actual.get(field) == expected[field]
        for field in _PAYLOAD_FIELDS
    )


def _chunks(values):
    for start in range(0, len(values), BATCH_SIZE):
        yield values[start : start + BATCH_SIZE]


def _read_back(client, expected):
    """Read each target once, in groups, without automatic RPC retries."""
    collection = client.collection("data")
    snapshots = {}
    for record_ids in _chunks(list(expected)):
        references = [collection.document(record_id) for record_id in record_ids]
        # get_all yields a stream: consume it inside the caller's try block.
        for snapshot in client.get_all(
            references, retry=None, timeout=RPC_TIMEOUT_SECONDS
        ):
            snapshots[snapshot.id] = snapshot
    matched = []
    missing = []
    conflicts = []
    for record_id, payload in expected.items():
        snapshot = snapshots.get(record_id)
        if snapshot is None:
            # A complete response should include even absent documents.  Do not
            # confuse an incomplete/malformed response with confirmed absence.
            raise RuntimeError("incomplete_readback")
        if not snapshot.exists:
            missing.append(record_id)
        elif _same_payload(snapshot.to_dict(), payload):
            matched.append(record_id)
        else:
            conflicts.append({"code": "stored_content_mismatch", "id": record_id})
    return matched, missing, conflicts


def verify_records(client, records):
    """Compare every target document to its CSV-derived required field values."""
    report = _report(len(records))
    expected, conflicts = _validated_records(records)
    report["remaining_ids"] = list(expected)
    if conflicts:
        report.update(status="conflict", conflicts=conflicts)
        return report
    try:
        matched, missing, conflicts = _read_back(client, expected)
    except Exception:
        report.update(status="network_error", errors=["verification_read_failed"])
        return report
    report.update(
        verified_count=len(matched),
        missing=missing,
        conflicts=conflicts,
        remaining_ids=[record_id for record_id in expected if record_id not in matched],
    )
    if missing or conflicts:
        report["status"] = "verification_failed"
    return report


def store_records(client, records):
    """Preflight all existing data, skip identical records, and only create new ones.

    Successful commits are counted as confirmed creations.  If a commit fails,
    a single readback attempt distinguishes absent records from records now
    present; presence following an unacknowledged commit is reported separately
    because its creator cannot be established.  No retry, update, or deletion
    is performed.  Call verify_records after success for independent readback.
    """
    report = _report(len(records))
    expected, conflicts = _validated_records(records)
    report["remaining_ids"] = list(expected)
    if conflicts:
        report.update(status="conflict", conflicts=conflicts)
        return report

    collection = client.collection("data")
    try:
        snapshots = collection.limit(MAX_EXISTING_DOCUMENTS + 1).get(
            retry=None, timeout=RPC_TIMEOUT_SECONDS
        )
    except Exception:
        report.update(status="network_error", errors=["preflight_read_failed"])
        return report
    if len(snapshots) > MAX_EXISTING_DOCUMENTS:
        report.update(
            status="conflict", conflicts=[{"code": "collection_scan_limit"}]
        )
        return report

    months = {payload["date"][:7]: record_id for record_id, payload in expected.items()}
    skipped = set()
    try:
        for snapshot in snapshots:
            record_id = snapshot.id
            actual = snapshot.to_dict()
            if record_id in expected:
                if _same_payload(actual, expected[record_id]):
                    skipped.add(record_id)
                else:
                    conflicts.append({"code": "existing_content_mismatch", "id": record_id})
            existing_month = _month(actual.get("date")) if isinstance(actual, dict) else None
            if existing_month in months and record_id != months[existing_month]:
                conflicts.append({"code": "duplicate_month", "id": record_id, "month": existing_month})
    except Exception:
        report.update(status="network_error", errors=["preflight_decode_failed"])
        return report
    report["skipped"] = len(skipped)
    new_ids = [record_id for record_id in expected if record_id not in skipped]
    report["remaining_ids"] = new_ids
    if conflicts:
        report.update(status="conflict", conflicts=conflicts)
        return report

    confirmed = []
    for record_ids in _chunks(new_ids):
        try:
            batch = client.batch()
            for record_id in record_ids:
                batch.create(collection.document(record_id), expected[record_id])
            batch.commit(retry=None, timeout=RPC_TIMEOUT_SECONDS)
        except Exception as exc:
            # Exception messages may contain credential or transport details.
            # Only a fixed category is retained, never str(exc) or repr(exc).
            already_exists = type(exc).__name__ == "AlreadyExists"
            report.update(
                status="conflict" if already_exists else "network_error",
                created=len(confirmed),
                created_confirmed=len(confirmed),
                created_ids=confirmed,
                errors=["concurrent_document_exists" if already_exists else "batch_create_failed"],
            )
            if already_exists:
                report["conflicts"] = [{"code": "concurrent_document_exists"}]
            try:
                matched, missing, read_conflicts = _read_back(client, expected)
            except Exception:
                report["errors"].append("failure_readback_failed")
                report["remaining_ids"] = [record_id for record_id in new_ids if record_id not in confirmed]
                report["uncertain_ids"] = [] if already_exists else list(record_ids)
            else:
                report["verified_count"] = len(matched)
                report["missing"] = missing
                report["conflicts"].extend(read_conflicts)
                report["remaining_ids"] = [record_id for record_id in expected if record_id not in matched]
                report["present_after_error_ids"] = [record_id for record_id in record_ids if record_id in matched]
                report["uncertain_ids"] = [] if already_exists else report["present_after_error_ids"].copy()
            report["uncertain_count"] = len(report["uncertain_ids"])
            return report
        confirmed.extend(record_ids)
    report.update(
        created=len(confirmed),
        created_confirmed=len(confirmed),
        created_ids=confirmed,
        remaining_ids=[],
    )
    return report
