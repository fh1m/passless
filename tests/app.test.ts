import { describe, expect, it } from "vitest";
import request from "supertest";
import { createApp } from "../src/app.js";

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
});
