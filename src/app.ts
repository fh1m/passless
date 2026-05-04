import cookieParser from "cookie-parser";
import express from "express";
import session from "express-session";
import helmet from "helmet";
import {
  generateAuthenticationOptions,
  generateRegistrationOptions,
  verifyAuthenticationResponse,
  verifyRegistrationResponse
} from "@simplewebauthn/server";
import type { AuthenticatorTransportFuture, WebAuthnCredential } from "@simplewebauthn/server";
import { z } from "zod";
import { config, cookieSettings } from "./config.js";
import {
  ensureUser,
  getCredentialByCredentialId,
  getCredentialsByUsername,
  getUserById,
  getUserByUsername,
  insertCredential,
  popValidChallenge,
  saveChallenge,
  updateCredentialCounter
} from "./db.js";
import { escapeHtml, layout } from "./web.js";

const registerSchema = z.object({
  username: z.string().trim().min(3).max(64),
  displayName: z.string().trim().min(1).max(120)
});

const loginSchema = z.object({
  username: z.string().trim().min(3).max(64)
});

const registerVerifySchema = z.object({
  username: z.string().trim().min(3).max(64),
  response: z.unknown()
});

const authVerifySchema = z.object({
  username: z.string().trim().min(3).max(64),
  response: z.unknown()
});

function parseTransports(raw: string): AuthenticatorTransportFuture[] {
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item) => typeof item === "string") as AuthenticatorTransportFuture[];
  } catch {
    return [];
  }
}

function normalizeUsername(username: string): string {
  return username.trim().toLowerCase();
}

function normalizeRequestOrigin(origin: string): string | null {
  try {
    const trimmedOrigin = origin.trim();
    const parsedOrigin = new URL(trimmedOrigin).origin;
    return parsedOrigin === trimmedOrigin ? parsedOrigin : null;
  } catch {
    return null;
  }
}

function resolveAllowedOrigin(origin: string | undefined): string | null {
  if (!origin) {
    return null;
  }

  const normalizedOrigin = normalizeRequestOrigin(origin);
  if (!normalizedOrigin) {
    return null;
  }

  if (config.EXPECTED_ORIGINS.includes(normalizedOrigin)) {
    return normalizedOrigin;
  }

  if (
    config.ALLOW_TRYCLOUDFLARE_ORIGIN &&
    config.TRYCLOUDFLARE_ORIGIN_REGEX?.test(normalizedOrigin)
  ) {
    return normalizedOrigin;
  }

  return null;
}

function expectedOriginsForVerification(origin: string): string | string[] {
  const combinedOrigins = config.EXPECTED_ORIGINS.includes(origin)
    ? config.EXPECTED_ORIGINS
    : [...config.EXPECTED_ORIGINS, origin];
  return combinedOrigins.length === 1 ? combinedOrigins[0] : combinedOrigins;
}

