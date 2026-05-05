import { randomUUID } from "node:crypto";
import request from "supertest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const webauthnMocks = vi.hoisted(() => ({
  generateRegistrationOptions: vi.fn(async () => ({ challenge: "register-challenge" })),
  generateAuthenticationOptions: vi.fn(async () => ({ challenge: "auth-challenge" })),
  verifyRegistrationResponse: vi.fn(async () => ({
    verified: true,
    registrationInfo: {
      credential: {
        id: "mock-credential-id",
        publicKey: new Uint8Array([1, 2, 3]),
        counter: 0,
        transports: []
      },
      credentialBackedUp: false,
      credentialDeviceType: "singleDevice",
      aaguid: ""
    }
  })),
  verifyAuthenticationResponse: vi.fn(async () => ({
    verified: true,
    authenticationInfo: {
      newCounter: 1
    }
  }))
}));

vi.mock("@simplewebauthn/server", () => webauthnMocks);

const baseEnv = { ...process.env };

async function loadApp(overrides: Record<string, string | undefined> = {}) {
  process.env = {
    ...baseEnv,
    NODE_ENV: "test",
    RP_ID: "localhost",
    EXPECTED_ORIGIN: "http://localhost:3000",
    ...overrides
  };
  vi.resetModules();
  const [{ createApp }, db] = await Promise.all([import("../src/app.js"), import("../src/db.js")]);
  return { app: createApp(), ...db };
}

beforeEach(() => {
  webauthnMocks.generateRegistrationOptions.mockClear();
  webauthnMocks.generateAuthenticationOptions.mockClear();
  webauthnMocks.verifyRegistrationResponse.mockClear();
  webauthnMocks.verifyAuthenticationResponse.mockClear();
});

afterEach(() => {
  process.env = { ...baseEnv };
  vi.resetModules();
});

describe("dynamic RP ID resolution", () => {
  it("uses localhost RP ID for localhost flow even if config RP_ID is stale", async () => {
    const { app } = await loadApp({ RP_ID: "trycloudflare.com" });
    const suffix = randomUUID();

    const response = await request(app)
      .post("/api/register/options")
      .set("origin", "http://localhost:3000")
      .send({ username: `local-${suffix}`, displayName: "Local User" });

    expect(response.status).toBe(200);
    expect(webauthnMocks.generateRegistrationOptions).toHaveBeenCalledWith(
      expect.objectContaining({ rpID: "localhost" })
    );
  });

  it("uses tunnel hostname as RP ID for register/auth options", async () => {
    const { app, ensureUser, insertCredential } = await loadApp({
      ALLOW_TRYCLOUDFLARE_ORIGIN: "true"
    });
    const suffix = randomUUID();
    const tunnelOrigin = `https://${suffix}.trycloudflare.com`;
    const username = `tunnel-${suffix}`;

    const registerOptionsResponse = await request(app)
      .post("/api/register/options")
      .set("origin", tunnelOrigin)
      .send({ username, displayName: "Tunnel User" });

    expect(registerOptionsResponse.status).toBe(200);
    expect(webauthnMocks.generateRegistrationOptions).toHaveBeenCalledWith(
      expect.objectContaining({ rpID: `${suffix}.trycloudflare.com` })
    );

    const user = ensureUser(username, "Tunnel User");
    insertCredential({
      user_id: user.id,
      credential_id: `cred-${suffix}`,
      public_key_b64: "AQID",
      counter: 0,
      transports_json: "[]",
      aaguid: "",
      device_type: "singleDevice",
      backed_up: 0
    });
    const authOptionsResponse = await request(app)
      .post("/api/auth/options")
      .set("origin", tunnelOrigin)
      .send({ username });

    expect(authOptionsResponse.status).toBe(200);
    expect(webauthnMocks.generateAuthenticationOptions).toHaveBeenCalledWith(
      expect.objectContaining({ rpID: `${suffix}.trycloudflare.com` })
    );
  });

  it("uses tunnel hostname as expectedRPID for registration and auth verification", async () => {
    const { app, ensureUser, saveChallenge, insertCredential } = await loadApp({
      ALLOW_TRYCLOUDFLARE_ORIGIN: "true"
    });
    const suffix = randomUUID();
    const tunnelOrigin = `https://${suffix}.trycloudflare.com`;
    const expectedRpId = `${suffix}.trycloudflare.com`;
    const username = `verify-${suffix}`;

    const user = ensureUser(username, "Verify User");
    saveChallenge(username, "register", `register-${suffix}`);

    const registerVerifyResponse = await request(app)
      .post("/api/register/verify")
      .set("origin", tunnelOrigin)
      .send({ username, response: { id: `reg-${suffix}` } });

    expect(registerVerifyResponse.status).toBe(200);
    expect(webauthnMocks.verifyRegistrationResponse).toHaveBeenCalledWith(
      expect.objectContaining({ expectedRPID: expectedRpId })
    );

    const credentialId = `auth-cred-${suffix}`;
    insertCredential({
      user_id: user.id,
      credential_id: credentialId,
      public_key_b64: "AQID",
      counter: 0,
      transports_json: "[]",
      aaguid: "",
      device_type: "singleDevice",
      backed_up: 0
    });
    saveChallenge(username, "auth", `auth-${suffix}`);

    const authVerifyResponse = await request(app)
      .post("/api/auth/verify")
      .set("origin", tunnelOrigin)
      .send({ username, response: { id: credentialId } });

    expect(authVerifyResponse.status).toBe(200);
    expect(webauthnMocks.verifyAuthenticationResponse).toHaveBeenCalledWith(
      expect.objectContaining({ expectedRPID: expectedRpId })
    );
  });
});
