"""Configuration and connection tests using synthetic credentials and mocks only."""

import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from app import config
from app.config import FirebaseError, FirebaseSettings
from app.services import firestore as service


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_SECRET = "offline-test-private-value"


def credential_data(project_id="offline-project"):
    # Deliberately not a usable private key. Certificate parsing is mocked.
    return {
        "type": "service_account",
        "project_id": project_id,
        "private_key": TEST_SECRET,
        "client_email": "offline@example.invalid",
        "token_uri": "https://oauth2.googleapis.com/token",
    }


def settings(**overrides):
    values = {
        "project_id": "offline-project",
        "credentials_json": json.dumps(credential_data()),
        "credentials_path": "",
        "emulator_host": None,
    }
    values.update(overrides)
    return FirebaseSettings(**values)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        # The user permits writes inside this project only.
        local_dir = PROJECT_ROOT / ".local"
        local_dir.mkdir(exist_ok=True)
        self.temp_dir = tempfile.TemporaryDirectory(prefix="offline-test-", dir=local_dir)
        self.addCleanup(self.temp_dir.cleanup)
        self.temp_path = Path(self.temp_dir.name)

    def assert_safe_error(self, expected_code, candidate):
        with self.assertRaises(FirebaseError) as caught:
            config.validate_credentials(candidate)
        self.assertEqual(expected_code, caught.exception.code)
        self.assertNotIn(TEST_SECRET, str(caught.exception))
        return caught.exception

    def fixture_file(self):
        path = self.temp_path / "synthetic-credential.json"
        path.write_text(json.dumps(credential_data()), encoding="utf-8")
        return path

    def test_missing_project_is_reported(self):
        self.assert_safe_error("missing_project_id", settings(project_id=""))

    def test_missing_credentials_are_reported(self):
        self.assert_safe_error("missing_credentials", settings(credentials_json=""))

    def test_invalid_json_is_safe(self):
        self.assert_safe_error("invalid_json", settings(credentials_json="{" + TEST_SECRET))

    def test_json_must_be_an_object(self):
        self.assert_safe_error("invalid_credentials", settings(credentials_json="[]"))

    def test_non_service_account_is_rejected(self):
        data = credential_data()
        data["type"] = "authorized_user"
        self.assert_safe_error("invalid_credentials", settings(credentials_json=json.dumps(data)))

    def test_required_fields_are_checked(self):
        for field in ("private_key", "client_email", "token_uri"):
            with self.subTest(field=field):
                data = credential_data()
                data.pop(field)
                self.assert_safe_error("invalid_credentials", settings(credentials_json=json.dumps(data)))

    def test_missing_file_is_reported_without_exposing_path(self):
        path = self.temp_path / (TEST_SECRET + ".json")
        self.assert_safe_error(
            "credentials_file_missing",
            settings(credentials_json="", credentials_path=str(path)),
        )

    def test_relative_file_path_is_rejected(self):
        self.assert_safe_error(
            "credentials_path_not_absolute",
            settings(credentials_json="", credentials_path="relative-key.json"),
        )

    def test_file_credentials_are_read_from_explicit_path(self):
        path = self.fixture_file()
        result = config.validate_credentials(settings(credentials_json="", credentials_path=str(path)))
        self.assertEqual("offline-project", result["project_id"])

    def test_invalid_file_json_is_rejected(self):
        path = self.temp_path / "invalid.json"
        path.write_text("{" + TEST_SECRET, encoding="utf-8")
        self.assert_safe_error("invalid_json", settings(credentials_json="", credentials_path=str(path)))

    def test_project_mismatch_is_rejected(self):
        self.assert_safe_error(
            "project_mismatch",
            settings(credentials_json=json.dumps(credential_data("another-offline-project"))),
        )

    def test_json_credentials_take_priority_over_file(self):
        candidate = settings(credentials_path=str(self.temp_path / "absent.json"))
        result = config.validate_credentials(candidate)
        self.assertEqual("offline-project", result["project_id"])

    def test_invalid_json_does_not_fall_back_to_valid_file(self):
        candidate = settings(credentials_json="{", credentials_path=str(self.fixture_file()))
        self.assert_safe_error("invalid_json", candidate)

    def test_emulator_setting_is_blocked_even_when_empty(self):
        for emulator_host in ("127.0.0.1:8080", ""):
            with self.subTest(is_empty=emulator_host == ""):
                self.assert_safe_error("emulator_configured", settings(emulator_host=emulator_host))

    def test_settings_repr_hides_sensitive_fields(self):
        candidate = settings(credentials_path=TEST_SECRET)
        self.assertNotIn(TEST_SECRET, repr(candidate))
        self.assertNotIn("private_key", repr(candidate))

    def test_process_environment_takes_precedence_including_empty_values(self):
        dotenv = {
            "FIREBASE_PROJECT_ID": "dotenv-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "dotenv-path",
            "FIREBASE_SERVICE_ACCOUNT_JSON": "dotenv-json",
            "FIRESTORE_EMULATOR_HOST": "dotenv-emulator",
        }
        process = {
            "FIREBASE_PROJECT_ID": "process-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "",
            "FIREBASE_SERVICE_ACCOUNT_JSON": "",
            "FIRESTORE_EMULATOR_HOST": "",
        }
        with patch.dict(os.environ, process, clear=True), patch.object(config, "dotenv_values", return_value=dotenv):
            actual = config.load_firebase_settings()
        self.assertEqual("process-project", actual.project_id)
        self.assertEqual("", actual.credentials_path)
        self.assertEqual("", actual.credentials_json)
        self.assertEqual("", actual.emulator_host)

    def test_dotenv_path_is_absolute_and_independent_of_working_directory(self):
        previous = Path.cwd()
        try:
            os.chdir(self.temp_path)
            with patch.dict(os.environ, {}, clear=True), patch.object(config, "dotenv_values", return_value={}) as read:
                config.load_firebase_settings()
        finally:
            os.chdir(previous)
        call = read.call_args
        path = call.args[0] if call.args else call.kwargs["dotenv_path"]
        self.assertEqual(PROJECT_ROOT / "backend" / ".env", Path(path))
        self.assertTrue(Path(path).is_absolute())
        self.assertIs(False, call.kwargs["interpolate"])


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.saved_client = service._client
        service._client = None
        self.addCleanup(setattr, service, "_client", self.saved_client)
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        self.load = self.patches.enter_context(patch.object(service, "load_firebase_settings", return_value=settings()))
        self.validate = self.patches.enter_context(patch.object(service, "validate_credentials", return_value=credential_data()))
        self.certificate = self.patches.enter_context(patch.object(service.credentials, "Certificate"))
        self.get_app = self.patches.enter_context(patch.object(service.firebase_admin, "get_app", side_effect=ValueError("absent")))
        self.app = MagicMock()
        self.app.project_id = "offline-project"
        self.initialize = self.patches.enter_context(patch.object(service.firebase_admin, "initialize_app", return_value=self.app))
        self.make_client = self.patches.enter_context(patch.object(service.firestore, "client"))

    def test_client_initializes_once_and_uses_default_database(self):
        first = service.get_firestore_client()
        second = service.get_firestore_client()
        self.assertIs(first, second)
        self.initialize.assert_called_once()
        self.make_client.assert_called_once_with(app=self.app, database_id="(default)")
        self.assertIn("gajimaiso-firestore", str(self.initialize.call_args))

    def test_unowned_existing_named_app_is_rejected(self):
        self.get_app.side_effect = None
        self.get_app.return_value = self.app
        with self.assertRaises(FirebaseError) as caught:
            service.get_firestore_client()
        self.assertEqual("initialization_conflict", caught.exception.code)
        self.initialize.assert_not_called()
        self.make_client.assert_not_called()

    def test_existing_app_project_mismatch_is_blocked(self):
        self.get_app.side_effect = None
        self.app.project_id = "another-offline-project"
        self.get_app.return_value = self.app
        with self.assertRaises(FirebaseError) as caught:
            service.get_firestore_client()
        self.assertEqual("initialization_project_mismatch", caught.exception.code)
        self.make_client.assert_not_called()

    def test_configuration_failure_never_initializes_sdk(self):
        self.validate.side_effect = FirebaseError("missing_credentials")
        with self.assertRaises(FirebaseError) as caught:
            service.get_firestore_client()
        self.assertEqual("missing_credentials", caught.exception.code)
        self.certificate.assert_not_called()
        self.initialize.assert_not_called()

    def test_sdk_failure_is_safe_and_does_not_cache_client(self):
        self.certificate.side_effect = ValueError(TEST_SECRET)
        with self.assertRaises(FirebaseError) as caught:
            service.get_firestore_client()
        self.assertEqual("initialization_failed", caught.exception.code)
        self.assertNotIn(TEST_SECRET, str(caught.exception))
        self.assertIsNone(service._client)

    def test_concurrent_requests_initialize_only_once(self):
        barrier = threading.Barrier(6)

        def initialize(*args, **kwargs):
            time.sleep(0.03)
            return self.app

        def request_client(_):
            barrier.wait(timeout=3)
            return service.get_firestore_client()

        self.initialize.side_effect = initialize
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(request_client, range(6)))
        self.assertTrue(all(client is results[0] for client in results))
        self.initialize.assert_called_once()
        self.make_client.assert_called_once()