export function createApp(): express.Express {
  const app = express();
  app.set("trust proxy", 1);

  app.use(
    helmet({
      contentSecurityPolicy: false
    })
  );
  app.use(express.json());
  app.use(express.urlencoded({ extended: false }));
  app.use(cookieParser());
  app.use(
    session({
      secret: config.SESSION_SECRET,
      resave: false,
      saveUninitialized: false,
      cookie: cookieSettings
    })
  );

  app.use("/static", express.static("src/static"));

  app.get("/", (req, res) => {
    if (req.session.userId) {
      res.redirect("/app");
      return;
    }
    res.redirect("/login");
  });

  app.get("/register", (_req, res) => {
    res.type("html").send(
      layout(
        "Register passkey",
        `<section class="panel">
          <h1>Create passkey account</h1>
          <p class="lede">Register your credential once, then sign in across browsers/devices.</p>
          <form id="register-form">
            <label>
              Username
              <input required name="username" minlength="3" maxlength="64" />
            </label>
            <label>
              Display name
              <input required name="displayName" minlength="1" maxlength="120" />
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
            try {
              const optionsRes = await fetch("/api/register/options", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
              });
              if (!optionsRes.ok) throw new Error("Unable to get registration options");
              const options = await optionsRes.json();
              const attResp = await startRegistration({ optionsJSON: options });
              const verifyRes = await fetch("/api/register/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
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
        </script>`
      )
    );
  });

  app.get("/login", (_req, res) => {
    res.type("html").send(
      layout(
        "Passkey login",
        `<section class="panel">
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
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
              });
              if (!optionsRes.ok) throw new Error("Unable to get authentication options");
              const options = await optionsRes.json();
              const authResp = await startAuthentication({ optionsJSON: options });
              const verifyRes = await fetch("/api/auth/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: payload.username, response: authResp })
              });
              const verify = await verifyRes.json();
              if (!verifyRes.ok || !verify.verified) throw new Error(verify.error || "Login failed");
              status.textContent = "Authenticated. Redirecting...";
              window.location.href = "/app";
            } catch (error) {
              status.textContent = error instanceof Error ? error.message : "Authentication failed";
            }
          });
        </script>`
      )
    );
  });

  app.get("/app", (req, res) => {
    if (!req.session.userId) {
      res.redirect("/login");
      return;
    }
    const user = getUserById(req.session.userId);
    if (!user) {
      req.session.destroy(() => undefined);
      res.redirect("/login");
      return;
    }
    const credentials = getCredentialsByUsername(user.username);
    const latestCredential = credentials[credentials.length - 1];
    const transports = latestCredential
      ? parseTransports(latestCredential.transports_json).join(", ")
      : "N/A";

    res.type("html").send(
      layout(
        "Protected area",
        `<section class="panel">
          <h1>Authenticated</h1>
          <p class="lede">Welcome, <strong>${escapeHtml(user.username)}</strong>.</p>
          <dl class="info-list">
            <div class="info-row">
              <dt>Authenticator type</dt>
              <dd>${escapeHtml(latestCredential?.device_type || "unknown")}</dd>
            </div>
            <div class="info-row">
              <dt>Backed up</dt>
              <dd>${latestCredential?.backed_up ? "yes" : "no"}</dd>
            </div>
            <div class="info-row">
              <dt>Transports</dt>
              <dd>${escapeHtml(transports)}</dd>
            </div>
          </dl>
          <form method="post" action="/logout">
            <button type="submit">Logout</button>
          </form>
        </section>`
      )
    );
  });

  app.post("/logout", (req, res) => {
    req.session.destroy(() => {
      res.clearCookie("connect.sid");
      res.redirect("/login");
    });
  });

  app.get("/healthz", (_req, res) => {
    res.json({ ok: true });
  });

  app.post("/api/register/options", async (req, res) => {
    if (!resolveAllowedOrigin(req.headers.origin)) {
      res.status(403).json({ error: "Invalid origin header" });
      return;
    }
    const parsed = registerSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: parsed.error.issues[0]?.message ?? "Invalid request" });
      return;
    }

    const username = normalizeUsername(parsed.data.username);
    const user = ensureUser(username, parsed.data.displayName);
    const existingCreds = getCredentialsByUsername(user.username).map((cred) => ({
      id: cred.credential_id,
      transports: parseTransports(cred.transports_json)
    }));

    const options = await generateRegistrationOptions({
      rpName: config.RP_NAME,
      rpID: config.RP_ID,
      userName: user.username,
      userDisplayName: user.display_name,
      userID: new TextEncoder().encode(user.id),
      timeout: 60000,
      excludeCredentials: existingCreds,
      authenticatorSelection: {
        residentKey: "preferred",
        userVerification: "required"
      },
      attestationType: "none"
    });
    saveChallenge(user.username, "register", options.challenge);
    res.json(options);
  });

  app.post("/api/register/verify", async (req, res) => {
    const allowedOrigin = resolveAllowedOrigin(req.headers.origin);
    if (!allowedOrigin) {
      res.status(403).json({ error: "Invalid origin header" });
      return;
    }
    const parsed = registerVerifySchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: parsed.error.issues[0]?.message ?? "Invalid request" });
      return;
    }

    const username = normalizeUsername(parsed.data.username);
    const expectedChallenge = popValidChallenge(username, "register");
    if (!expectedChallenge) {
      res.status(400).json({ error: "Registration challenge missing or expired" });
      return;
    }

    const user = getUserByUsername(username);
    if (!user) {
      res.status(404).json({ error: "User not found" });
      return;
    }

    const verification = await verifyRegistrationResponse({
      response: parsed.data.response as Parameters<
        typeof verifyRegistrationResponse
      >[0]["response"],
      expectedChallenge,
      expectedOrigin: expectedOriginsForVerification(allowedOrigin),
      expectedRPID: config.RP_ID,
      requireUserVerification: true
    });
    if (!verification.verified || !verification.registrationInfo) {
      res.status(401).json({ verified: false, error: "Registration verification failed" });
      return;
    }

    const { credential, credentialBackedUp, credentialDeviceType, aaguid } =
      verification.registrationInfo;
    insertCredential({
      user_id: user.id,
      credential_id: credential.id,
      public_key_b64: Buffer.from(credential.publicKey).toString("base64"),
      counter: credential.counter,
      transports_json: JSON.stringify(credential.transports ?? []),
      aaguid,
      device_type: credentialDeviceType,
      backed_up: credentialBackedUp ? 1 : 0
    });
    req.session.userId = user.id;
    req.session.username = user.username;
    res.json({ verified: true });
  });

  app.post("/api/auth/options", async (req, res) => {
    if (!resolveAllowedOrigin(req.headers.origin)) {
      res.status(403).json({ error: "Invalid origin header" });
      return;
    }
    const parsed = loginSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: parsed.error.issues[0]?.message ?? "Invalid request" });
      return;
    }

    const username = normalizeUsername(parsed.data.username);
    const user = getUserByUsername(username);
    if (!user) {
      res.status(404).json({ error: "User not found" });
      return;
    }

    const userCredentials = getCredentialsByUsername(username);
    if (!userCredentials.length) {
      res.status(400).json({ error: "No passkeys registered" });
      return;
    }

    const options = await generateAuthenticationOptions({
      rpID: config.RP_ID,
      timeout: 60000,
      userVerification: "required",
      allowCredentials: userCredentials.map((cred) => ({
        id: cred.credential_id,
        transports: parseTransports(cred.transports_json)
      }))
    });
    saveChallenge(username, "auth", options.challenge);
    res.json(options);
  });

  app.post("/api/auth/verify", async (req, res) => {
    const allowedOrigin = resolveAllowedOrigin(req.headers.origin);
    if (!allowedOrigin) {
      res.status(403).json({ error: "Invalid origin header" });
      return;
    }
    const parsed = authVerifySchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: parsed.error.issues[0]?.message ?? "Invalid request" });
      return;
    }

    const username = normalizeUsername(parsed.data.username);
    const expectedChallenge = popValidChallenge(username, "auth");
    if (!expectedChallenge) {
      res.status(400).json({ error: "Authentication challenge missing or expired" });
      return;
    }

    const user = getUserByUsername(username);
    if (!user) {
      res.status(404).json({ error: "User not found" });
      return;
    }

    const credentialResponse = parsed.data.response as Parameters<
      typeof verifyAuthenticationResponse
    >[0]["response"] &
      WebAuthnCredential;
    const credential = getCredentialByCredentialId(credentialResponse.id);
    if (!credential) {
      res.status(404).json({ error: "Credential not found" });
      return;
    }
    if (credential.user_id !== user.id) {
      res.status(401).json({ error: "Credential does not belong to user" });
      return;
    }

    const verification = await verifyAuthenticationResponse({
      response: credentialResponse,
      expectedChallenge,
      expectedOrigin: expectedOriginsForVerification(allowedOrigin),
      expectedRPID: config.RP_ID,
      requireUserVerification: true,
      credential: {
        id: credential.credential_id,
        publicKey: new Uint8Array(Buffer.from(credential.public_key_b64, "base64")),
        counter: credential.counter,
        transports: parseTransports(credential.transports_json)
      }
    });

    if (!verification.verified) {
      res.status(401).json({ verified: false, error: "Authentication verification failed" });
      return;
    }

    updateCredentialCounter(credential.credential_id, verification.authenticationInfo.newCounter);
    req.session.userId = user.id;
    req.session.username = user.username;
    res.json({ verified: true });
  });

  app.use(
    (error: unknown, _req: express.Request, res: express.Response, next: express.NextFunction) => {
      void next;
      const message = error instanceof Error ? error.message : "Unexpected error";
      res.status(500).json({ error: message });
    }
  );

  return app;
}
