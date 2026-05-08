"""Flask application factory and WebAuthn ceremony handlers.

This module implements the core WebAuthn flows:
- Registration (attestation ceremony): register new passkeys
- Authentication (assertion ceremony): verify existing passkeys

Each route verifies the appropriate WebAuthn data:
- Challenge validity and TTL
- Origin header matching
- RP ID hash verification
- Signature and user verification
- Signature counter monotonicity (replay protection)

Credential storage and multi-device support:
- One user account can have multiple credentials
- Multiple credentials per user enable same-username multi-device login
- RP ID and origin configuration determine cross-device credential reuse
"""

from __future__ import annotations

import base64
import json
from urllib.parse import urlsplit

from flask import Flask, jsonify, redirect, request, session
from werkzeug.middleware.proxy_fix import ProxyFix
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .config import config
from .db import (
    PasslessDatabase,
    database as default_database,
)
from .web import app_page, login_page, register_page


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _json_response(payload: object, status: int = 200):
    return jsonify(payload), status


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _parse_transports(raw: str) -> list[AuthenticatorTransport]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    transports: list[AuthenticatorTransport] = []
    for item in parsed:
        if not isinstance(item, str):
            continue
        try:
            transports.append(AuthenticatorTransport(item))
        except ValueError:
            continue
    return transports


def _transports_to_text(raw: str) -> str:
    transports = _parse_transports(raw)
    return ", ".join(transport.value for transport in transports)


def _normalize_origin(origin: str) -> str | None:
    try:
        trimmed = origin.strip()
        if not trimmed or trimmed == "null":
            return None
        parsed = urlsplit(trimmed)
        normalized = f"{parsed.scheme}://{parsed.netloc}"
        return normalized if normalized == trimmed else None
    except Exception:
        return None


def _normalize_referer_to_origin(referer: str | None) -> str | None:
    if not referer:
        return None
    try:
        parsed = urlsplit(referer)
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        return None


def _header_value(value: str | None | list[str]) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _extract_hostname(host_header: str) -> str:
    if host_header.startswith("["):
        end = host_header.find("]")
        if end != -1:
            return host_header[1:end]
    return host_header.split(":", 1)[0]


def _is_dynamic_tunnel_hostname(hostname: str) -> bool:
    normalized = hostname.lower()
    return (
        normalized.endswith(".trycloudflare.com")
        or normalized.endswith(".ngrok-free.app")
        or normalized.endswith(".ngrok.io")
        or normalized.endswith(".ngrok.app")
    )


def _normalize_rp_id_host(hostname: str) -> str:
    return "localhost" if hostname in {"127.0.0.1", "::1"} else hostname


def _origin_is_allowed(origin: str) -> bool:
    if origin in config.expected_origins:
        return True
    if config.allow_trycloudflare_origin and config.trycloudflare_origin_regex:
        if config.trycloudflare_origin_regex.match(origin):
            return True
    if config.allow_ngrok_origin and config.ngrok_origin_regex:
        if config.ngrok_origin_regex.match(origin):
            return True
    return False


def _resolve_allowed_origin(req) -> str | None:
    x_client_origin = _header_value(req.headers.get("X-Client-Origin"))
    origin_header = _header_value(req.headers.get("Origin"))
    referer_header = _header_value(req.headers.get("Referer"))
    candidates = [x_client_origin, origin_header, _normalize_referer_to_origin(referer_header)]

    for candidate in candidates:
        if not candidate:
            continue
        normalized = _normalize_origin(candidate)
        if normalized and _origin_is_allowed(normalized):
            return normalized

    if not x_client_origin and not origin_header and not referer_header:
        host_header = _header_value(req.headers.get("Host"))
        if host_header:
            hostname = _extract_hostname(host_header)
            if not _is_dynamic_tunnel_hostname(hostname):
                protocol = req.headers.get("X-Forwarded-Proto") or req.scheme
                fallback_origin = f"{protocol}://{host_header}"
                normalized = _normalize_origin(fallback_origin)
                if normalized and _origin_is_allowed(normalized):
                    return normalized

    return None


def _resolve_effective_rp_id(allowed_origin: str) -> str:
    hostname = urlsplit(allowed_origin).hostname or ""
    if _is_dynamic_tunnel_hostname(hostname):
        return hostname
    return _normalize_rp_id_host(hostname)


