# Passless WebAuthn Passwordless Proof-of-Concept Report

## Abstract

Passless is a Python-based WebAuthn proof-of-concept that implements passwordless registration and authentication using passkeys and other WebAuthn authenticators. The browser ceremony follows the standard WebAuthn flow demonstrated by the classroom WebAuthn.io example. The service supports username-based accounts, multiple credentials per user, a protected post-login page, and deployment through localhost, local HTTPS, or Cloudflare Tunnel for multi-device testing. The backend verifies the protocol data required by the rubric, including challenge, origin, RP ID hash, user presence/verification, signature validity, and signature counter updates.

## 1. System overview

The service is implemented in Python with Flask and SQLite. The browser UI is server-rendered from the Python application, and the WebAuthn browser helper is loaded in-page, so no Node.js build pipeline is required.

### Core modules

- `src/app.py` - Flask routes, origin/RP resolution, WebAuthn ceremonies, and session handling
- `src/config.py` - environment parsing and validation
- `src/db.py` - SQLite persistence for users, credentials, and challenges
- `src/server.py` - runtime entrypoint and optional HTTPS startup
- `src/web.py` - HTML for registration, login, and protected pages
- `tests/` - unit tests for configuration, RP resolution, and WebAuthn behavior

### Python-specific implementation choices

- The backend uses Flask sessions with secure cookie settings.
- `ProxyFix` is enabled so tunneled deployments preserve the correct host and scheme.
- SQLite is used for durable local persistence with a simple schema and no external database service.
- Standard-library `ssl` support is used for local HTTPS when a certificate is configured.
- Environment variables are loaded early so local, tunnel, and production-like configurations share the same runtime path.

## 2. Requirement coverage

| Requirement | Implementation in Passless |
|---|---|
| Reachable on multiple browsers/devices | Localhost HTTPS, Cloudflare Tunnel, and named tunnel support |
| Secure context | `http://localhost` for development, or HTTPS for remote access |
| Full WebAuthn flow | Separate registration and authentication ceremonies using WebAuthn APIs |
| Supported authenticators | Platform authenticators, browser passkeys, and roaming authenticators |
| Protected page | `/app` shows the authenticated username and authenticator metadata |
| Server verification | Challenge, origin, RP ID hash, UP/UV, signature, and counter are enforced |
| Multi-device bonus | Stable RP/origin support plus multiple credentials per username |
| Negative test | Wrong-user and tampered-response rejection paths are implemented |

## 3. Registration ceremony

The registration flow follows the attestation ceremony:

1. The browser submits a username and optional display name.
2. The server creates or reuses the user record and generates a challenge.
3. The server returns registration options with a resolved RP ID, resident-key preference, and user verification required.
4. The browser invokes `navigator.credentials.create()`.
5. The browser sends the attestation response back to the server.
6. The server verifies:
   - challenge match
   - origin match
   - RP ID hash match
   - user verification requirement
   - attestation response integrity
7. The credential ID, public key, transports, authenticator type, backed-up flag, and signature counter are stored.

Important design details:

- The user handle is a UUID stored separately from the username.
- A username can own multiple credentials, which supports same-user multi-device enrollment.
- Display name is required only for first-time registration, which keeps repeat enrollment smooth.

## 4. Authentication ceremony

The authentication flow follows the assertion ceremony:

1. The browser submits a username.
2. The server loads all credentials for that user and returns authentication options.
3. The browser invokes `navigator.credentials.get()`.
4. The browser sends the assertion response back to the server.
5. The server verifies:
   - challenge match
   - origin match
   - RP ID hash match
   - user presence and user verification
   - assertion signature validity
   - signature counter monotonicity
6. The stored signature counter is updated after a successful login.
7. The user is redirected to the protected page.

The server also checks that the asserted credential belongs to the requested user. This prevents cross-user credential reuse.

## 5. Deployment and RP configuration

### Local development

- `RP_ID=localhost`
- `EXPECTED_ORIGIN=http://localhost:3000`
- `python -m src.server`

### Local HTTPS

For HTTPS on localhost, generate a self-signed certificate and enable:

- `HTTPS_ENABLED=true`
- `HTTPS_KEY_PATH=...`
- `HTTPS_CERT_PATH=...`

### Cloudflare Tunnel

The recommended multi-device testing command is:

```bash
cloudflared tunnel --url http://localhost:3000
```

For temporary tunnel testing, the backend can accept the generated trycloudflare origin pattern. For repeated cross-device reuse, a named tunnel with a fixed hostname is preferred so the RP ID stays stable.

### RP/origin policy

- Localhost testing uses `localhost` as the RP ID.
- Quick tunnels are suitable for temporary validation.
- Named tunnels or fixed domains are required for stable cross-device credential reuse.
- The browser sends `X-Client-Origin`, and the server falls back to standard origin headers only when appropriate.

## 6. Testing and evidence

### Automated tests

The repository includes unit tests for:

- configuration parsing
- RP ID resolution
- origin validation
- challenge handling
- registration and authentication verification paths
- multi-credential behavior

### Desktop browser matrix

| Browser | Registration | Login | Notes | Screenshot |
|---|---|---|---|---|
| Chrome | Pass/Fail | Pass/Fail | [Add note] | [Insert screenshot] |
| Firefox | Pass/Fail | Pass/Fail | [Add note] | [Insert screenshot] |
| Edge or Safari | Pass/Fail | Pass/Fail | [Add note] | [Insert screenshot] |

### Mobile browser matrix

| Browser | Registration | Login | Notes | Screenshot |
|---|---|---|---|---|
| Chrome on Android | Pass/Fail | Pass/Fail | [Add note] | [Insert screenshot] |
| Safari on iOS | Pass/Fail | Pass/Fail | [Add note] | [Insert screenshot] |
| Firefox on Android | Pass/Fail | Pass/Fail | [Add note] | [Insert screenshot] |

### Negative tests

| Test | Expected result | Screenshot |
|---|---|---|
| Wrong username/credential | Rejected with meaningful error | [Insert screenshot] |
| Tampered client data or signature | Rejected by verification | [Insert screenshot] |
| Replay of a used assertion | Rejected by counter check | [Insert screenshot] |
| Invalid origin | Rejected with origin error | [Insert screenshot] |

## 7. Conclusion

Passless satisfies the core WebAuthn requirements with a Python backend, strict protocol verification, stable deployment options, and practical multi-device support. The implementation is intentionally conservative on the server side: it validates the cryptographic ceremony data, maintains per-credential counters, and keeps the RP/origin configuration explicit so that login behavior is predictable across browsers and devices.

## Appendix A: Screenshot placeholders

- [Insert screenshot: registration on desktop browser]
- [Insert screenshot: login on desktop browser]
- [Insert screenshot: protected page on desktop browser]
- [Insert screenshot: registration on mobile browser]
- [Insert screenshot: login on mobile browser]
- [Insert screenshot: protected page on mobile browser]
- [Insert screenshot: negative test showing server rejection]
