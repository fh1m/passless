"""Test support utilities for loading modules with custom environment."""

from __future__ import annotations

import importlib
import os
from contextlib import contextmanager
from unittest.mock import patch


BASE_ENV = {
    "APP_ENV": "test",
    "EXPECTED_ORIGIN": "http://localhost:3000",
    "RP_ID": "localhost",
    "SESSION_SECRET": "x" * 32,
    "DB_PATH": ":memory:",
}


@contextmanager
def loaded_modules(overrides: dict[str, str] | None = None):
    env = {**BASE_ENV, **(overrides or {})}
    with patch.dict(os.environ, env, clear=True):
        import src.config as config_module
        import src.db as db_module
        import src.app as app_module

        importlib.reload(config_module)
        importlib.reload(db_module)
        importlib.reload(app_module)
        try:
            yield app_module, db_module, config_module
        finally:
            db_module.database.close()
