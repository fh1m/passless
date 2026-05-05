import { afterEach, describe, expect, it, vi } from "vitest";

const baseEnv = { ...process.env };

async function loadConfig(overrides: Record<string, string | undefined>) {
  process.env = { ...baseEnv, ...overrides };
  vi.resetModules();
  return (await import("../src/config.js")).config;
}

afterEach(() => {
  process.env = { ...baseEnv };
  vi.resetModules();
});

describe("config origin parsing", () => {
  it("supports multiple expected origins", async () => {
    const config = await loadConfig({
      EXPECTED_ORIGIN: "http://localhost:3000",
      EXPECTED_ORIGINS: "https://alpha.example.com, https://beta.example.com/"
    });

    expect(config.EXPECTED_ORIGINS).toEqual([
      "http://localhost:3000",
      "https://alpha.example.com",
      "https://beta.example.com"
    ]);
  });

  it("builds trycloudflare regex when enabled", async () => {
    const config = await loadConfig({
      ALLOW_TRYCLOUDFLARE_ORIGIN: "true"
    });

    expect(config.TRYCLOUDFLARE_ORIGIN_REGEX).not.toBeNull();
    expect(config.TRYCLOUDFLARE_ORIGIN_REGEX?.test("https://a1b2c3.trycloudflare.com")).toBe(true);
    expect(config.TRYCLOUDFLARE_ORIGIN_REGEX?.test("https://evil.example.com")).toBe(false);
  });

  it("builds ngrok regex when enabled", async () => {
    const config = await loadConfig({
      ALLOW_NGROK_ORIGIN: "true"
    });

    expect(config.NGROK_ORIGIN_REGEX).not.toBeNull();
    expect(config.NGROK_ORIGIN_REGEX?.test("https://abc123.ngrok-free.app")).toBe(true);
    expect(config.NGROK_ORIGIN_REGEX?.test("https://demo.ngrok.io")).toBe(true);
    expect(config.NGROK_ORIGIN_REGEX?.test("https://evil.example.com")).toBe(false);
  });

  it("throws on invalid trycloudflare pattern", async () => {
    await expect(() =>
      loadConfig({
        ALLOW_TRYCLOUDFLARE_ORIGIN: "true",
        TRYCLOUDFLARE_ORIGIN_PATTERN: "["
      })
    ).rejects.toThrow("Invalid TRYCLOUDFLARE_ORIGIN_PATTERN");
  });

  it("throws on invalid ngrok pattern", async () => {
    await expect(() =>
      loadConfig({
        ALLOW_NGROK_ORIGIN: "true",
        NGROK_ORIGIN_PATTERN: "["
      })
    ).rejects.toThrow("Invalid NGROK_ORIGIN_PATTERN");
  });
});
