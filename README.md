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
- origin (validated against configured allowlist/patterns)
- RP ID (derived from validated request-origin host, with tunnel-aware handling)
- user verification requirement
- assertion signature validity
- signature counter and counter update on success

Additional safeguards:

- Origin validation using `X-Client-Origin` → `Origin` → `Referer` origin candidates (strict allowlist/pattern checks)
- Input validation with Zod
- HTTP headers via Helmet
- HttpOnly session cookie

## Cross-device/browser testing (tunnels)

### Why browser shows RP ID/domain errors

If you see browser errors like **"The relying party ID is not a registrable domain suffix of, nor equal to the current domain"**, your `RP_ID` does not match the page origin host rules.
This app now derives RP ID from the request origin hostname for known tunnel hosts (for example `*.trycloudflare.com`, `*.ngrok-free.app`, `*.ngrok.io`).

### Recommended for final submission: named Cloudflare tunnel (fixed hostname)

Use a fixed hostname so the same passkey remains valid across sessions/devices.

1. Create a named tunnel and map a stable hostname in your Cloudflare zone (one-time setup).
2. Run the tunnel with that hostname pointing to `http://localhost:3000`.
3. Set `.env`:

```bash
RP_ID=<your-fixed-hostname>
EXPECTED_ORIGIN=https://<your-fixed-hostname>
```

4. Keep `ALLOW_TRYCLOUDFLARE_ORIGIN=false` for this stable setup.

This is the preferred way to satisfy the Project 2 multi-device requirement and bonus RP/origin correctness.

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

Important: quick tunnels generate a new hostname each run. Credentials created on an old hostname will not work on a different hostname.

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

### Username-based multi-device login workflow

If passkeys are not synced automatically between devices, use this flow:

1. On **Device A**, register username + display name.
2. On **Device B**, attempt login with the same username.
3. If browser says no matching passkey on Device B, open `/register` on Device B and register the **same username** (display name optional for existing user).
4. Log in again with the same username on Device B.

This keeps a single account username while storing multiple credentials (one per device if needed).

### Troubleshooting checklist (RP ID error focus)

- Confirm address bar host exactly matches `EXPECTED_ORIGIN` host.
- For quick/random tunnel hosts, keep `RP_ID=localhost`; RP ID is resolved from the request origin host.
- Do **not** set `RP_ID=trycloudflare.com` (browser rejects it for random subdomain pages).
- If using ngrok random hosts, set `ALLOW_NGROK_ORIGIN=true`.
- Do **not** reuse old tunnel values (quick tunnel hosts change every run).
- Restart `npm run dev` after every `.env` edit.
- Ensure `.env` is in repo root and loaded by the running process.
- Test WebAuthn from the same origin you configured (no mixed localhost/tunnel tabs).

### Cross-browser/device guidance for Project 2 report

Use this sequence for each browser/device pair (Chrome, Edge, Firefox/Safari if available, plus at least one mobile browser):

1. Open `/register` and create a passkey.
2. Sign out, then open `/login` and authenticate with that passkey.
3. Confirm `/app` shows username plus authenticator fields (type, backed up, transports).
4. Capture one success screenshot and one intentional failure screenshot.

Recommended manual matrix:

- Desktop Chrome (register + login)
- Desktop Edge or Firefox (login with same passkey)
- Mobile Chrome/Safari (login with cross-device passkey)

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

## Submission checklist

### Core WebAuthn functionality

- [ ] Register passkey from **at least one desktop browser** (Chrome, Edge, or Firefox)
- [ ] Login from **at least two different desktop browsers** (e.g., Chrome + Edge/Firefox)
- [ ] Login from **at least one mobile browser** (Chrome/Safari on Android/iOS)
- [ ] Confirm protected `/app` page displays:
  - Username
  - Authenticator type (platform/cross-platform)
  - Backed-up flag and transports if available

### Protocol strictness verification

- [ ] **RP ID validation**: Confirm `RP_ID` matches page origin host (non-localhost or fixed tunnel name)
- [ ] **Origin validation**: Verify strict checking via:
  - Test with correct origin → should succeed
  - Test with mismatched origin (e.g., wrong tunnel URL or different device origin) → should be rejected
