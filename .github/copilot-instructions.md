# Copilot Instructions for `passless`

## Repository baseline

- This repository contains a Python/Flask WebAuthn proof-of-concept with source in `src/`, tests in `tests/`, and documentation in `README.md`, `DEPLOYMENT.md`, and `REPORT.md`.
- Treat the PDFs in `instructions/` as the primary requirement source.

## Build, test, and lint commands

- No build or lint tooling is currently defined in this repository.
- Test command:
  - `python -m unittest discover -s tests -p 'test_*.py'`
- Single-test command:
  - `python -m unittest tests.test_app`
- When implementation files and a stack are added, update this section with any new build or lint/format command(s).

## High-level architecture to follow

Implement and maintain a passwordless WebAuthn service with these major parts:

1. **HTTPS web server + RP configuration**
   - Service must be reachable across devices/browsers.
   - Localhost is acceptable for development; remote device access requires TLS (self-signed cert or tunnel setup is acceptable).

2. **Registration flow (attestation)**
   - Backend generates registration options/challenge.
   - Frontend calls WebAuthn APIs and returns attestation response.
   - Backend verifies attestation and persists credential metadata tied to the user.

3. **Authentication flow (assertion)**
   - Backend generates authentication options/challenge.
   - Frontend obtains assertion via authenticator and sends response.
   - Backend verifies assertion and establishes authenticated session/state.

4. **Credential/authenticator persistence**
   - Store credential public key, credential ID, transports/authenticator metadata as needed by the chosen library.
   - Track and update signature counter on each successful login.

5. **Protected application surface**
   - After successful login, route to a protected page that confirms authentication and shows username + authenticator info.

## Key conventions for this codebase

- Keep implementation decisions aligned with the required WebAuthn verification checks. Server-side WebAuthn verification must explicitly cover:
  - challenge
  - origin
  - RP ID hash
  - user-present / user-verified flags
  - signature validity
  - signature counter validation + update
- Preserve multi-device/multi-browser support as a first-class requirement in API and session design.
- Maintain compatibility-testing artifacts (screenshots/notes per browser/device) because they are part of the required deliverable.
- If architecture/code decisions are ambiguous, prefer the requirement language in `instructions/` and the current repository documentation over generic templates.
