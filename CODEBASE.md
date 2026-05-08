# Codebase Guide

This document provides an overview of the Passless codebase structure, conventions, and common tasks.

## Directory structure

```
src/
  __init__.py         # Package documentation
  app.py              # Flask factory and WebAuthn routes
  config.py           # Configuration management
  db.py               # Database layer
  load_env.py         # Environment variable loading
  server.py           # WSGI entrypoint
  web.py              # HTML template generators
  static/style.css    # Minimal CSS

tests/
  __init__.py
  test_app.py         # WebAuthn ceremony tests
  test_config.py      # Configuration parsing tests
  test_load_env.py    # Environment loading tests
  test_rpid_resolution.py  # RP ID selection tests
  support.py          # Test utilities

data/
  passless.db         # SQLite database (created at runtime)
  .gitkeep            # Directory marker

instructions/       # Assignment PDFs (reference)
  CSE722 Project 2.pdf
  CSE722 Lecture 7.pdf

.env.example        # Template environment variables
.env                # Local environment (git-ignored)
requirements.txt    # Python dependencies
README.md           # Quick start guide
DEPLOYMENT.md       # Full deployment runbook
REPORT.md           # Implementation report
CODEBASE.md         # This file
```

## Naming conventions

### Python naming (PEP 8)
- **Modules**: `snake_case` (e.g., `load_env.py`)
- **Classes**: `PascalCase` (e.g., `AppConfig`, `PasslessDatabase`)
- **Functions**: `snake_case` (e.g., `create_app()`, `load_config()`)
- **Constants**: `UPPER_CASE` (e.g., `DEFAULT_TRYCLOUDFLARE_ORIGIN_PATTERN`)
- **Private functions**: `_leading_underscore_snake_case` (e.g., `_parse_origin()`)

### Environment variables
- **Format**: `UPPER_SNAKE_CASE`
- **No Node/JS refs**: Use `APP_ENV` instead of `NODE_ENV`
- **Examples**: `APP_ENV`, `RP_ID`, `EXPECTED_ORIGIN`, `HTTPS_ENABLED`

### Database schema
- **Tables**: `snake_case` (e.g., `users`, `credentials`, `auth_challenges`)
- **Columns**: `snake_case` (e.g., `user_id`, `credential_id`, `public_key_b64`)
- **IDs**: UUIDs for user records; integers for auto-increment; base64url for binary data

## Key concepts

### Configuration hierarchy
1. **`load_config()`**: Called once at module import; creates immutable `AppConfig`
2. **`config` singleton**: Shared globally; accessed as `from .config import config`
3. **Frozen dataclass**: All fields are immutable; no runtime reconfiguration

### RP ID resolution
- **localhost flow**: Always uses `RP_ID=localhost` regardless of config
- **Tunnel flow**: Dynamically uses tunnel hostname (e.g., `abc123.trycloudflare.com`)
- **Named tunnels**: Fixed hostname allows stable cross-device passkey reuse
- **See**: `_resolve_effective_rp_id()` in `app.py`

### Challenge lifecycle
1. **Generate**: 32-byte random value with 5-minute TTL
2. **Store**: In `auth_challenges` table linked to username and flow type
3. **Verify**: Extracted from attestation/assertion response; must match stored value
4. **Consume**: Deleted immediately after verification (single-use)
5. **Expire**: Auto-purged if TTL exceeded

### Signature counter
- **Purpose**: Detects cloned or replayed authenticators
- **Monotonicity**: Must be strictly greater than previous value on each login
- **Update**: Incremented after successful authentication
- **Storage**: Persisted per credential in database

### Session management
- **Type**: Flask server-side session
- **Cookie**: HttpOnly, Secure (in production), SameSite=Lax
- **Lifetime**: 6 hours
- **See**: `SESSION_COOKIE_*` config in `app.py`

## Common tasks

### Running the app

```bash
# Local development
python -m src.server

# With HTTPS (self-signed)
APP_ENV=development HTTPS_ENABLED=true python -m src.server

# With Cloudflare Tunnel
cloudflared tunnel --url http://localhost:3000
```

### Running tests

```bash
# All tests
python -m unittest discover -s tests -p 'test_*.py'

# Single test module
python -m unittest tests.test_app

# Single test class
python -m unittest tests.test_app.AppTests

# Single test method
python -m unittest tests.test_app.AppTests.test_requires_display_name_for_first_time_registration
```

