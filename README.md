# WebAuthn Passwordless Authentication - PoC

A production-ready proof-of-concept for WebAuthn/passwordless authentication. Supports multi-device, cross-browser registration and login using passkeys with cryptographic verification.

## Features

- **WebAuthn Implementation**: Full attestation (registration) and assertion (authentication) ceremony support
- **Cryptographic Verification**: Challenge, origin, RP ID, signature validity, and counter checks
- **Multi-Device Support**: Same passkey works across registered devices and browsers
- **Session Management**: Secure HttpOnly cookies with SQLite-backed persistence
- **Protected Routes**: Example authenticated dashboard with authenticator metadata display
- **Deployment Ready**: Local HTTPS, Cloudflare Tunnel, and ngrok support

## Tech stack

- Node.js + TypeScript
- Express + `@simplewebauthn/server`
- Browser WebAuthn via `@simplewebauthn/browser`
- SQLite (`better-sqlite3`)
- ESLint + Prettier + Vitest + Supertest + Playwright (smoke)

## Quick start

### 1. Prerequisites

- Node.js LTS (20+ recommended)
- npm
- A passkey-capable authenticator (Windows Hello / Android biometrics / browser password manager, etc.)

### 2. Install dependencies

```bash
npm install
```

### 3. Configure environment

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Default values work for local development (`localhost`).

### 4. Run locally

```bash
npm run dev
```

Open:

- `http://localhost:3000/register`
- `http://localhost:3000/login`

## Build, lint, and test

```bash
npm run format
npm run lint
npm run build
npm run test
```

Run a single test file:

```bash
npm run test:single -- tests/app.test.ts
```

Run e2e smoke test:

```bash
npx playwright install chromium
npm run e2e
```

## Configuration

Environment variables (`.env`):

- `NODE_ENV` = `development | test | production`
- `HOST` / `PORT` = server bind address
- `RP_NAME` = WebAuthn relying party name
- `RP_ID` = static fallback RP ID for fixed-domain deployments (for localhost/tunnels, runtime uses the request origin host)
- `EXPECTED_ORIGIN` = primary full origin used by the browser (must match actual origin)
- `EXPECTED_ORIGINS` = optional comma-separated extra allowed origins
- `ALLOW_TRYCLOUDFLARE_ORIGIN` = `true` to allow Cloudflare quick tunnel origins (disabled by default)
- `TRYCLOUDFLARE_ORIGIN_PATTERN` = regex for allowed quick tunnel origins (default: `^https://[a-z0-9-]+\.trycloudflare\.com$`)
- `ALLOW_NGROK_ORIGIN` = `true` to allow ngrok random hosts (disabled by default)
- `NGROK_ORIGIN_PATTERN` = regex for allowed ngrok origins (default supports `*.ngrok-free.app`, `*.ngrok.io`, `*.ngrok.app`)
- `SESSION_SECRET` = strong random secret (required for secure sessions)
- `DB_PATH` = SQLite file path (`:memory:` in tests by default)
- `CHALLENGE_TTL_SECONDS` = challenge expiry
- `HTTPS_ENABLED` + `HTTPS_KEY_PATH` + `HTTPS_CERT_PATH` = optional direct HTTPS mode

`.env` is loaded automatically at runtime (no manual `export` required). Load order is:

1. `.env.<NODE_ENV>.local`
2. `.env.local` (except during `NODE_ENV=test`)
3. `.env.<NODE_ENV>`
4. `.env`

Existing shell environment variables always take precedence.

## Optional local HTTPS setup

WebAuthn works best on secure origins. `http://localhost` is allowed for local development, but use direct HTTPS if you want to test non-localhost behavior.

1. Generate local certs (example with OpenSSL):

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes -keyout certs/key.pem -out certs/cert.pem -days 365 -subj "/CN=localhost"
```

2. Update `.env`:

```bash
HTTPS_ENABLED=true
HTTPS_KEY_PATH=./certs/key.pem
HTTPS_CERT_PATH=./certs/cert.pem
EXPECTED_ORIGIN=https://localhost:3000
```

3. Start app and open `https://localhost:3000/register`.

