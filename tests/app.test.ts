import { describe, expect, it } from "vitest";
import request from "supertest";
import { createApp } from "../src/app.js";
import { randomUUID } from "node:crypto";
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
});
