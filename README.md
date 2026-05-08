# WebAuthn Passwordless PoC

Minimal WebAuthn passwordless authentication with a Python backend and the same browser frontend flow.

## Features

- Registration and login with passkeys
- Server-side verification of challenge, origin, RP ID, signature, and counter
- Multi-device registration per username
- Protected dashboard showing authenticator metadata
- Localhost, HTTPS, Cloudflare Tunnel, and ngrok support

## Stack

- Python 3.14+
- Flask
- `webauthn`
- SQLite
- Vanilla browser WebAuthn UI served from the backend

## Quick start

### 1. Create a virtualenv

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

### 4. Run the server

```bash
python -m src.server
```

Open:

- `http://localhost:3000/register`
- `http://localhost:3000/login`

## Test

```bash
python -m unittest
```

Single file:

```bash
python -m unittest tests.test_app
```

## Configuration

- `NODE_ENV` = `development | test | production`
- `HOST` / `PORT` = bind address
- `RP_NAME` = relying party name
- `RP_ID` = relying party ID
- `EXPECTED_ORIGIN` = browser origin
- `EXPECTED_ORIGINS` = optional extra origins
- `ALLOW_TRYCLOUDFLARE_ORIGIN` / `ALLOW_NGROK_ORIGIN` = allow tunnel origins
- `SESSION_SECRET` = long random session secret
- `DB_PATH` = SQLite database path
- `CHALLENGE_TTL_SECONDS` = challenge expiry in seconds
- `HTTPS_ENABLED` + certificate paths = direct HTTPS mode

## Structure

```text
src/
  app.py        # Flask app and WebAuthn routes
  server.py     # Runtime entrypoint
  config.py     # Environment parsing
  db.py         # SQLite persistence
  web.py        # HTML helpers
  static/style.css
tests/
  test_*.py     # Python unit tests
```

## Deployment

See `DEPLOYMENT.md` for localhost, HTTPS, Cloudflare Tunnel, and ngrok setup.
