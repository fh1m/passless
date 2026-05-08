from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from src.load_env import load_runtime_env


class LoadEnvTests(unittest.TestCase):
    def test_loads_env_files_with_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir)
            (env_dir / ".env").write_text("SOURCE=base\nCOMMON=base\n", encoding="utf-8")
            (env_dir / ".env.production").write_text(
                "COMMON=production\nPRODUCTION_ONLY=yes\n", encoding="utf-8"
            )
            (env_dir / ".env.local").write_text("LOCAL_ONLY=present\n", encoding="utf-8")
            (env_dir / ".env.production.local").write_text("COMMON=production-local\n", encoding="utf-8")

            runtime_env: dict[str, str] = {"COMMON": "already-set"}
            loaded = load_runtime_env(env_dir=env_dir, node_env="production", process_env=runtime_env)

            self.assertEqual(
                [Path(path).name for path in loaded],
                [".env.production.local", ".env.local", ".env.production", ".env"],
            )
            self.assertEqual(runtime_env["COMMON"], "already-set")
            self.assertEqual(runtime_env["SOURCE"], "base")
            self.assertEqual(runtime_env["LOCAL_ONLY"], "present")
            self.assertEqual(runtime_env["PRODUCTION_ONLY"], "yes")

    def test_skips_env_files_in_test_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir)
            (env_dir / ".env").write_text("SOURCE=base\n", encoding="utf-8")

            runtime_env: dict[str, str] = {}
            loaded = load_runtime_env(env_dir=env_dir, node_env="test", process_env=runtime_env)

            self.assertEqual(loaded, [])
            self.assertNotIn("SOURCE", runtime_env)


if __name__ == "__main__":
    unittest.main()
