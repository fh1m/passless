# CSE722 Project 2 Report Template (Passless)

Use this scaffold to produce the final submission report.

## 1. Project summary

- Project title:
- Team members:
- GitHub repository link:
- Deployment URL(s):

## 2. Deployment and environment

### 2.1 Host and transport

- Local OS used for development:
- Remote access method:
  - [ ] Named Cloudflare Tunnel (recommended — fixed hostname, stable credentials)
  - [ ] Cloudflare Quick Tunnel (`*.trycloudflare.com` — hostname changes each run)
  - [ ] ngrok (random subdomain)
  - [ ] Other
- HTTPS handling details (cert/tunnel):
- Cross-device access verified on (list devices/networks used):

### 2.2 RP/origin configuration and verification

**Configuration:**

- Final RP ID: (must match the hostname in EXPECTED_ORIGIN)
- Final EXPECTED_ORIGIN: (primary origin, must be HTTPS for cross-device/non-localhost)
- ALLOW_TRYCLOUDFLARE_ORIGIN: true/false (only for quick tunnels)
- ALLOW_NGROK_ORIGIN: true/false (only for ngrok random hosts)

**Verification steps performed:**

1. **Static configuration check:**
   - [ ] `.env` RP_ID matches `EXPECTED_ORIGIN` hostname
   - [ ] For named tunnel: `RP_ID` matches fixed tunnel hostname (e.g., `myapp.company.com`)
   - [ ] For quick tunnel: `RP_ID=localhost` and `ALLOW_TRYCLOUDFLARE_ORIGIN=true`
   - [ ] SERVER logs on startup confirm correct RP ID and origin allowlist (if available)

2. **Browser-level RP ID validation:**
   - [ ] Registered passkey from origin matching RP ID → **success**
   - [ ] Attempted access from different tunnel URL (different host) → **browser rejects** with RP ID error (e.g., "relying party ID is not a registrable domain suffix")
   - This demonstrates RP ID is properly enforced at the browser level.

3. **Server-side origin validation:**
   - [ ] Attempted POST to `/register/verify` or `/login/verify` with `Origin: https://attacker.com` → **403 Forbidden**
   - [ ] Valid origin from configured allowlist → **200 OK** (if other validation passes)
   - Command example (replace localhost with your actual origin):
     ```bash
     curl -X POST http://localhost:3000/login/verify \
       -H "Origin: https://attacker.com" \
       -H "Content-Type: application/json" \
       -d '{...}'
     ```

4. **How stability was maintained:**
   - Named tunnel chosen (stable hostname across sessions)
   - OR: Quick tunnel used; all device tests completed in single tunnel session
   - OR: ngrok session kept running; all tests used same ngrok URL
   - Consequences of hostname changes: (describe if applicable)

## 3. WebAuthn registration (attestation) flow

1. Client requests registration options.
2. Server generates challenge + RP/user parameters.
3. Authenticator produces attestation response.
4. Server verification details:
   - challenge check:
   - origin check:
   - RP ID check:
   - UP/UV policy:
   - signature/attestation handling:
5. Credential persistence fields stored:

## 4. WebAuthn authentication (assertion) flow

1. Client requests authentication options.
2. Server sends challenge + allowCredentials.
3. Authenticator returns assertion.
4. Server verification details:
   - challenge check:
   - origin check:
   - RP ID hash / RP ID matching:
   - UP/UV policy:
   - signature verification:
   - signature counter check and update:
5. Session creation and protected route behavior:

## 5. Multi-device and multi-browser validation

### 5.1 Desktop browser tests (at least 3)

| Browser | Device/OS | Register | Login | Notes |
| ------- | --------- | -------- | ----- | ----- |
|         |           | ✅/❌    | ✅/❌ |       |
|         |           | ✅/❌    | ✅/❌ |       |
|         |           | ✅/❌    | ✅/❌ |       |

### 5.2 Mobile browser tests (at least 3)

| Browser | Device/OS | Register | Login | Notes |
| ------- | --------- | -------- | ----- | ----- |
|         |           | ✅/❌    | ✅/❌ |       |
|         |           | ✅/❌    | ✅/❌ |       |
|         |           | ✅/❌    | ✅/❌ |       |

### 5.3 Cross-device behavior

- Same username login behavior across devices:
- Synced passkey behavior observed:
- Additional-device credential enrollment behavior:

## 6. Negative tests (required)

### 6.1 Cross-device / credential mismatch

**Test:** Attempt login with username that has no credentials registered.

**Setup:**

1. Register **Username A** from Device X.
2. On Device Y, attempt login with **Username B** (never registered).

**Expected result:**

- Server returns error "No credentials found for this user" or empty allowCredentials list
- Browser cannot authenticate without matching credential

**Actual result:**

**How verified:**

- [ ] Browser console shows credential mismatch error
- [ ] Manual test result documented
- [ ] API test: `npm run test:single -- tests/app.test.ts` shows test case passing
- Screenshot reference: (if capturing browser UI)

---

### 6.2 Tampered/invalid authentication payload

**Test:** POST invalid attestation/assertion data to verify endpoints.

**Setup:**

1. Capture a valid registration or login response.
2. Tamper with one field (e.g., signature, clientDataJSON, authenticatorData).
3. POST to `/register/verify` or `/login/verify`.

