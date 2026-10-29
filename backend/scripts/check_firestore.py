"""Validate local settings, or explicitly run one temporary cloud check."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from uuid import uuid4

# Resolve imports from this file, regardless of the terminal's current folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import FirebaseError, load_firebase_settings, validate_credentials
from app.services.firestore import get_firestore_client


REQUEST_TIMEOUT = 5
LIVE_TIMEOUT = 35
CLEANUP_TIMEOUT = 20
TREE_STOP_TIMEOUT = 5
REAP_TIMEOUT = 5
COLLECTION = "_connection_checks"
MESSAGES = {
    "configuration": "Firebase 설정 또는 자격증명 검증에 실패했습니다.",
    "already_exists": "문서 ID가 이미 존재하여 검사와 삭제를 중단했습니다.",
    "missing_document": "저장한 테스트 문서를 조회하지 못했습니다.",
    "value_mismatch": "조회한 값이 저장한 값과 일치하지 않습니다.",
    "ownership_unknown": "문서 소유권을 확인할 수 없어 삭제하지 않았습니다.",
    "document_remains": "삭제 후에도 문서가 존재합니다. 추가 삭제는 하지 않았습니다.",
    "timeout": "요청 또는 전체 검사 제한 시간을 초과했습니다.",
    "permission_denied": "Firestore 접근 권한이 없습니다.",
    "unauthenticated": "Firebase 인증에 실패했습니다.",
    "unavailable": "Firestore에 연결할 수 없습니다.",
    "failed_precondition": "데이터베이스 상태 또는 문서 변경 조건을 확인해야 합니다.",
    "unexpected": "검사를 완료하지 못했습니다. 예외 원문은 비밀 보호를 위해 생략합니다.",
    "worker_failed": "검사 프로세스의 정상 종료를 확인하지 못했습니다.",
    "interrupted": "사용자가 검사를 중단했습니다.",
    "worker_termination_failed": "검사 프로세스 트리 종료를 확인하지 못해 추가 연결을 중단했습니다.",
    "cleanup_unverified": "제한 시간 내 테스트 문서 정리를 확인하지 못했습니다.",
}


@dataclass(frozen=True)
class CheckResult:
    check_ok: bool
    cleanup_ok: bool
    error_code: str | None = None
    cleanup_error_code: str | None = None


class WorkerTerminationError(RuntimeError):
    """The owned process tree may still run; never start competing cleanup."""

    def __init__(self, pid: int):
        self.pid = pid
        super().__init__("worker process tree termination is unverified")


def _classify_error(error: Exception) -> str:
    # Never include exception messages, credential values, or tracebacks.
    return {
        "AlreadyExists": "already_exists",
        "DeadlineExceeded": "timeout",
        "TimeoutError": "timeout",
        "Timeout": "timeout",
        "ReadTimeout": "timeout",
        "PermissionDenied": "permission_denied",
        "Unauthenticated": "unauthenticated",
        "ServiceUnavailable": "unavailable",
        "TransportError": "unavailable",
        "FailedPrecondition": "failed_precondition",
        "FirebaseError": "configuration",
    }.get(type(error).__name__, "unexpected")


def _payload(run_token: str) -> dict[str, str]:
    return {"run_token": run_token, "purpose": "firestore_connection_check"}


def _cleanup_document(client, document, payload: dict[str, str]) -> str | None:
    """Delete only a document with this run's exact values and update time."""
    try:
        snapshot = document.get(retry=None, timeout=REQUEST_TIMEOUT)
        if not snapshot.exists:
            return None
        if snapshot.to_dict() != payload or snapshot.update_time is None:
            return "ownership_unknown"
        option = client.write_option(last_update_time=snapshot.update_time)
        document.delete(option=option, retry=None, timeout=REQUEST_TIMEOUT)
        if document.get(retry=None, timeout=REQUEST_TIMEOUT).exists:
            return "document_remains"
        return None
    except Exception as error:
        return _classify_error(error)


