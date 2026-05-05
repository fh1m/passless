# passless

`passless` is a WebAuthn/passwordless authentication service for the CSE722 project.  
It supports registration on one device and authentication from other browsers/devices using passkeys.

## Features (v1)

- WebAuthn registration (attestation) and authentication (assertion) flows
- Server-side verification with challenge/origin/RP ID/signature/counter checks
- SQLite persistence for users and credentials (with signature counter updates)
- Session-based protected route (`/app`) and logout flow
- Minimal UI for register/login/protected pages
- HTTPS-ready configuration + Cloudflare Tunnel workflow for cross-device testing

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

## Architecture overview

### Flow

1. Client requests registration/authentication options.
2. Server generates challenge and stores it in SQLite with expiry.
3. Browser completes WebAuthn operation.
4. Client posts response to verify endpoint.
5. Server verifies challenge + origin + RP ID + cryptographic proof.
6. Server persists credential/counter updates and issues session.
7. Protected route uses session to authorize access.

### Project structure

```
src/
  app.ts            # Routes + WebAuthn endpoints + protected UI
  server.ts         # HTTP/HTTPS bootstrap
  config.ts         # Env/config validation
  db.ts             # SQLite schema + data access
  web.ts            # HTML layout helpers
  static/style.css  # UI stylesheet
tests/
  app.test.ts       # API/session integration tests
e2e/
  smoke.spec.ts     # Browser smoke test
```

## Security and verification details

Server verification explicitly checks:

- challenge (fresh + expected)
- origin (`EXPECTED_ORIGIN`)
- RP ID (`RP_ID`)
- user verification requirement
- assertion signature validity
- signature counter and counter update on success

Additional safeguards:

- Origin header enforcement for WebAuthn POST endpoints
- Input validation with Zod
- HTTP headers via Helmet
- HttpOnly session cookie

## Cross-device/browser testing (tunnels)

### Why browser shows RP ID/domain errors

If you see browser errors like **"The relying party ID is not a registrable domain suffix of, nor equal to the current domain"**, your `RP_ID` does not match the page origin host rules.
This app now derives RP ID from the request origin hostname for known tunnel hosts (for example `*.trycloudflare.com`, `*.ngrok-free.app`, `*.ngrok.io`).

### Quick start: Cloudflare quick tunnel (`*.trycloudflare.com`)

1. Start app:

Linux/macOS:

```bash
npm run dev
```

Windows PowerShell:

```powershell
npm run dev
```

2. Start tunnel:

Linux/macOS:

```bash
cloudflared tunnel --url http://localhost:3000
```

Windows PowerShell:

```powershell
cloudflared tunnel --url http://localhost:3000
```

3. Keep local defaults and allow quick-tunnel origins:

```bash
RP_ID=localhost
EXPECTED_ORIGIN=http://localhost:3000
ALLOW_TRYCLOUDFLARE_ORIGIN=true
TRYCLOUDFLARE_ORIGIN_PATTERN=^https://[a-z0-9-]+\.trycloudflare\.com$
```

4. Restart server after `.env` changes, then open the generated tunnel URL.

### Fallback quick start: ngrok HTTP tunnel

1. Start app (`npm run dev`).
2. Start tunnel:

Linux/macOS:

```bash
ngrok http 3000
```

Windows PowerShell:

```powershell
ngrok http 3000
```

3. Allow ngrok random hosts in `.env`:

```bash
RP_ID=localhost
EXPECTED_ORIGIN=http://localhost:3000
ALLOW_NGROK_ORIGIN=true
NGROK_ORIGIN_PATTERN=^https://[a-z0-9-]+\.(?:ngrok-free\.app|ngrok\.io|ngrok\.app)$
```

4. Restart server after `.env` changes.

### Troubleshooting checklist (RP ID error focus)

- Confirm address bar host exactly matches `EXPECTED_ORIGIN` host.
- For quick/random tunnel hosts, keep `RP_ID=localhost`; RP ID is resolved from the request origin host.
- Do **not** set `RP_ID=trycloudflare.com` (browser rejects it for random subdomain pages).
- If using ngrok random hosts, set `ALLOW_NGROK_ORIGIN=true`.
- Do **not** reuse old tunnel values (quick tunnel hosts change every run).
- Restart `npm run dev` after every `.env` edit.
- Ensure `.env` is in repo root and loaded by the running process.
- Test WebAuthn from the same origin you configured (no mixed localhost/tunnel tabs).

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

## Assignment verification checklist

- [ ] Register passkey from desktop browser
- [ ] Login from desktop browser(s)
- [ ] Login from mobile browser(s)
- [ ] Confirm protected page shows username + authenticator info
- [ ] Capture screenshots of successful/unsuccessful tests per browser/device
- [ ] Document observed cross-browser issues in report
