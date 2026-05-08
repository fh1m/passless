"""Passless WebAuthn proof-of-concept application package.

A Python/Flask implementation of passwordless authentication using WebAuthn (passkeys).
Supports registration with multiple authenticators per user and cross-device login via
stable RP ID configuration.

Modules:
    app: Flask application factory and route handlers
    config: Configuration loading and validation
    db: SQLite persistence layer
    load_env: Environment variable loading from .env files
    server: WSGI server entrypoint
    web: HTML template generators
"""
