from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.support import loaded_modules


class RpidResolutionTests(unittest.TestCase):
    def test_uses_localhost_rp_id_for_localhost_flow_even_if_config_is_stale(self) -> None:
        with loaded_modules({"RP_ID": "trycloudflare.com"}) as (app_module, db_module, _):
            db = db_module.PasslessDatabase(":memory:")
            self.addCleanup(db.close)
            app = app_module.create_app(database=db)
            client = app.test_client()

            with patch.object(app_module, "generate_registration_options", wraps=app_module.generate_registration_options) as mock_generate:
                response = client.post(
                    "/api/register/options",
                    base_url="http://localhost:3000",
                    headers={"Origin": "http://localhost:3000"},
                    json={"username": "local-user", "displayName": "Local User"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertTrue(mock_generate.called)
            self.assertEqual(mock_generate.call_args.kwargs["rp_id"], "localhost")

    def test_uses_tunnel_hostname_as_rp_id(self) -> None:
        with loaded_modules({"ALLOW_TRYCLOUDFLARE_ORIGIN": "true"}) as (app_module, db_module, _):
            db = db_module.PasslessDatabase(":memory:")
            self.addCleanup(db.close)
            app = app_module.create_app(database=db)
            client = app.test_client()
            origin = "https://abc123.trycloudflare.com"

            with patch.object(app_module, "generate_registration_options", wraps=app_module.generate_registration_options) as mock_generate:
                response = client.post(
                    "/api/register/options",
                    base_url=origin,
                    headers={"Origin": origin},
                    json={"username": "tunnel-user", "displayName": "Tunnel User"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(mock_generate.call_args.kwargs["rp_id"], "abc123.trycloudflare.com")

    def test_uses_tunnel_hostname_for_verification(self) -> None:
        with loaded_modules({"ALLOW_TRYCLOUDFLARE_ORIGIN": "true"}) as (app_module, db_module, _):
            db = db_module.PasslessDatabase(":memory:")
            self.addCleanup(db.close)
            app = app_module.create_app(database=db)
            client = app.test_client()
            origin = "https://abc123.trycloudflare.com"

            user = db.ensure_user("verify-user", "Verify User")
            db.save_challenge(user.username, "register", b"register-challenge")

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
            ) as mock_verify:
                response = client.post(
                    "/api/register/verify",
                    base_url=origin,
                    headers={"Origin": origin},
                    json={"username": user.username, "response": {"id": "credential-id", "response": {}}},
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(mock_verify.call_args.kwargs["expected_rp_id"], "abc123.trycloudflare.com")

            credential_id = "auth-cred"
            db.insert_credential(
                {
                    "user_id": user.id,
                    "credential_id": credential_id,
                    "public_key_b64": "AQID",
                    "counter": 0,
                    "transports_json": "[]",
                    "aaguid": "",
                    "device_type": "singleDevice",
                    "backed_up": 0,
                }
            )
            db.save_challenge(user.username, "auth", b"auth-challenge")

            with patch.object(
                app_module,
                "verify_authentication_response",
                return_value=SimpleNamespace(new_sign_count=1),
            ) as mock_auth_verify:
                auth_response = client.post(
                    "/api/auth/verify",
                    base_url=origin,
                    headers={"Origin": origin},
                    json={"username": user.username, "response": {"id": credential_id, "response": {}}},
                )

            self.assertEqual(auth_response.status_code, 200)
            self.assertEqual(mock_auth_verify.call_args.kwargs["expected_rp_id"], "abc123.trycloudflare.com")


if __name__ == "__main__":
    unittest.main()
