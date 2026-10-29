"""Offline authentication/admission contracts; no real keys, AI or Firestore."""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import create_app
from app.config import load_allowed_origins
from app.security import ChatAdmission, load_access_token
from app.routers.data import get_data_service
from app.routers.chat import get_chat_service
from app.routers.conversations import get_conversation_service
from tests.test_data_api import FakeDataService

TOKEN = "offline-only-access-token-for-tests-012345"
HEADERS = {"Authorization": "Bearer " + TOKEN}
ID = "00000000-0000-4000-8000-000000000001"
PROTECTED = [("POST", "/api/data"), ("PUT", "/api/data/changwon-net-2042-02"),
             ("DELETE", "/api/data/changwon-net-2042-02"), ("POST", "/api/chat"),
             ("POST", "/api/conversations"), ("GET", "/api/conversations"),
             ("GET", "/api/conversations/" + ID), ("DELETE", "/api/conversations/" + ID)]


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch("app.security.load_access_token", return_value=TOKEN)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.app = create_app()
        self.client = TestClient(self.app)
        self.data = FakeDataService()
        self.app.dependency_overrides[get_data_service] = lambda: self.data

    def test_all_protected_paths_reject_missing_wrong_and_nonbearer_before_services(self):
        def forbidden():
            raise AssertionError("Protected service initialized before authentication")
        calls = Mock(side_effect=forbidden)
        def provider():
            return calls()
        for dependency in (get_data_service, get_chat_service, get_conversation_service):
            self.app.dependency_overrides[dependency] = provider
        for method, path in PROTECTED:
            for headers in ({}, {"Authorization": "Bearer incorrect"}, {"Authorization": "Basic incorrect"}):
                with self.subTest(method=method, path=path, headers=bool(headers)):
                    result = self.client.request(method, path, headers=headers)
                    self.assertEqual(401, result.status_code)
                    self.assertEqual("access_denied", result.json()["detail"]["code"])
                    self.assertNotIn(TOKEN, result.text)
        calls.assert_not_called()
        self.assertEqual([], list(self.app.state.chat_admission.attempts))

    def test_missing_server_token_fails_closed(self):
        with patch("app.security.load_access_token", return_value=""):
            for method, path in PROTECTED:
                self.assertEqual(403, self.client.request(method, path, headers=HEADERS).status_code)

    def test_public_routes_and_swagger_security_contract(self):
        for path in ("/health", "/docs", "/openapi.json", "/api/data", "/api/data/summary"):
            self.assertEqual(200, self.client.get(path).status_code)
        schema = self.client.get("/openapi.json").json()
        self.assertEqual("bearer", schema["components"]["securitySchemes"]["AppAccessToken"]["scheme"])
        for method, path in PROTECTED:
            if "changwon-net" in path or path.endswith(ID):
                path = path.rsplit("/", 1)[0] + "/{id}"
            self.assertEqual([{"AppAccessToken": []}], schema["paths"][path][method.lower()]["security"])
        self.assertNotIn("security", schema["paths"]["/api/data"]["get"])

    def test_authorized_data_create_update_delete_only_in_fake_store(self):
        payload = {"date": "2042-02-01", "value": -12, "memo": "offline test"}
        self.assertEqual(201, self.client.post("/api/data", json=payload, headers=HEADERS).status_code)
        payload["value"] = -15
        self.assertEqual(-15, self.client.put("/api/data/changwon-net-2042-02", json=payload, headers=HEADERS).json()["value"])
        self.assertEqual(204, self.client.delete("/api/data/changwon-net-2042-02", headers=HEADERS).status_code)
        self.assertEqual({}, self.data.records)

    def test_authorized_conversation_list_and_delete(self):
        service = Mock()
        service.list_conversations.return_value = []
        self.app.dependency_overrides[get_conversation_service] = lambda: service
        self.assertEqual(200, self.client.get("/api/conversations", headers=HEADERS).status_code)
        self.assertEqual(204, self.client.delete("/api/conversations/" + ID, headers=HEADERS).status_code)
        service.delete_conversation.assert_called_once_with(ID)

    def test_chat_limit_blocks_before_ai_and_failed_attempts_count(self):
        service = Mock()
        service.chat.side_effect = HTTPException(502, detail="offline AI error")
        provider = Mock(return_value=service)
        def get_service():
            return provider()
        self.app.dependency_overrides[get_chat_service] = get_service
        for _ in range(5):
            self.assertEqual(502, self.client.post("/api/chat", json={"message": "offline question"}, headers=HEADERS).status_code)
        limited = self.client.post("/api/chat", json={"message": "offline question"}, headers=HEADERS)
        self.assertEqual(429, limited.status_code)
        self.assertEqual("60", limited.headers["Retry-After"])
        self.assertEqual(5, provider.call_count)
        self.assertEqual(5, service.chat.call_count)
        self.assertFalse(self.app.state.chat_admission.active)

    def test_concurrent_admission_and_expiry(self):
        clock = Mock(return_value=0)
        gate = ChatAdmission(clock)
        gate.enter()
        with self.assertRaises(HTTPException):
            gate.enter()
        gate.leave()
        for _ in range(4):
            gate.enter(); gate.leave()
        with self.assertRaises(HTTPException):
            gate.enter()
        clock.return_value = 60
        gate.enter(); gate.leave()
        self.assertEqual([60], list(gate.attempts))

    def test_cors_authorization_allowed_only_for_configured_origin(self):
        headers = {"Origin": "http://127.0.0.1:5500", "Access-Control-Request-Method": "POST",
                   "Access-Control-Request-Headers": "Authorization,Content-Type"}
        self.assertEqual(200, self.client.options("/api/chat", headers=headers).status_code)
        headers["Origin"] = "https://unapproved.example"
        response = self.client.options("/api/chat", headers=headers)
        self.assertEqual(400, response.status_code)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_cors_wildcard_and_malformed_origins_fail_closed(self):
        for origins in ("*", "https://*.example.com", "https://user:pass@example.com", "https://example.com/path"):
            with patch.dict(os.environ, {"ALLOWED_ORIGINS": origins}):
                self.assertEqual([], load_allowed_origins())


class AccessSettingsTests(unittest.TestCase):
    def test_file_loading_process_precedence_and_invalid_tokens(self):
        with TemporaryDirectory() as directory:
            env = Path(directory) / ".env"
            env.write_text("APP_ACCESS_TOKEN=" + TOKEN, encoding="utf-8")
            with patch("app.security.ENV_FILE", env), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(TOKEN, load_access_token())
                for value in ("", "short", "space " * 8, "한" * 32):
                    with patch.dict(os.environ, {"APP_ACCESS_TOKEN": value}):
                        self.assertEqual("", load_access_token())
                with patch.dict(os.environ, {"APP_ACCESS_TOKEN": TOKEN + "new"}):
                    self.assertEqual(TOKEN + "new", load_access_token())


if __name__ == "__main__":
    unittest.main()
