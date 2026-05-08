# Passless

Passless is a Python/Flask proof-of-concept for passwordless WebAuthn authentication. It supports username-based registration, multiple passkeys per account, cross-browser login, and a protected page that shows authenticator details after sign-in.

## Features

- Username-first registration and login
- Multiple credentials per username for same-user multi-device use
- Server-side verification of challenge, origin, RP ID hash, user presence/verification, signature, and signature counter
- Protected authenticated page with username and authenticator metadata
- Localhost, self-signed HTTPS, Cloudflare Tunnel, and ngrok support
- Python-only backend; no Node.js build step required

## Repository layout

```text
src/
  app.py         # Flask routes, WebAuthn ceremonies, session handling
  config.py      # Environment parsing and origin/RP validation
  db.py          # SQLite persistence for users, credentials, challenges
  load_env.py    # Optional .env loading helper
  server.py      # Runtime entrypoint
  web.py         # Server-rendered HTML for register/login/dashboard pages
  static/        # CSS assets
tests/           # Unit tests
data/            # SQLite database location
instructions/    # Assignment PDFs
DEPLOYMENT.md    # Detailed runbook
REPORT.md        # Formal implementation report
```

## Prerequisites

- Python 3.14 or newer
- `cloudflared` for tunnel-based multi-device testing
- Optional: OpenSSL for generating a local self-signed certificate

## Local setup

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.server
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m src.server
```

Open:

- `http://localhost:3000/register`
- `http://localhost:3000/login`

## Cloudflare Tunnel for multi-device testing

The quickest way to expose the local service to other devices is:

```bash
cloudflared tunnel --url http://localhost:3000
```

Use the generated HTTPS URL on your other devices. For temporary testing, set:

```env
ALLOW_TRYCLOUDFLARE_ORIGIN=true
```

For repeated cross-device testing, prefer a named tunnel with a fixed hostname so the RP ID stays stable across browsers and devices.

## Configuration

Key environment variables are defined in `.env.example`:

- `HOST` / `PORT` - bind address
- `RP_NAME` - human-readable relying party name
- `RP_ID` - WebAuthn relying party ID
- `EXPECTED_ORIGIN` - primary browser origin
- `EXPECTED_ORIGINS` - optional comma-separated allow list
- `ALLOW_TRYCLOUDFLARE_ORIGIN` - permit trycloudflare hostnames
- `TRYCLOUDFLARE_ORIGIN_PATTERN` - regex for trycloudflare origins
- `ALLOW_NGROK_ORIGIN` - permit ngrok hostnames
- `NGROK_ORIGIN_PATTERN` - regex for ngrok origins
- `SESSION_SECRET` - long random session secret
- `DB_PATH` - SQLite database path
- `CHALLENGE_TTL_SECONDS` - challenge lifetime
- `HTTPS_ENABLED`, `HTTPS_KEY_PATH`, `HTTPS_CERT_PATH` - local HTTPS mode

## Testing

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Single test module:

```bash
python -m unittest tests.test_app
```

## Deployment modes

- **Localhost:** `RP_ID=localhost`, `EXPECTED_ORIGIN=http://localhost:3000`
- **Local HTTPS:** enable `HTTPS_ENABLED=true` and provide certificate paths
- **Cloudflare quick tunnel:** use `cloudflared tunnel --url http://localhost:3000`
- **Named Cloudflare tunnel:** use a stable hostname for cross-device passkey reuse

See `DEPLOYMENT.md` for step-by-step setup.
