"""Configuration loading, validation, and app state.

Environment variables are parsed into an immutable AppConfig dataclass that is
shared by the Flask app and all request handlers.

Key configuration areas:
- app_env: deployment environment (development/test/production)
- Origin validation: configured primary origin + pattern-based tunnel allowlist
- RP ID resolution: dynamically selected based on request origin
- Session and cookie security settings based on app_env
- Optional local HTTPS via self-signed certificate paths

The load_config() function is called once at module load time, so changes to
environment variables after import have no effect.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from urllib.parse import urlsplit

from .load_env import load_runtime_env

load_runtime_env()

DEFAULT_TRYCLOUDFLARE_ORIGIN_PATTERN = "^https://[a-z0-9-]+\\.trycloudflare\\.com$"
DEFAULT_NGROK_ORIGIN_PATTERN = "^https://[a-z0-9-]+\\.(?:ngrok-free\\.app|ngrok\\.io|ngrok\\.app)$"


def _parse_bool(value: str | None) -> bool:
    return value is not None and value.strip().lower() == "true"


def _parse_origin(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Origin cannot be empty")
    parsed = urlsplit(trimmed)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid origin: {value}")
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_origins_csv(value: str | None) -> list[str]:
    if not value:
        return []
    origins: list[str] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        origin = _parse_origin(item)
        if origin not in origins:
            origins.append(origin)
    return origins


def _parse_int(name: str, raw: str | None, default: int) -> int:
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {name}") from exc


def _compile_regex(name: str, pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid {name}") from exc


@dataclass(frozen=True)
class AppConfig:
    app_env: str
    host: str
    port: int
    rp_name: str
    rp_id: str
    expected_origin: str
    expected_origins: tuple[str, ...]
    allow_trycloudflare_origin: bool
    trycloudflare_origin_regex: re.Pattern[str] | None
    allow_ngrok_origin: bool
    ngrok_origin_regex: re.Pattern[str] | None
    session_secret: str
    db_path: str
    challenge_ttl_seconds: int
    https_enabled: bool
    https_key_path: str | None
    https_cert_path: str | None


def load_config() -> AppConfig:
    app_env = os.environ.get("APP_ENV", "development")
    host = os.environ.get("HOST", "0.0.0.0")
    port = _parse_int("PORT", os.environ.get("PORT"), 3000)
    rp_name = os.environ.get("RP_NAME", "Passless")
    rp_id = os.environ.get("RP_ID", "localhost")
    expected_origin_raw = os.environ.get("EXPECTED_ORIGIN", "http://localhost:3000")
    expected_origins_raw = os.environ.get("EXPECTED_ORIGINS")
    allow_trycloudflare_origin = _parse_bool(os.environ.get("ALLOW_TRYCLOUDFLARE_ORIGIN"))
    trycloudflare_origin_pattern = os.environ.get(
        "TRYCLOUDFLARE_ORIGIN_PATTERN", DEFAULT_TRYCLOUDFLARE_ORIGIN_PATTERN
    )
    allow_ngrok_origin = _parse_bool(os.environ.get("ALLOW_NGROK_ORIGIN"))
    ngrok_origin_pattern = os.environ.get("NGROK_ORIGIN_PATTERN", DEFAULT_NGROK_ORIGIN_PATTERN)
    session_secret = os.environ.get("SESSION_SECRET", "change-this-in-production-now")
    db_path = os.environ.get("DB_PATH") or (":memory:" if app_env == "test" else "./data/passless.db")
    challenge_ttl_seconds = _parse_int(
        "CHALLENGE_TTL_SECONDS", os.environ.get("CHALLENGE_TTL_SECONDS"), 300
    )
    https_enabled = _parse_bool(os.environ.get("HTTPS_ENABLED"))
    https_key_path = os.environ.get("HTTPS_KEY_PATH")
    https_cert_path = os.environ.get("HTTPS_CERT_PATH")

    expected_origins = [_parse_origin(expected_origin_raw), *_parse_origins_csv(expected_origins_raw)]
    deduped_expected_origins: list[str] = []
    for origin in expected_origins:
        if origin not in deduped_expected_origins:
            deduped_expected_origins.append(origin)

    trycloudflare_origin_regex = (
        _compile_regex("TRYCLOUDFLARE_ORIGIN_PATTERN", trycloudflare_origin_pattern)
        if allow_trycloudflare_origin
        else None
    )
    ngrok_origin_regex = (
        _compile_regex("NGROK_ORIGIN_PATTERN", ngrok_origin_pattern) if allow_ngrok_origin else None
    )

    if len(session_secret) < 16:
        raise ValueError("SESSION_SECRET must be at least 16 characters")

    return AppConfig(
        app_env=app_env,
        host=host,
        port=port,
        rp_name=rp_name,
        rp_id=rp_id,
        expected_origin=deduped_expected_origins[0],
        expected_origins=tuple(deduped_expected_origins),
        allow_trycloudflare_origin=allow_trycloudflare_origin,
        trycloudflare_origin_regex=trycloudflare_origin_regex,
        allow_ngrok_origin=allow_ngrok_origin,
        ngrok_origin_regex=ngrok_origin_regex,
        session_secret=session_secret,
        db_path=db_path,
        challenge_ttl_seconds=challenge_ttl_seconds,
        https_enabled=https_enabled,
        https_key_path=https_key_path,
        https_cert_path=https_cert_path,
    )


config = load_config()
