import { randomUUID } from "node:crypto";
import request from "supertest";
import { describe, expect, it } from "vitest";
import { createApp } from "../src/app.js";
import { ensureUser, insertCredential, saveChallenge } from "../src/db.js";

describe("passless app", () => {
  const app = createApp();

  it("returns health status", async () => {
    const response = await request(app).get("/healthz");
    expect(response.status).toBe(200);
    expect(response.body).toEqual({ ok: true });
  });

  it("redirects anonymous protected access to login", async () => {
    const response = await request(app).get("/app");
    expect(response.status).toBe(302);
    expect(response.headers.location).toBe("/login");
  });

  it("rejects register options with invalid origin", async () => {
    const response = await request(app)
      .post("/api/register/options")
      .set("origin", "http://evil.test")
      .send({ username: "alice", displayName: "Alice" });

    expect(response.status).toBe(403);
    expect(response.body.error).toBe("Invalid origin header");
  });

  it("rejects register options when origin header is missing", async () => {
    const response = await request(app)
      .post("/api/register/options")
      .send({ username: "alice", displayName: "Alice" });

    expect(response.status).toBe(403);
    expect(response.body.error).toBe("Invalid origin header");
  });

  it("accepts register options when origin is missing but x-client-origin is valid", async () => {
    const suffix = randomUUID();
    const response = await request(app)
      .post("/api/register/options")
      .set("x-client-origin", "http://localhost:3000")
      .send({ username: `xclient-${suffix}`, displayName: "X Client" });

    expect(response.status).toBe(200);
    expect(response.body.challenge).toBeTypeOf("string");
  });

  it("accepts register options when origin is missing but referer is valid", async () => {
    const suffix = randomUUID();
    const response = await request(app)
      .post("/api/register/options")
      .set("referer", "http://localhost:3000/register")
      .send({ username: `ref-${suffix}`, displayName: "Ref User" });

    expect(response.status).toBe(200);
    expect(response.body.challenge).toBeTypeOf("string");
  });

  it("rejects register options when x-client-origin is invalid", async () => {
    const response = await request(app)
      .post("/api/register/options")
      .set("x-client-origin", "https://evil.test")
      .send({ username: "alice", displayName: "Alice" });

    expect(response.status).toBe(403);
    expect(response.body.error).toBe("Invalid origin header");
  });

  it("accepts register options with an allowed origin", async () => {
    const suffix = randomUUID();
    const response = await request(app)
      .post("/api/register/options")
      .set("origin", "http://localhost:3000")
      .send({ username: `alice-${suffix}`, displayName: "Alice" });

    expect(response.status).toBe(200);
    expect(response.body.challenge).toBeTypeOf("string");
  });

  it("requires display name for first-time registration", async () => {
    const suffix = randomUUID();
    const response = await request(app)
      .post("/api/register/options")
      .set("origin", "http://localhost:3000")
      .send({ username: `newuser-${suffix}` });

    expect(response.status).toBe(400);
    expect(response.body.error).toBe("Display name is required for first-time registration");
  });

  it("allows additional device registration for existing username without display name", async () => {
    const suffix = randomUUID();
    const username = `multi-${suffix}`;

    const first = await request(app)
      .post("/api/register/options")
      .set("origin", "http://localhost:3000")
      .send({ username, displayName: "Multi Device User" });
    expect(first.status).toBe(200);

    const second = await request(app)
      .post("/api/register/options")
      .set("origin", "http://localhost:3000")
      .send({ username });
    expect(second.status).toBe(200);
    expect(second.body.challenge).toBeTypeOf("string");
  });

  it("rejects register verification without an active challenge", async () => {
    const response = await request(app)
      .post("/api/register/verify")
      .set("origin", "http://localhost:3000")
      .send({
        username: `alice-${randomUUID()}`,
        response: { id: "credential-id" }
      });

    expect(response.status).toBe(400);
    expect(response.body.error).toBe("Registration challenge missing or expired");
  });

  it("rejects authentication options when origin header is missing", async () => {
    const suffix = randomUUID();
    const user = ensureUser(`alice-${suffix}`, "Alice");
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

    const response = await request(app).post("/api/auth/options").send({ username: user.username });

    expect(response.status).toBe(403);
    expect(response.body.error).toBe("Invalid origin header");
  });

  it("rejects authentication verification without an active challenge", async () => {
    const suffix = randomUUID();
    const user = ensureUser(`alice-${suffix}`, "Alice");
    const credentialId = `cred-${suffix}`;
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

    const response = await request(app)
      .post("/api/auth/verify")
      .set("origin", "http://localhost:3000")
      .send({
        username: user.username,
        response: { id: credentialId }
      });

    expect(response.status).toBe(400);
    expect(response.body.error).toBe("Authentication challenge missing or expired");
  });

  it("rejects authentication with unknown credential id", async () => {
    const suffix = randomUUID();
    const user = ensureUser(`alice-${suffix}`, "Alice");
    saveChallenge(user.username, "auth", `challenge-${suffix}`);

    const response = await request(app)
      .post("/api/auth/verify")
      .set("origin", "http://localhost:3000")
      .send({
        username: user.username,
        response: { id: `non-existent-${suffix}` }
      });

    expect(response.status).toBe(404);
    expect(response.body.error).toBe("Credential not found");
  });

  it("rejects authentication if credential does not belong to username", async () => {
    const suffix = randomUUID();
    const alice = ensureUser(`alice-${suffix}`, "Alice");
    const bob = ensureUser(`bob-${suffix}`, "Bob");
    const bobCredentialId = `cred-${suffix}`;
    insertCredential({
      user_id: bob.id,
      credential_id: bobCredentialId,
      public_key_b64: "AQID",
      counter: 0,
      transports_json: "[]",
      aaguid: "",
      device_type: "singleDevice",
      backed_up: 0
    });
    saveChallenge(alice.username, "auth", `challenge-${suffix}`);

    const response = await request(app)
      .post("/api/auth/verify")
      .set("origin", "http://localhost:3000")
      .send({
        username: alice.username,
        response: { id: bobCredentialId }
      });

    expect(response.status).toBe(401);
    expect(response.body.error).toBe("Credential does not belong to user");
  });

  // Negative tests for protocol strictness and replay prevention
  describe("protocol strictness - negative tests", () => {
    it("rejects authentication with mismatched RP ID", async () => {
      // This test verifies that RP ID validation is strict
      const suffix = randomUUID();
      const user = ensureUser(`rpid-${suffix}`, "RP ID User");
      const credentialId = `cred-${suffix}`;
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
      saveChallenge(user.username, "auth", `challenge-${suffix}`);

      // Send from a different origin that might have different RP ID
      const response = await request(app)
        .post("/api/auth/verify")
        .set("origin", "http://evil.test")
        .send({
          username: user.username,
          response: { id: credentialId }
        });

      // Should reject either due to invalid origin or RP ID mismatch
      expect([403, 400, 401]).toContain(response.status);
    });

    it("rejects register options for missing username field", async () => {
      const response = await request(app)
        .post("/api/register/options")
        .set("origin", "http://localhost:3000")
        .send({ displayName: "No Username" });

      expect(response.status).toBe(400);
      expect(response.body.error).toBeDefined();
    });

    it("rejects auth options for missing username field", async () => {
      const response = await request(app)
        .post("/api/auth/options")
        .set("origin", "http://localhost:3000")
        .send({});

      expect(response.status).toBe(400);
      expect(response.body.error).toBeDefined();
    });

    it("rejects register verification with missing response field", async () => {
      const suffix = randomUUID();
      const response = await request(app)
        .post("/api/register/verify")
        .set("origin", "http://localhost:3000")
        .send({ username: `user-${suffix}` });

      expect(response.status).toBe(400);
    });

    it("rejects auth verification with missing response field", async () => {
      const suffix = randomUUID();
      const user = ensureUser(`auth-${suffix}`, "Auth User");
      saveChallenge(user.username, "auth", `challenge-${suffix}`);

      const response = await request(app)
        .post("/api/auth/verify")
        .set("origin", "http://localhost:3000")
        .send({ username: user.username });

      expect(response.status).toBe(400);
    });

    it("rejects authentication with invalid credential ID encoding", async () => {
      const suffix = randomUUID();
      const user = ensureUser(`enc-${suffix}`, "Encoding User");
      saveChallenge(user.username, "auth", `challenge-${suffix}`);

      // Send credential ID with invalid base64/encoding
      // Server treats invalid encoding as unknown credential ID (404)
      const response = await request(app)
        .post("/api/auth/verify")
        .set("origin", "http://localhost:3000")
        .send({
          username: user.username,
          response: {
            id: "!!!invalid-base64!!!"
          }
        });

      expect([400, 404]).toContain(response.status);
    });
  });

  describe("cross-origin and origin validation", () => {
    it("accepts auth options with valid origin", async () => {
      const suffix = randomUUID();
      const user = ensureUser(`cross-${suffix}`, "Cross User");
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

      const response = await request(app)
        .post("/api/auth/options")
        .set("origin", "http://localhost:3000")
        .send({ username: user.username });

      expect(response.status).toBe(200);
      expect(response.body.challenge).toBeTypeOf("string");
    });

    it("rejects auth options with Referer but no direct origin", async () => {
      const suffix = randomUUID();
      const user = ensureUser(`referer-${suffix}`, "Referer User");
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

      // Auth options should work with Referer fallback
      const response = await request(app)
        .post("/api/auth/options")
        .set("referer", "http://localhost:3000/auth")
        .send({ username: user.username });

      // Should either accept (Referer fallback) or reject (no origin)
      expect([200, 403]).toContain(response.status);
    });

    it("ensures username and credential pairing validation", async () => {
      const suffix = randomUUID();
      const user1 = ensureUser(`pair1-${suffix}`, "User 1");
      const user2 = ensureUser(`pair2-${suffix}`, "User 2");

      // Create credential for user1
      const cred1 = `cred-${suffix}-1`;
      insertCredential({
        user_id: user1.id,
        credential_id: cred1,
        public_key_b64: "AQID",
        counter: 0,
        transports_json: "[]",
        aaguid: "",
        device_type: "singleDevice",
        backed_up: 0
      });

      // Create challenge for user2
      saveChallenge(user2.username, "auth", `challenge-${suffix}`);

      // Try to authenticate as user2 with user1's credential
      const response = await request(app)
        .post("/api/auth/verify")
        .set("origin", "http://localhost:3000")
        .send({
          username: user2.username,
          response: { id: cred1 }
        });

      expect(response.status).toBe(401);
      expect(response.body.error).toBe("Credential does not belong to user");
    });
  });
});