def _expected_origins_for_verification(origin: str) -> str | list[str]:
    origins = list(config.expected_origins) if origin in config.expected_origins else [*config.expected_origins, origin]
    return origins[0] if len(origins) == 1 else origins


def _parse_register_payload(payload: object) -> tuple[str, str | None] | tuple[None, str]:
    if not isinstance(payload, dict):
        return None, "Invalid request"
    username = payload.get("username")
    if not isinstance(username, str) or not (3 <= len(username.strip()) <= 64):
        return None, "username is required"
    display_name = payload.get("displayName")
    if display_name is not None and (
        not isinstance(display_name, str) or not (1 <= len(display_name.strip()) <= 120)
    ):
        return None, "displayName is invalid"
    return _normalize_username(username), (display_name.strip() if isinstance(display_name, str) else None)


def _parse_username_payload(payload: object) -> tuple[str | None, str]:
    if not isinstance(payload, dict):
        return None, "Invalid request"
    username = payload.get("username")
    if not isinstance(username, str) or not (3 <= len(username.strip()) <= 64):
        return None, "username is required"
    return _normalize_username(username), ""


def create_app(database: PasslessDatabase | None = None) -> Flask:
    db = database or default_database
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.secret_key = config.session_secret
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=config.app_env == "production",
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 6,
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.database = db

    @app.get("/")
    def index():
        if session.get("user_id"):
            return redirect("/app")
        return redirect("/login")

    @app.get("/register")
    def register():
        return register_page()

    @app.get("/login")
    def login():
        return login_page()

    @app.get("/app")
    def protected():
        user_id = session.get("user_id")
        if not user_id:
            return redirect("/login")
        user = db.get_user_by_id(user_id)
        if not user:
            session.clear()
            return redirect("/login")
        credentials = db.get_credentials_by_username(user.username)
        latest = credentials[-1] if credentials else None
        return app_page(
            username=user.username,
            credential_count=len(credentials),
            authenticator_type=latest.device_type if latest else "unknown",
            backed_up=bool(latest.backed_up) if latest else False,
            transports=_transports_to_text(latest.transports_json) if latest else "N/A",
        )

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.get("/healthz")
    def healthz():
        return _json_response({"ok": True})

    @app.post("/api/register/options")
    def register_options():
        origin = _resolve_allowed_origin(request)
        if not origin:
            return _json_response({"error": "Invalid origin header"}, 403)
        parsed = _parse_register_payload(request.get_json(silent=True))
        if parsed[0] is None:
            return _json_response({"error": parsed[1]}, 400)
        username, display_name = parsed
        existing_user = db.get_user_by_username(username)
        if not existing_user and not display_name:
            return _json_response(
                {"error": "Display name is required for first-time registration"}, 400
            )
        user = existing_user or db.ensure_user(username, display_name or username)
        existing_credentials = [
            PublicKeyCredentialDescriptor(
                id=base64.urlsafe_b64decode(cred.credential_id + "=" * (-len(cred.credential_id) % 4)),
                transports=_parse_transports(cred.transports_json),
            )
            for cred in db.get_credentials_by_username(user.username)
        ]
        options = generate_registration_options(
            rp_id=_resolve_effective_rp_id(origin),
            rp_name=config.rp_name,
            user_name=user.username,
            user_id=user.id.encode("utf-8"),
            user_display_name=user.display_name,
            timeout=60000,
            exclude_credentials=existing_credentials,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
            attestation=AttestationConveyancePreference.NONE,
        )
        db.save_challenge(user.username, "register", options.challenge)
        return jsonify(json.loads(options_to_json(options)))

    @app.post("/api/register/verify")
    def register_verify():
        origin = _resolve_allowed_origin(request)
        if not origin:
            return _json_response({"error": "Invalid origin header"}, 403)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _json_response({"error": "Invalid request"}, 400)
        username = payload.get("username")
        response = payload.get("response")
        if not isinstance(username, str) or not isinstance(response, (dict, str)):
            return _json_response({"error": "Invalid request"}, 400)
        username = _normalize_username(username)
        expected_challenge = db.pop_valid_challenge(username, "register")
        if not expected_challenge:
            return _json_response({"error": "Registration challenge missing or expired"}, 400)
        user = db.get_user_by_username(username)
        if not user:
            return _json_response({"error": "User not found"}, 404)
        try:
            verification = verify_registration_response(
                credential=response,
                expected_challenge=expected_challenge,
                expected_origin=_expected_origins_for_verification(origin),
                expected_rp_id=_resolve_effective_rp_id(origin),
                require_user_verification=True,
            )
        except InvalidRegistrationResponse:
            return _json_response(
                {"verified": False, "error": "Registration verification failed"}, 401
            )
        credential_id = _b64url_encode(verification.credential_id)
        public_key_b64 = _b64url_encode(verification.credential_public_key)
        transports_json = "[]"
        if isinstance(response, dict):
            response_payload = response.get("response")
            if isinstance(response_payload, dict):
                transports = response_payload.get("transports")
                if isinstance(transports, list):
                    transports_json = json.dumps([item for item in transports if isinstance(item, str)])
        db.insert_credential(
            {
                "user_id": user.id,
                "credential_id": credential_id,
                "public_key_b64": public_key_b64,
                "counter": verification.sign_count,
                "transports_json": transports_json,
                "aaguid": verification.aaguid,
                "device_type": getattr(verification.credential_device_type, "value", str(verification.credential_device_type)),
                "backed_up": 1 if verification.credential_backed_up else 0,
            }
        )
        session["user_id"] = user.id
        session["username"] = user.username
        return _json_response({"verified": True})

    @app.post("/api/auth/options")
    def auth_options():
        origin = _resolve_allowed_origin(request)
        if not origin:
            return _json_response({"error": "Invalid origin header"}, 403)
        parsed = _parse_username_payload(request.get_json(silent=True))
        if parsed[0] is None:
            return _json_response({"error": parsed[1]}, 400)
        username = parsed[0]
        user = db.get_user_by_username(username)
        if not user:
            return _json_response({"error": "User not found"}, 404)
        credentials = db.get_credentials_by_username(username)
        if not credentials:
            return _json_response({"error": "No passkeys registered"}, 400)
        options = generate_authentication_options(
            rp_id=_resolve_effective_rp_id(origin),
            timeout=60000,
            user_verification=UserVerificationRequirement.REQUIRED,
            allow_credentials=[
                PublicKeyCredentialDescriptor(
                    id=base64.urlsafe_b64decode(cred.credential_id + "=" * (-len(cred.credential_id) % 4)),
                    transports=_parse_transports(cred.transports_json),
                )
                for cred in credentials
            ],
        )
        db.save_challenge(username, "auth", options.challenge)
        return jsonify(json.loads(options_to_json(options)))

    @app.post("/api/auth/verify")
    def auth_verify():
        origin = _resolve_allowed_origin(request)
        if not origin:
            return _json_response({"error": "Invalid origin header"}, 403)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _json_response({"error": "Invalid request"}, 400)
        username = payload.get("username")
        response = payload.get("response")
        if not isinstance(username, str) or not isinstance(response, (dict, str)):
            return _json_response({"error": "Invalid request"}, 400)
        username = _normalize_username(username)
        expected_challenge = db.pop_valid_challenge(username, "auth")
        if not expected_challenge:
            return _json_response({"error": "Authentication challenge missing or expired"}, 400)
        user = db.get_user_by_username(username)
        if not user:
            return _json_response({"error": "User not found"}, 404)
        credential_id = None
        if isinstance(response, dict):
            credential_id = response.get("id")
        credential = db.get_credential_by_credential_id(credential_id) if isinstance(credential_id, str) else None
        if not credential:
            return _json_response({"error": "Credential not found"}, 404)
        if credential.user_id != user.id:
            return _json_response({"error": "Credential does not belong to user"}, 401)
        try:
            verification = verify_authentication_response(
                credential=response,
                expected_challenge=expected_challenge,
                expected_origin=_expected_origins_for_verification(origin),
                expected_rp_id=_resolve_effective_rp_id(origin),
                require_user_verification=True,
                credential_public_key=base64.urlsafe_b64decode(
                    credential.public_key_b64 + "=" * (-len(credential.public_key_b64) % 4)
                ),
                credential_current_sign_count=credential.counter,
            )
        except InvalidAuthenticationResponse:
            return _json_response(
                {"verified": False, "error": "Authentication verification failed"}, 401
        )
        db.update_credential_counter(credential.credential_id, verification.new_sign_count)
        session["user_id"] = user.id
        session["username"] = user.username
        return _json_response({"verified": True})

    return app