def run_connection_check(
    client, *, document_id: str | None = None, run_token: str | None = None
) -> CheckResult:
    """Run one create/read/delete check using the supplied real or mock client."""
    document = client.collection(COLLECTION).document(document_id or uuid4().hex)
    payload = _payload(run_token or uuid4().hex)
    error_code = None
    cleanup_error_code = None
    check_ok = False
    create_attempted = False
    already_exists = False
    try:
        create_attempted = True
        document.create(payload, retry=None, timeout=REQUEST_TIMEOUT)
        snapshot = document.get(retry=None, timeout=REQUEST_TIMEOUT)
        if not snapshot.exists:
            error_code = "missing_document"
        elif snapshot.to_dict() != payload:
            error_code = "value_mismatch"
        else:
            check_ok = True
    except Exception as error:
        error_code = _classify_error(error)
        already_exists = error_code == "already_exists"
    finally:
        # A timed-out create may have succeeded remotely. Probe ownership first.
        # AlreadyExists is different: an existing document must never be deleted.
        if create_attempted and not already_exists:
            cleanup_error_code = _cleanup_document(client, document, payload)
    return CheckResult(check_ok, cleanup_error_code is None, error_code, cleanup_error_code)


def _exit_code(result: CheckResult) -> int:
    if not result.cleanup_ok:
        return 3
    return 0 if result.check_ok else 1


def _read_worker_input() -> tuple[str, str]:
    data = json.loads(sys.stdin.read())
    values = (data["document_id"], data["run_token"])
    if any(
        not isinstance(value, str)
        or len(value) != 32
        or any(character not in "0123456789abcdef" for character in value)
        for value in values
    ):
        raise ValueError("invalid worker input")
    return values


def _worker(cleanup_only: bool) -> int:
    try:
        document_id, run_token = _read_worker_input()
        client = get_firestore_client()
        if cleanup_only:
            document = client.collection(COLLECTION).document(document_id)
            cleanup_error = _cleanup_document(client, document, _payload(run_token))
            result = CheckResult(False, cleanup_error is None, "timeout", cleanup_error)
        else:
            result = run_connection_check(client, document_id=document_id, run_token=run_token)
    except Exception as error:
        result = CheckResult(False, not cleanup_only, _classify_error(error),
                             _classify_error(error) if cleanup_only else None)
    print(json.dumps(asdict(result)))
    return _exit_code(result)


def _terminate_worker_tree(process) -> None:
    """Stop only this invocation's process tree, with bounded confirmation."""
    if process.poll() is None:
        try:
            if os.name == "nt":
                stopped = subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=TREE_STOP_TIMEOUT,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if stopped.returncode != 0:
                    raise WorkerTerminationError(process.pid)
            else:
                # Popen below creates a new session solely for this worker.
                os.killpg(process.pid, signal.SIGKILL)
        except (Exception, KeyboardInterrupt):
            raise WorkerTerminationError(process.pid) from None
    try:
        # Drain inherited pipes and reap the launcher after tree termination.
        # A launcher-only exit with a remaining child cannot pass this timeout.
        process.communicate(timeout=REAP_TIMEOUT)
    except (Exception, KeyboardInterrupt):
        raise WorkerTerminationError(process.pid) from None