### Debugging

**Print debugging:**
```python
from flask import current_app
# Inside a route handler
current_app.logger.debug("Message: %s", value)
```

**Database inspection:**
```bash
sqlite3 data/passless.db
> SELECT * FROM users;
> SELECT * FROM credentials;
> SELECT * FROM auth_challenges;
```

**Flask shell:**
```bash
python -c "from src.app import create_app; from src.db import database; app = create_app(); ctx = app.app_context(); ctx.push(); print(database.get_user_by_username('alice'))"
```

**Tcpdump/network trace:**
```bash
tcpdump -A -s 0 'tcp port 3000 and (((ip[2:2] - ((ip[0]&xf)<<2)) - ((tcp[12]&xf0)>>2)) != 0)'
```

### Adding a new environment variable

1. **Add to `.env.example`**: Document the new variable with a comment
2. **Add to `src/config.py`**: Add a parser function if needed (e.g., `_parse_bool()`)
3. **Add to `AppConfig` dataclass**: Include the field
4. **Add to `load_config()`**: Extract the environment variable
5. **Update `AppConfig()` constructor call**: Pass the new field
6. **Update tests**: Test both the parser and the config loading

**Example:**
```python
# .env.example
CACHE_ENABLED=false

# src/config.py
cache_enabled = _parse_bool(os.environ.get("CACHE_ENABLED", "false"))

# In AppConfig dataclass
cache_enabled: bool

# In load_config()
cache_enabled=cache_enabled,

# In test support.py
"CACHE_ENABLED": "false",
```

### Adding a new route

1. **Choose the correct flow**: Registration (attestation) or authentication (assertion)
2. **Import helpers from `app.py`**: Use `_resolve_allowed_origin()`, `_resolve_effective_rp_id()`
3. **Validate origin**: Return 403 Forbidden if origin is invalid
4. **Use webauthn library**: Import and call `generate_*_options()` or `verify_*_response()`
5. **Handle errors gracefully**: Return meaningful error messages with appropriate HTTP status codes
6. **Write tests**: Add unit tests to validate verification logic

### Tracing an authentication issue

1. **Check APP_ENV**: Is it set correctly?
2. **Check RP_ID**: Does it match the browser's expected value?
3. **Check EXPECTED_ORIGIN**: Does it match the actual browser origin?
4. **Check challenges**: Are they being generated and stored?
5. **Check signature counter**: Is it being incremented?
6. **Review logs**: Look for "Invalid origin header" or verification errors

## Testing strategy

### Unit tests
- **Focus**: Config parsing, RP ID resolution, challenge validation
- **Coverage**: Positive cases, error cases, edge cases
- **Location**: `tests/test_*.py`

### Integration tests
- **Focus**: End-to-end WebAuthn ceremony
- **Coverage**: Registration + authentication for various scenarios
- **Isolation**: Use in-memory SQLite (`DB_PATH=:memory:`)

### Manual testing
- **Required**: Multi-browser, multi-device verification per assignment
- **Evidence**: Screenshots in browser/device matrix (see `REPORT.md`)

## Performance considerations

- **Database indexes**: Added on `auth_challenges (username, flow_type)` for fast lookup
- **Challenge TTL**: 5 minutes balances security and UX (configurable via `CHALLENGE_TTL_SECONDS`)
- **Session lifetime**: 6 hours (configurable via `PERMANENT_SESSION_LIFETIME`)
- **In-memory DB**: Used for tests to avoid disk I/O

## Security considerations

- **Challenge single-use**: Deleted after verification to prevent replay
- **Counter validation**: Monotonically increasing; failure indicates cloned authenticator
- **Origin validation**: Prevents phishing by binding credentials to registered origin
- **RP ID hash**: Prevents credential binding to wrong relying party
- **User verification**: Required during registration and authentication
- **Session security**: HttpOnly and Secure cookies in production
- **No passwords stored**: Only public keys and WebAuthn attestation data

## Future improvements

- Add logging to all critical paths (challenge generation, verification, counter updates)
- Add metrics/telemetry for registration and authentication latency
- Add rate limiting on registration/authentication endpoints
- Implement credential revocation/deletion UI
- Add backup codes for account recovery
- Support resident key (discoverable credential) workflows
- Add support for platform authenticator attestation verification
