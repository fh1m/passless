"""Load environment variables from .env files with precedence-based merging.

Precedence order (highest to lowest):
1. .env.{APP_ENV}.local (e.g., .env.production.local) - for local overrides in production deployments
2. .env.local - for shared local overrides
3. .env.{APP_ENV} (e.g., .env.production) - for environment-specific settings
4. .env - for base defaults

In test mode (APP_ENV=test), no .env files are loaded; only os.environ is used.

Usage:
    load_runtime_env()  # Load into os.environ (default behavior)
    load_runtime_env(env_dir=Path(...), process_env={})  # Load into custom dict

This supports flexible deployment: a single .env can be used for dev, while
production uses environment-specific overrides via .env.production.
"""

from __future__ import annotations

import os
from pathlib import Path


def _parse_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def load_runtime_env(
    *,
    env_dir: Path | None = None,
    app_env: str | None = None,
    process_env: dict[str, str] | None = None,
) -> list[str]:
    env_dir = env_dir or Path(__file__).resolve().parent.parent
    app_env = app_env or os.environ.get("APP_ENV", "development")
    if process_env is None:
        process_env = os.environ

    if app_env == "test":
        return []

    loaded: list[str] = []
    candidates = [f".env.{app_env}.local"]
    if app_env != "test":
        candidates.append(".env.local")
    candidates.extend([f".env.{app_env}", ".env"])

    for candidate in candidates:
        path = env_dir / candidate
        if not path.exists():
            continue
        if process_env is os.environ:
            _parse_env_file(path)
        else:
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].lstrip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key or key in process_env:
                    continue
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                process_env[key] = value
        loaded.append(str(path))

    return loaded
