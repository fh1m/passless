# Passless

**A Flask/WebAuthn course project exploring passkey registration and sign-in.**

The relying party verifies a signature without receiving the passkey's private
signing key. That removes the need for a server-side password verifier; it does
not make account metadata, sessions or the server's session-signing secret safe
to disclose. Synced passkeys also need a more careful description than “the
secret never leaves one device.”

## Status and limits

At the reviewed application snapshot [`f29f73d`](https://github.com/fh1m/passless/tree/f29f73d5a56045c839d26abff66a5ecdb4dc52c8),
additional credential enrollment does not adequately establish ownership of an
existing account. A valid WebAuthn registration is not, by itself, permission
to add a credential to that account. **This is coursework, not a production
authentication service.** This documentation correction does not change or fix
the application. The [technical review](https://fh1m.github.io/notes/passless/)
separates the working browser ceremony from the incomplete account policy.

![Registering a passkey, then signing in with it](assets/ceremony.png)

*Registered and signed in by a real Chrome with a virtual WebAuthn
authenticator (`WebAuthn.addVirtualAuthenticator` over the DevTools protocol).
No password was typed, because there isn't one.*

## What the server actually keeps

After that registration and one sign-in, here's the entire credential row in
SQLite:

| username | public_key_b64 | key length | counter | device_type |
|---|---|---:|---:|---|
| fh1m | `pQECAyYgASFYIKmUPLnH29V8…` | 103 chars (77 bytes, a COSE EC2 P-256 public key) | 2 | single_device |

The public key lets the server verify an assertion without holding the private
signing key. The database still contains account identifiers and credential
metadata worth protecting.

The counter rose to 2 in this virtual-authenticator demonstration. It is not a
universal clone detector: [WebAuthn's counter guidance](https://www.w3.org/TR/webauthn-2/#sctn-sign-counter)
is conditional, and some authenticators report zero. Challenge freshness,
signature verification and authorized account changes remain separate duties.

```mermaid
sequenceDiagram
  participant B as Browser + authenticator
  participant S as Passless (Flask)
  B->>S: username
  S->>B: challenge, RP ID, allowed credentials
  Note over B: satisfy user-verification request<br/>sign authenticatorData and SHA-256(clientDataJSON)
  B->>S: assertion: client data, authenticator data, signature
  Note over S: check challenge, origin, RP ID hash,<br/>UP/UV flags, signature, applicable counter policy
  S->>B: session cookie → /app
```

It was built as a course project (`instructions/` holds the brief).
[`REPORT.md`](REPORT.md) maps the original requirements to their implementation.
The reviewed snapshot's existing suite had **25 tests**, including invalid-origin,
missing-challenge, unknown-credential and wrong-user rejections. Passing that
suite did not establish the missing enrollment-ownership policy.

## Features

- Username-first registration and login
- Multiple credentials per username; existing-account enrollment authorization remains incomplete
- Library-based verification of challenge, origin, RP ID hash, user presence/verification, signature and applicable counter policy
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

## Development modes

Use synthetic accounts for local demonstrations. Do not expose real accounts
or treat the tunnel instructions as a production security recommendation while
the enrollment boundary remains unresolved.

- **Localhost:** `RP_ID=localhost`, `EXPECTED_ORIGIN=http://localhost:3000`
- **Local HTTPS:** enable `HTTPS_ENABLED=true` and provide certificate paths
- **Cloudflare quick tunnel:** use `cloudflared tunnel --url http://localhost:3000`
- **Named Cloudflare tunnel:** use a stable hostname for cross-device passkey reuse

See `DEPLOYMENT.md` for step-by-step setup.