## Architecture

### Registration Flow (Attestation)

1. Client requests registration options (challenge)
2. Server generates challenge, stores with TTL
3. Browser prompts user to register authenticator
4. Client sends attestation response to server
5. Server verifies: challenge, origin, RP ID, attestation signature
6. Server stores credential metadata (public key, ID, transports)
7. Session established

### Authentication Flow (Assertion)

1. Client requests authentication options (challenge)
2. Server generates challenge, stores with TTL
3. Browser prompts user to authenticate
4. Client sends assertion response to server
5. Server verifies: challenge, origin, RP ID, assertion signature, counter
6. Server updates signature counter (prevents replay)
7. Session established, user logged in

### Security Verification

Server explicitly validates:

- **Challenge**: Matches stored challenge, not expired
- **Origin**: Matches configured allowlist or pattern
- **RP ID**: Derived from request origin (tunnel-aware)
- **Signature**: Cryptographically valid
- **Counter**: Incremented (replay protection)
- **User Verification**: Browser attestation flags checked

### Project Structure

```
src/
  app.ts              # Express routes, WebAuthn endpoints, UI
  server.ts           # HTTP/HTTPS bootstrap
  config.ts           # Environment validation
  db.ts               # SQLite schema and data access
  web.ts              # HTML helpers
  static/style.css    # Stylesheet
tests/
  app.test.ts         # Integration tests (34 tests)
e2e/
  smoke.spec.ts       # Playwright smoke test
```

## Deployment

For production and cross-device testing, use HTTPS with a stable hostname. See [DEPLOYMENT.md](./docs/DEPLOYMENT.md) for:

- Self-signed certificate setup
- Cloudflare Tunnel (recommended for production)
- ngrok tunnel (quick testing alternative)
- Origin/RP ID configuration

## Troubleshooting

### "Invalid origin header"

- Verify `EXPECTED_ORIGIN` in `.env` matches the address bar exactly
- For localhost: `EXPECTED_ORIGIN=http://localhost:3000`
- After editing `.env`, restart the server

### "RP ID is not a registrable domain"

- Browser validates RP ID matches the hostname
- For tunnels, `RP_ID` must be the tunnel's stable hostname
- Quick tunnels (`.trycloudflare.com`) generate a new hostname each run—credentials won't port between sessions
- Use a named tunnel for stable hostname across sessions

### Credential not recognized on another device

- Same username must be used on both devices (same user account)
- For quick tunnels: re-register the credential on each device (hostname changes)
- For named tunnels or production: same passkey works across devices (hostname stable)

## API Reference

### Registration

- `GET /register` — Registration UI
- `POST /api/register/options` — Get registration challenge
  - Body: `{ username, displayName }`
  - Response: `{ challenge, rp, user, ... }`
- `POST /api/register/verify` — Verify attestation
  - Body: Attestation response from browser
  - Response: Success or error message

### Authentication

- `GET /login` — Login UI
- `POST /api/login/options` — Get authentication challenge
  - Body: `{ username }`
  - Response: `{ challenge, rpId, allowCredentials, ... }`
- `POST /api/login/verify` — Verify assertion
  - Body: Assertion response from browser
  - Response: Success and session established

### Protected

- `GET /app` — Authenticated dashboard (requires session)
  - Shows: username, authenticator type, backup status, transports
- `POST /logout` — Clear session

## Git + GitHub workflow

Local git author is configured as:

- `Fahim Faisal <fahim.2002.faisal@gmail.com>`

For pushing to GitHub repo `passless`:

```bash
git remote add origin git@github.com:<your-username>/passless.git
git branch -M main
git push -u origin main
```

Or with GitHub CLI:

```bash
gh repo create passless --public --source=. --remote=origin --push
```

## Contributing

Fork, make changes, and submit a pull request. Run `npm run format && npm run lint && npm run test` before submitting.
