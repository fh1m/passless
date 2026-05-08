"""Server-rendered HTML pages for registration, login, and authenticated dashboard.

Each page:
1. Renders minimal semantic HTML with inline CSS
2. Includes a <script type="module"> that uses @simplewebauthn/browser
3. Implements the browser-side WebAuthn ceremony
4. Handles UI state, errors, and user feedback

Security:
- HTML is escaped to prevent XSS
- No form data is submitted directly; WebAuthn is the only auth mechanism
- Sensitive data (challenges, credentials) never leaves the server
- Session cookies are HttpOnly and Secure in production

The JavaScript uses X-Client-Origin header so the backend can determine the
browser's origin even when accessed through proxies or tunnels.
"""

from __future__ import annotations


def escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{escape_html(title)}</title>
    <link rel="stylesheet" href="/static/style.css" />
  </head>
  <body>
    <main class="container">
      {body}
    </main>
  </body>
</html>"""


def register_page() -> str:
    return layout(
        "Register passkey",
        """<section class="panel">
          <h1>Create passkey account</h1>
          <p class="lede">Register your credential, then sign in with the same username across browsers/devices.</p>
          <form id="register-form">
            <label>
              Username
              <input required name="username" minlength="3" maxlength="64" />
            </label>
            <label>
              Display name (required for first-time registration)
              <input name="displayName" minlength="1" maxlength="120" />
            </label>
            <button type="submit">Create account + passkey</button>
          </form>
          <p id="status" class="status" aria-live="polite"></p>
          <p class="meta">Already registered? <a href="/login">Sign in</a></p>
        </section>
        <script type="module">
          import { startRegistration } from "https://cdn.jsdelivr.net/npm/@simplewebauthn/browser/+esm";
          const status = document.querySelector("#status");
          const form = document.querySelector("#register-form");
          form.addEventListener("submit", async (event) => {
            event.preventDefault();
            status.textContent = "Preparing registration...";
            const formData = new FormData(form);
            const payload = {
              username: String(formData.get("username") || "").trim().toLowerCase(),
              displayName: String(formData.get("displayName") || "").trim()
            };
            if (!payload.displayName) {
              delete payload.displayName;
            }
            try {
              const optionsRes = await fetch("/api/register/options", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-Client-Origin": window.location.origin
                },
                body: JSON.stringify(payload)
              });
              if (!optionsRes.ok) {
                const optionsError = await optionsRes
                  .json()
                  .catch(() => ({ error: "Unable to get registration options" }));
                throw new Error(optionsError.error || "Unable to get registration options");
              }
              const options = await optionsRes.json();
              const attResp = await startRegistration({ optionsJSON: options });
              const verifyRes = await fetch("/api/register/verify", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-Client-Origin": window.location.origin
                },
                body: JSON.stringify({ username: payload.username, response: attResp })
              });
              const verify = await verifyRes.json();
              if (!verifyRes.ok || !verify.verified) throw new Error(verify.error || "Verification failed");
              status.textContent = "Registration complete. Redirecting...";
              window.location.href = "/app";
            } catch (error) {
              status.textContent = error instanceof Error ? error.message : "Registration failed";
            }
          });
        </script>""",
    )


def login_page() -> str:
    return layout(
        "Passkey login",
        """<section class="panel">
          <h1>Passless Login</h1>
          <p class="lede">Use your previously registered passkey to sign in.</p>
          <form id="login-form">
            <label>
              Username
              <input required name="username" minlength="3" maxlength="64" />
            </label>
            <button type="submit">Sign in with passkey</button>
          </form>
          <p id="status" class="status" aria-live="polite"></p>
          <p class="meta">New here? <a href="/register">Create account</a></p>
        </section>
        <script type="module">
          import { startAuthentication } from "https://cdn.jsdelivr.net/npm/@simplewebauthn/browser/+esm";
          const status = document.querySelector("#status");
          const form = document.querySelector("#login-form");
          form.addEventListener("submit", async (event) => {
            event.preventDefault();
            status.textContent = "Preparing authentication...";
            const formData = new FormData(form);
            const payload = {
              username: String(formData.get("username") || "").trim().toLowerCase()
            };
            try {
              const optionsRes = await fetch("/api/auth/options", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-Client-Origin": window.location.origin
                },
                body: JSON.stringify(payload)
              });
              if (!optionsRes.ok) {
                const optionsError = await optionsRes
                  .json()
                  .catch(() => ({ error: "Unable to get authentication options" }));
                throw new Error(optionsError.error || "Unable to get authentication options");
              }
              const options = await optionsRes.json();
              const authResp = await startAuthentication({ optionsJSON: options });
              const verifyRes = await fetch("/api/auth/verify", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-Client-Origin": window.location.origin
                },
                body: JSON.stringify({ username: payload.username, response: authResp })
              });
              const verify = await verifyRes.json();
              if (!verifyRes.ok || !verify.verified) throw new Error(verify.error || "Login failed");
              status.textContent = "Authenticated. Redirecting...";
              window.location.href = "/app";
            } catch (error) {
              if (error instanceof DOMException && error.name === "NotAllowedError") {
                status.textContent = "No matching passkey was found on this device. Register this device using the same username.";
              } else {
                status.textContent = error instanceof Error ? error.message : "Authentication failed";
              }
            }
          });
        </script>""",
    )


def app_page(
    *,
    username: str,
    credential_count: int,
    authenticator_type: str,
    backed_up: bool,
    transports: str,
) -> str:
    return layout(
        "Protected area",
        f"""<section class="panel">
          <h1>Authenticated</h1>
          <p class="lede">Welcome, <strong>{escape_html(username)}</strong>.</p>
          <dl class="info-list">
            <div class="info-row">
              <dt>Registered passkeys</dt>
              <dd>{credential_count}</dd>
            </div>
            <div class="info-row">
              <dt>Authenticator type</dt>
              <dd>{escape_html(authenticator_type or "unknown")}</dd>
            </div>
            <div class="info-row">
              <dt>Backed up</dt>
              <dd>{"yes" if backed_up else "no"}</dd>
            </div>
            <div class="info-row">
              <dt>Transports</dt>
              <dd>{escape_html(transports)}</dd>
            </div>
          </dl>
          <form method="post" action="/logout">
            <button type="submit">Logout</button>
          </form>
        </section>""",
    )
