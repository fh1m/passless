from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.support import loaded_modules


class AppTests(unittest.TestCase):
    def _build(self, overrides: dict[str, str] | None = None):
        modules = loaded_modules(overrides)
        app_module, db_module, _ = modules.__enter__()
        db = db_module.PasslessDatabase(":memory:")
        app = app_module.create_app(database=db)
        client = app.test_client()
        self.addCleanup(db.close)
        self.addCleanup(modules.__exit__, None, None, None)
        return app_module, db, client

    def test_healthz_returns_ok(self) -> None:
        _, _, client = self._build()
        response = client.get("/healthz", base_url="http://localhost:3000")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

    def test_redirects_anonymous_protected_access_to_login(self) -> None:
        _, _, client = self._build()
        response = client.get("/app", base_url="http://localhost:3000")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    def test_rejects_register_options_with_invalid_origin(self) -> None:
        _, _, client = self._build()
        response = client.post(
            "/api/register/options",
            base_url="http://localhost:3000",
            headers={"Origin": "http://evil.test"},
            json={"username": "alice", "displayName": "Alice"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "Invalid origin header")

    def test_accepts_register_options_when_origin_missing_but_host_is_valid(self) -> None:
        _, _, client = self._build()
        response = client.post(
            "/api/register/options",
            base_url="http://localhost:3000",
            json={"username": "alice", "displayName": "Alice"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("challenge", response.get_json())

    def test_accepts_register_options_with_x_client_origin(self) -> None:
        _, _, client = self._build()
        response = client.post(
            "/api/register/options",
            base_url="http://localhost:3000",
            headers={"X-Client-Origin": "http://localhost:3000"},
            json={"username": "alice", "displayName": "Alice"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json()["challenge"], str)

    def test_accepts_register_options_with_referer(self) -> None:
        _, _, client = self._build()
        response = client.post(
            "/api/register/options",
            base_url="http://localhost:3000",
            headers={"Referer": "http://localhost:3000/register"},
            json={"username": "alice", "displayName": "Alice"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json()["challenge"], str)

    def test_requires_display_name_for_first_time_registration(self) -> None:
        _, _, client = self._build()
        response = client.post(
            "/api/register/options",
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
            json={"username": "new-user"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"], "Display name is required for first-time registration"
        )

    def test_allows_second_device_registration_without_display_name(self) -> None:
        app_module, db, client = self._build()
        with patch.object(
            app_module,
            "verify_registration_response",
            return_value=SimpleNamespace(
                credential_id=b"credential-id",
                credential_public_key=b"\x01\x02\x03",
                sign_count=0,
                aaguid="",
                credential_device_type=SimpleNamespace(value="singleDevice"),
                credential_backed_up=False,
            ),
        ):
            first = client.post(
                "/api/register/options",
                base_url="http://localhost:3000",
                headers={"Origin": "http://localhost:3000"},
                json={"username": "multi-user", "displayName": "Multi User"},
            )
            self.assertEqual(first.status_code, 200)

            db.save_challenge("multi-user", "register", b"challenge")
            client.post(
                "/api/register/verify",
                base_url="http://localhost:3000",
                headers={"Origin": "http://localhost:3000"},
                json={"username": "multi-user", "response": {"id": "credential-id", "response": {}}},
            )

        second = client.post(
            "/api/register/options",
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
            json={"username": "multi-user"},
        )
        self.assertEqual(second.status_code, 200)
        self.assertIn("challenge", second.get_json())

    def test_rejects_register_verification_without_active_challenge(self) -> None:
        _, _, client = self._build()
        response = client.post(
            "/api/register/verify",
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
            json={"username": "alice", "response": {"id": "credential-id"}},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Registration challenge missing or expired")

    def test_accepts_auth_options_with_valid_origin(self) -> None:
        _, db, client = self._build()
        user = db.ensure_user("alice", "Alice")
        db.insert_credential(
            {
                "user_id": user.id,
                "credential_id": "cred-1",
                "public_key_b64": "AQID",
                "counter": 0,
                "transports_json": "[]",
                "aaguid": "",
                "device_type": "singleDevice",
                "backed_up": 0,
            }
        )
        response = client.post(
            "/api/auth/options",
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
            json={"username": "alice"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("challenge", response.get_json())

    def test_auth_options_without_origin_uses_host_fallback(self) -> None:
        _, db, client = self._build()
        user = db.ensure_user("alice", "Alice")
        db.insert_credential(
            {
                "user_id": user.id,
                "credential_id": "cred-1",
                "public_key_b64": "AQID",
                "counter": 0,
                "transports_json": "[]",
                "aaguid": "",
                "device_type": "singleDevice",
                "backed_up": 0,
            }
        )
        response = client.post(
            "/api/auth/options",
            base_url="http://localhost:3000",
            json={"username": "alice"},
        )
        self.assertEqual(response.status_code, 200)

    def test_rejects_auth_options_with_no_passkeys(self) -> None:
        _, db, client = self._build()
        db.ensure_user("alice", "Alice")
        response = client.post(
            "/api/auth/options",
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
            json={"username": "alice"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "No passkeys registered")

    def test_rejects_authentication_verification_without_active_challenge(self) -> None:
        _, db, client = self._build()
        user = db.ensure_user("alice", "Alice")
        db.insert_credential(
            {
                "user_id": user.id,
                "credential_id": "cred-1",
                "public_key_b64": "AQID",
                "counter": 0,
                "transports_json": "[]",
                "aaguid": "",
                "device_type": "singleDevice",
                "backed_up": 0,
            }
        )
        response = client.post(
            "/api/auth/verify",
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
            json={"username": "alice", "response": {"id": "cred-1"}},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Authentication challenge missing or expired")

    def test_rejects_authentication_with_unknown_credential_id(self) -> None:
        _, db, client = self._build()
        user = db.ensure_user("alice", "Alice")
        db.save_challenge("alice", "auth", b"challenge")
        response = client.post(
            "/api/auth/verify",
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
            json={"username": "alice", "response": {"id": "missing-cred"}},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Credential not found")

    def test_rejects_authentication_if_credential_does_not_belong_to_user(self) -> None:
        _, db, client = self._build()
        alice = db.ensure_user("alice", "Alice")
        bob = db.ensure_user("bob", "Bob")
        db.insert_credential(
            {
                "user_id": bob.id,
                "credential_id": "cred-bob",
                "public_key_b64": "AQID",
                "counter": 0,
                "transports_json": "[]",
                "aaguid": "",
                "device_type": "singleDevice",
                "backed_up": 0,
            }
        )
        db.save_challenge(alice.username, "auth", b"challenge")
        response = client.post(
            "/api/auth/verify",
            base_url="http://localhost:3000",
            headers={"Origin": "http://localhost:3000"},
            json={"username": "alice", "response": {"id": "cred-bob"}},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "Credential does not belong to user")


if __name__ == "__main__":
    unittest.main()