class ConnectionCheckTests(unittest.TestCase):
    def setUp(self):
        self.cli = importlib.import_module("scripts.check_firestore")
        self.client = MagicMock()
        self.ref = self.client.collection.return_value.document.return_value
        self.state = {"data": None}

        def create(payload, **kwargs):
            self.state["data"] = dict(payload)

        def get(**kwargs):
            snapshot = MagicMock()
            snapshot.exists = self.state["data"] is not None
            snapshot.to_dict.return_value = self.state["data"]
            snapshot.update_time = "offline-update-time"
            return snapshot

        def delete(**kwargs):
            self.state["data"] = None

        self.ref.create.side_effect = create
        self.ref.get.side_effect = get
        self.ref.delete.side_effect = delete

    def test_success_creates_reads_and_deletes_only_its_document(self):
        result = self.cli.run_connection_check(self.client, document_id="offline-run-id")
        self.assertTrue(result.check_ok)
        self.assertTrue(result.cleanup_ok)
        self.client.collection.assert_called_once_with("_connection_checks")
        self.client.collection.return_value.document.assert_called_once_with("offline-run-id")
        self.ref.create.assert_called_once()
        self.ref.delete.assert_called_once()
        self.assertIsNone(self.state["data"])
        self.assertGreaterEqual(self.ref.get.call_count, 3)
        self.assertIsNone(result.error_code)
        self.assertIsNone(result.cleanup_error_code)

    def test_all_document_requests_have_short_timeout_and_no_retry(self):
        self.cli.run_connection_check(self.client)
        for method in (self.ref.create, self.ref.get, self.ref.delete):
            for request in method.call_args_list:
                self.assertIsNone(request.kwargs["retry"])
                self.assertEqual(5, request.kwargs["timeout"])

    def test_existing_document_is_never_deleted(self):
        from google.api_core.exceptions import AlreadyExists

        self.state["data"] = {"existing": "leave-in-place"}
        self.ref.create.side_effect = AlreadyExists("already present")
        result = self.cli.run_connection_check(self.client, document_id="offline-collision")
        self.assertFalse(result.check_ok)
        self.ref.delete.assert_not_called()
        self.assertEqual({"existing": "leave-in-place"}, self.state["data"])

    def test_ambiguous_create_failure_attempts_owned_document_cleanup(self):
        def create_then_lose_response(payload, **kwargs):
            self.state["data"] = dict(payload)
            raise RuntimeError(TEST_SECRET)

        self.ref.create.side_effect = create_then_lose_response
        result = self.cli.run_connection_check(self.client)
        self.assertFalse(result.check_ok)
        self.assertTrue(result.cleanup_ok)
        self.ref.delete.assert_called_once()
        self.assertNotIn(TEST_SECRET, repr(result))

    def test_unrelated_document_is_preserved_during_cleanup(self):
        def create_then_find_unrelated_record(payload, **kwargs):
            self.state["data"] = {"another_run": True}
            raise RuntimeError(TEST_SECRET)

        self.ref.create.side_effect = create_then_find_unrelated_record
        result = self.cli.run_connection_check(self.client)
        self.assertFalse(result.check_ok)
        self.ref.delete.assert_not_called()
        self.assertEqual({"another_run": True}, self.state["data"])

    def test_cleanup_error_is_separate_and_safe(self):
        self.ref.delete.side_effect = RuntimeError(TEST_SECRET)
        result = self.cli.run_connection_check(self.client)
        self.assertTrue(result.check_ok)
        self.assertFalse(result.cleanup_ok)
        self.assertIsNotNone(result.cleanup_error_code)
        self.assertNotIn(TEST_SECRET, repr(result))

    def test_without_live_option_no_client_is_created(self):
        output = io.StringIO()
        with patch.object(self.cli, "load_firebase_settings", return_value=settings()), patch.object(
            self.cli, "validate_credentials", return_value=credential_data()
        ), patch.object(self.cli, "get_firestore_client") as client, contextlib.redirect_stdout(output):
            status = self.cli.main([])
        self.assertEqual(0, status)
        client.assert_not_called()
        self.assertNotIn(TEST_SECRET, output.getvalue())

    def test_missing_configuration_exits_once_without_connecting(self):
        output = io.StringIO()
        with patch.object(self.cli, "load_firebase_settings", return_value=settings(credentials_json="")), patch.object(
            self.cli, "validate_credentials", side_effect=FirebaseError("missing_credentials")
        ) as validate, patch.object(self.cli, "get_firestore_client") as client, contextlib.redirect_stdout(output):
            status = self.cli.main([])
        self.assertEqual(2, status)
        validate.assert_called_once()
        client.assert_not_called()

    def test_live_option_with_emulator_never_connects(self):
        output = io.StringIO()
        candidate = settings(emulator_host="127.0.0.1:8080")
        with patch.object(self.cli, "load_firebase_settings", return_value=candidate), patch.object(
            self.cli, "get_firestore_client"
        ) as client, contextlib.redirect_stdout(output):
            status = self.cli.main(["--live"])
        self.assertEqual(2, status)
        client.assert_not_called()

    def test_internal_worker_options_also_require_live(self):
        for options in (["--worker"], ["--worker", "--cleanup-only"]):
            with self.subTest(options=options), patch.object(self.cli, "get_firestore_client") as client:
                with contextlib.redirect_stdout(io.StringIO()):
                    status = self.cli.main(options)
                self.assertEqual(2, status)
                client.assert_not_called()

    def test_worker_timeout_attempts_only_one_cleanup_for_same_document(self):
        timeout = self.cli.subprocess.TimeoutExpired("offline-worker", 35)
        cleanup = self.cli.CheckResult(False, True, "timeout", None)
        with patch.object(self.cli, "_invoke_worker", side_effect=[timeout, cleanup]) as worker:
            with contextlib.redirect_stdout(io.StringIO()):
                status = self.cli._run_bounded_live()
        self.assertEqual(1, status)
        self.assertEqual(2, worker.call_count)
        initial, final = worker.call_args_list
        self.assertEqual(initial.args[0], final.args[0])
        self.assertFalse(initial.kwargs["cleanup_only"])
        self.assertTrue(final.kwargs["cleanup_only"])
        self.assertLessEqual(initial.kwargs["timeout"], 35)
        self.assertLessEqual(final.kwargs["timeout"], 20)

    def test_worker_and_cleanup_timeouts_report_cleanup_failure(self):
        timeout = self.cli.subprocess.TimeoutExpired("offline-worker", 35)
        output = io.StringIO()
        with patch.object(self.cli, "_invoke_worker", side_effect=timeout) as worker:
            with contextlib.redirect_stdout(output):
                status = self.cli._run_bounded_live()
        self.assertEqual(3, status)
        self.assertEqual(2, worker.call_count)
        self.assertIn("정리 실패", output.getvalue())

    def test_popen_timeout_stops_tree_before_starting_cleanup(self):
        initial = MagicMock()
        initial.pid = 12345
        initial.communicate.side_effect = self.cli.subprocess.TimeoutExpired("offline-worker", 35)
        cleanup = MagicMock()
        cleanup.communicate.return_value = (
            json.dumps({"check_ok": False, "cleanup_ok": True,
                        "error_code": "timeout", "cleanup_error_code": None}),
            None,
        )
        cleanup.returncode = 1
        events = []

        def start(command, **kwargs):
            if "--cleanup-only" in command:
                events.append("cleanup-start")
                return cleanup
            events.append("worker-start")
            return initial

        def terminate(process):
            self.assertIs(initial, process)
            events.append("tree-stopped")

        with patch.object(self.cli.subprocess, "Popen", side_effect=start) as popen, patch.object(
            self.cli, "_terminate_worker_tree", side_effect=terminate
        ) as stop, contextlib.redirect_stdout(io.StringIO()):
            status = self.cli._run_bounded_live()
        self.assertEqual(1, status)
        self.assertEqual(["worker-start", "tree-stopped", "cleanup-start"], events)
        self.assertEqual(2, popen.call_count)
        stop.assert_called_once_with(initial)
        self.assertEqual(initial.communicate.call_args.kwargs["input"],
                         cleanup.communicate.call_args.kwargs["input"])
        self.assertEqual(35, initial.communicate.call_args.kwargs["timeout"])
        self.assertEqual(20, cleanup.communicate.call_args.kwargs["timeout"])

    def test_windows_tree_stop_targets_only_owned_pid_and_is_bounded(self):
        process = MagicMock()
        process.pid = 12345
        process.poll.return_value = None
        fake_os = MagicMock()
        fake_os.name = "nt"
        with patch.object(self.cli, "os", fake_os), patch.object(self.cli.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.cli._terminate_worker_tree(process)
        run.assert_called_once()
        self.assertEqual(["taskkill", "/PID", "12345", "/T", "/F"], run.call_args.args[0])
        self.assertEqual(5, run.call_args.kwargs["timeout"])
        process.communicate.assert_called_once_with(timeout=5)

    def test_failed_windows_tree_stop_is_reported(self):
        process = MagicMock()
        process.pid = 12345
        process.poll.return_value = None
        fake_os = MagicMock()
        fake_os.name = "nt"
        with patch.object(self.cli, "os", fake_os), patch.object(self.cli.subprocess, "run") as run:
            run.return_value.returncode = 1
            with self.assertRaises(self.cli.WorkerTerminationError) as caught:
                self.cli._terminate_worker_tree(process)
        self.assertEqual(12345, caught.exception.pid)
        process.communicate.assert_not_called()

    def test_unconfirmed_tree_stop_prevents_any_cleanup_worker(self):
        process = MagicMock()
        process.pid = 12345
        process.communicate.side_effect = self.cli.subprocess.TimeoutExpired("offline-worker", 35)
        output = io.StringIO()
        with patch.object(self.cli.subprocess, "Popen", return_value=process) as popen, patch.object(
            self.cli, "_terminate_worker_tree", side_effect=self.cli.WorkerTerminationError(process.pid)
        ), contextlib.redirect_stdout(output):
            status = self.cli._run_bounded_live()
        self.assertEqual(3, status)
        popen.assert_called_once()
        self.assertIn("12345", output.getvalue())
        self.assertIn("정리 실패", output.getvalue())


if __name__ == "__main__":
    unittest.main()