**Expected result:**

- Server rejects with **400 Bad Request** or **401 Unauthorized**
- Error message: "Invalid signature" or "Verification failed"
- Session not created

**Actual result:**

**How verified:**

- [ ] API test with manual curl showing rejection:
  ```bash
  curl -X POST http://localhost:3000/register/verify \
    -H "Content-Type: application/json" \
    -d '{"response": {"clientDataJSON": "INVALID", ...}}'
  # Expected: 400 or 401 status
  ```
- [ ] Automated test case: `npm run test` verifies signature validation
- Screenshot reference: (if capturing browser dev tools or server logs)

---

### 6.3 Missing or invalid Origin header

**Test:** POST to verify endpoints without `Origin` header or with mismatched origin.

**Setup:**

1. Start server with `EXPECTED_ORIGIN=http://localhost:3000`.
2. Make request WITHOUT Origin header:
   ```bash
   curl -X POST http://localhost:3000/login/verify \
     -H "Content-Type: application/json" \
     -d '{...}'
   ```
3. Make request with WRONG origin:
   ```bash
   curl -X POST http://localhost:3000/login/verify \
     -H "Origin: https://attacker.com" \
     -H "Content-Type: application/json" \
     -d '{...}'
   ```

**Expected result:**

- Both requests return **403 Forbidden**
- Error message: "Origin not allowed" or similar
- No session created

**Actual result:**

**How verified:**

- [ ] Manual curl test confirms 403 status
- [ ] Automated test case in `npm run test` validates origin rejection
- Screenshot reference: (curl output or logs)

---

### 6.4 Signature counter replay (advanced)

**Test:** Resubmit an old assertion with stale counter value.

**Setup:**

1. Register a credential and perform one successful login (counter = 1).
2. Capture the assertion response.
3. Logout and attempt to reuse the SAME assertion response again.

**Expected result:**

- Second attempt returns **401 Unauthorized** or **400 Bad Request**
- Error message: "Counter value invalid" or "Possible cloned authenticator"
- Session NOT created for the second attempt

**Actual result:**

**How verified:**

- [ ] Manual replay test (capture response from first login, resubmit to `/login/verify`)
- [ ] Automated test: `npm run test:single -- tests/app.test.ts -t "counter"` validates counter increment and replay rejection
- Screenshot reference: (curl output or test output)

## 7. Issues encountered and resolutions

| Issue | Root cause | Resolution |
| ----- | ---------- | ---------- |
|       |            |            |
|       |            |            |

## 8. Bonus requirement statement

**How RP ID, origin, and user handle configuration supports credential use across browsers/devices of the same user:**

### RP ID as the credential scope

- **RP ID** is the cryptographic identifier used by the authenticator to derive key material.
- All credentials registered under the same RP ID are considered part of the same "relying party" and can be discovered/used by any browser/device accessing that RP ID.
- If Device A registers a passkey at `RP_ID=example.com`, Device B can use that same credential to log in IF:
  1. Device B accesses the same RP ID (`example.com`)
  2. Device B's browser/authenticator has synced the credential (if cloud-backed passkey)
  3. OR: Device B enrolls a new credential for the same user/username (different per-device credential, same account)

### Origin validation ensures integrity

- **EXPECTED_ORIGIN** is the server-side constraint that only allows requests from specific web origins.
- By keeping a **fixed, static origin** (e.g., named Cloudflare tunnel `https://myapp.company.com`), all devices accessing the app use the same origin.
- Server-side verification ensures:
  - Credential attestation/assertion is bound to that origin (via `clientDataJSON`)
  - Cross-origin forgery attempts are rejected (even if origin header is spoofed, RP ID mismatch in clientData is detected)
  - Device A and Device B, both accessing `https://myapp.company.com`, see the same credentials and can authenticate with them

### User handle (username) as the account identity

- **Username** is the human-readable identifier for the account.
- The same username can have multiple credentials:
  - One platform credential (Windows Hello / Face ID)
  - One cross-platform credential (security key USB dongle)
  - Multiple device-specific credentials if not synced
- When logging in from a different device, re-entering the username allows the browser to discover/enumerate credentials stored under that username and RP ID combo.

### Configuration for stability

```env
RP_ID=myapp.company.com                    # Fixed, never changes
EXPECTED_ORIGIN=https://myapp.company.com  # Fixed, never changes
SESSION_SECRET=<strong-random-secret>      # Consistent across sessions
```

With this setup:

- Device A registers `username=alice` with a Windows Hello credential at `RP_ID=myapp.company.com`.
- Device B, also accessing `https://myapp.company.com`, can:
  1. If passkey is synced (cloud-backed): enter `alice`, browser finds synced credential, logs in.
  2. If passkey is device-local: enter `alice`, browser has no matching credential, but user can register a new one for Device B; both Device A and B credentials are now linked to the same account/username.
- All credentials remain valid as long as RP ID and origin do not change.

If origin changes (e.g., quick tunnel to new hostname), old credentials become invalid for that new hostname due to browser-level RP ID mismatch.

## 9. Screenshot appendix

Attach screenshots for:

- successful registration/login cases
- unsuccessful/negative cases
- cross-browser and cross-device matrix evidence
