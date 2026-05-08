from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.support import loaded_modules


class ConfigTests(unittest.TestCase):
    def test_supports_multiple_expected_origins(self) -> None:
        with loaded_modules(
            {
                "EXPECTED_ORIGIN": "http://localhost:3000",
                "EXPECTED_ORIGINS": "https://alpha.example.com, https://beta.example.com/",
            }
        ) as (_, _, config_module):
            self.assertEqual(
                list(config_module.config.expected_origins),
                [
                    "http://localhost:3000",
                    "https://alpha.example.com",
                    "https://beta.example.com",
                ],
            )

    def test_builds_trycloudflare_regex_when_enabled(self) -> None:
        with loaded_modules({"ALLOW_TRYCLOUDFLARE_ORIGIN": "true"}) as (_, _, config_module):
            regex = config_module.config.trycloudflare_origin_regex
            self.assertIsNotNone(regex)
            self.assertTrue(regex and regex.match("https://a1b2c3.trycloudflare.com"))
            self.assertFalse(regex and regex.match("https://evil.example.com"))

    def test_builds_ngrok_regex_when_enabled(self) -> None:
        with loaded_modules({"ALLOW_NGROK_ORIGIN": "true"}) as (_, _, config_module):
            regex = config_module.config.ngrok_origin_regex
            self.assertIsNotNone(regex)
            self.assertTrue(regex and regex.match("https://abc123.ngrok-free.app"))
            self.assertTrue(regex and regex.match("https://demo.ngrok.io"))
            self.assertFalse(regex and regex.match("https://evil.example.com"))

    def test_throws_on_invalid_trycloudflare_pattern(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid TRYCLOUDFLARE_ORIGIN_PATTERN"):
            with loaded_modules(
                {
                    "ALLOW_TRYCLOUDFLARE_ORIGIN": "true",
                    "TRYCLOUDFLARE_ORIGIN_PATTERN": "[",
                }
            ):
                pass

    def test_throws_on_invalid_ngrok_pattern(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid NGROK_ORIGIN_PATTERN"):
            with loaded_modules({"ALLOW_NGROK_ORIGIN": "true", "NGROK_ORIGIN_PATTERN": "["}):
                pass


if __name__ == "__main__":
    unittest.main()