def _invoke_worker(data: dict[str, str], *, cleanup_only: bool, timeout: int) -> CheckResult:
    command = [sys.executable, str(Path(__file__).resolve()), "--live", "--worker"]
    if cleanup_only:
        command.append("--cleanup-only")
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        start_new_session=os.name != "nt",
    )
    try:
        stdout, _ = process.communicate(input=json.dumps(data), timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        _terminate_worker_tree(process)
        raise
    except Exception:
        _terminate_worker_tree(process)
        raise
    decoded = json.loads(stdout)
    if (
        set(decoded) != {"check_ok", "cleanup_ok", "error_code", "cleanup_error_code"}
        or type(decoded["check_ok"]) is not bool
        or type(decoded["cleanup_ok"]) is not bool
        or any(decoded[key] is not None and decoded[key] not in MESSAGES
               for key in ("error_code", "cleanup_error_code"))
    ):
        raise ValueError("invalid worker result")
    result = CheckResult(**decoded)
    if process.returncode != _exit_code(result):
        raise ValueError("invalid worker exit status")
    return result


def _run_bounded_live() -> int:
    data = {"document_id": uuid4().hex, "run_token": uuid4().hex}
    unconfirmed_pid = None
    try:
        result = _invoke_worker(data, cleanup_only=False, timeout=LIVE_TIMEOUT)
    except WorkerTerminationError as error:
        unconfirmed_pid = error.pid
        result = CheckResult(False, False, "worker_termination_failed", "cleanup_unverified")
    except (Exception, KeyboardInterrupt) as error:
        if isinstance(error, subprocess.TimeoutExpired):
            error_code = "timeout"
        elif isinstance(error, KeyboardInterrupt):
            error_code = "interrupted"
        else:
            error_code = "worker_failed"
        # Only a confirmed-terminated worker may be followed by cleanup.
        try:
            cleanup = _invoke_worker(data, cleanup_only=True, timeout=CLEANUP_TIMEOUT)
            result = CheckResult(False, cleanup.cleanup_ok, error_code, cleanup.cleanup_error_code)
        except WorkerTerminationError as termination_error:
            unconfirmed_pid = termination_error.pid
            result = CheckResult(False, False, error_code, "worker_termination_failed")
        except (Exception, KeyboardInterrupt):
            result = CheckResult(False, False, error_code, "cleanup_unverified")
    if result.check_ok and result.cleanup_ok:
        print("실제 Firestore 연결 검사 성공: 저장·조회 값 일치와 테스트 문서 삭제를 확인했습니다.")
    else:
        if result.check_ok:
            print("저장·조회 값 일치는 확인했지만 전체 연결 검사는 완료하지 못했습니다.")
        else:
            print("실제 Firestore 연결 검사 실패: " + MESSAGES[result.error_code or "unexpected"])
        if result.cleanup_ok:
            print("이번 실행의 테스트 문서 정리 확인 완료 또는 생성 전 실패입니다.")
        else:
            print("테스트 문서 정리 실패: " + MESSAGES[result.cleanup_error_code or "unexpected"])
            print("확인이 필요한 문서: " + COLLECTION + "/" + data["document_id"])
    if unconfirmed_pid is not None:
        print("종료 확인이 필요한 이번 검사 프로세스 PID: " + str(unconfirmed_pid))
    return _exit_code(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Firestore 로컬 설정 확인 / 명시적 실제 연결 검사")
    parser.add_argument("--live", action="store_true", help="실제 클라우드 저장·조회·삭제 검사 1회")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cleanup-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if (args.worker or args.cleanup_only) and not args.live:
        print("실제 연결에는 명시적인 --live 옵션이 필요합니다.")
        return 2
    if args.cleanup_only and not args.worker:
        print("정리 모드는 내부 검사 프로세스에서만 사용합니다.")
        return 2
    try:
        settings = load_firebase_settings()
        if settings.emulator_host is not None:
            if not args.worker:
                print("FIRESTORE_EMULATOR_HOST가 설정되어 클라우드 검사를 중단했습니다. 해당 설정을 해제하세요.")
            return 2
        validate_credentials(settings)
    except FirebaseError as error:
        if not args.worker:
            print("설정 검사 실패: " + str(error))
            print("backend/.env에 FIREBASE_PROJECT_ID와 GOOGLE_APPLICATION_CREDENTIALS(키 절대 경로)를 설정하세요.")
            print("배포용 FIREBASE_SERVICE_ACCOUNT_JSON을 사용하면 파일 경로보다 우선하며, 오류 시 우회하지 않습니다.")
            print("실제 Firestore 연결은 실행하지 않았습니다.")
        return 2
    except Exception:
        if not args.worker:
            print("로컬 설정 검사를 완료하지 못했습니다. 비밀 보호를 위해 예외 원문은 생략합니다.")
        return 2
    if not args.live:
        print("로컬 설정 형식과 프로젝트 ID 일치 확인 완료. 실제 Firestore 연결은 실행하지 않았습니다.")
        print("실제 연결 검사에는 --live 옵션을 명시하세요.")
        return 0
    if args.worker:
        return _worker(args.cleanup_only)
    return _run_bounded_live()


if __name__ == "__main__":
    raise SystemExit(main())