- [ ] **Negative test: missing origin** → request without `Origin` header must be rejected
- [ ] **Negative test: credential mismatch** → login attempt with wrong credential/user must fail
- [ ] **Cross-device credential reuse**: Same passkey from Device A authenticates on Device B with same username

### Evidence and reporting

- [ ] Run test suite: `npm run test` (all API tests must pass)
- [ ] Capture **success screenshot** per browser/device combo (register/login success)
- [ ] Capture **failure screenshot** for at least one negative test
- [ ] Screenshot shows browser address bar (verifying origin/RP ID matching domain)
- [ ] Document RP/origin configuration and how it enables cross-device reuse

## How to verify protocol strictness

### 1. Local verification before tunnel deployment

Start the server locally:

```bash
npm run dev
```

Run the automated negative test suite:

```bash
npm run test:single -- tests/app.test.ts
```

This tests:

- Challenge validation (replay detection)
- Origin mismatch rejection
- RP ID hash verification
- Signature counter enforcement
- Invalid signature rejection

### 2. Cross-origin rejection test (manual)

With server running on `http://localhost:3000`:

1. Open `http://localhost:3000/login` in your browser.
2. Register or attempt login (succeeds if origin matches).
3. On another machine (or different tunnel URL), try to POST to the verify endpoints with a spoofed `Origin` header:

```bash
curl -X POST http://localhost:3000/register/verify \
  -H "Origin: https://attacker.com" \
  -H "Content-Type: application/json" \
  -d '{"response": {...}}'
```

Expected: **403 Forbidden** (origin rejected).

### 3. RP ID / origin hostname matching (manual with tunnel)

When deployed via tunnel (e.g., `https://myapp.trycloudflare.com`):

1. Set `.env`:

```bash
RP_ID=myapp.trycloudflare.com
EXPECTED_ORIGIN=https://myapp.trycloudflare.com
ALLOW_TRYCLOUDFLARE_ORIGIN=false
```

2. Register passkey at `https://myapp.trycloudflare.com/register`.
3. Browser should accept (RP ID matches hostname).
4. Try accessing from a different tunnel URL (e.g., `https://other.trycloudflare.com`).
5. Expected: browser error **"relying party ID is not a registrable domain suffix"**.

This proves RP ID validation is enforced at the browser level and server-side verification rejects mismatched origins.

### 4. Signature counter enforcement

Run the test suite to confirm counter increments and replays are rejected:

```bash
npm run test:single -- tests/app.test.ts -t "counter"
```

The test verifies:

- Counter starts at 0
- Counter increments on each assertion
- Assertion with stale counter is rejected (replay protection)

## Screenshots and evidence guidance

When filling out the report, include:

1. **Registration success**
   - Screenshot of browser at `https://<your-origin>/register` showing "Passkey registered" message
   - Include address bar in screenshot (proves RP ID / origin matching)

2. **Login success**
   - Screenshot of browser at `https://<your-origin>/login` showing "Logged in" confirmation
   - Screenshot of protected `/app` page showing username + authenticator details
   - Address bar visible

3. **Cross-device login**
   - Same passkey used on different device/browser
   - Screenshot from Device A showing login success
   - Screenshot from Device B showing same username/passkey recognized

4. **Negative test: missing origin**
   - Screenshot of browser console or server logs showing origin validation rejection
   - Or: curl output showing 403 response when `Origin` header missing

5. **Negative test: credential mismatch**
   - Screenshot showing login attempt with wrong username fails
   - Or: API test output showing rejection

## Project structure

See above for file tree. Key WebAuthn endpoints:

- `GET /register` — registration page
- `GET /register/options` — get registration challenge (JSON)
- `POST /register/verify` — verify attestation (JSON)
- `GET /login` — login page
- `GET /login/options` — get authentication challenge (JSON)
- `POST /login/verify` — verify assertion (JSON)
- `GET /app` — protected page (requires session)
- `POST /logout` — clear session
