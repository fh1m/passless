import fs from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { loadRuntimeEnv } from "../src/load-env.js";

const fixtureDir = path.resolve("data/test-runtime-env");

function writeEnvFile(fileName: string, contents: string): void {
  fs.mkdirSync(fixtureDir, { recursive: true });
  fs.writeFileSync(path.join(fixtureDir, fileName), contents, "utf-8");
}

afterEach(() => {
  fs.rmSync(fixtureDir, { recursive: true, force: true });
});

describe("loadRuntimeEnv", () => {
  it("loads env files with non-overriding precedence", () => {
    writeEnvFile(".env", "SOURCE=base\nCOMMON=base\n");
    writeEnvFile(".env.production", "COMMON=production\nPRODUCTION_ONLY=yes\n");
    writeEnvFile(".env.local", "LOCAL_ONLY=present\n");
    writeEnvFile(".env.production.local", "COMMON=production-local\n");

    const runtimeEnv: NodeJS.ProcessEnv = {
      COMMON: "already-set"
    };

    const loaded = loadRuntimeEnv({
      envDir: fixtureDir,
      nodeEnv: "production",
      processEnv: runtimeEnv
    });

    expect(loaded.map((envPath) => path.basename(envPath))).toEqual([
      ".env.production.local",
      ".env.local",
      ".env.production",
      ".env"
    ]);
    expect(runtimeEnv.COMMON).toBe("already-set");
    expect(runtimeEnv.SOURCE).toBe("base");
    expect(runtimeEnv.LOCAL_ONLY).toBe("present");
    expect(runtimeEnv.PRODUCTION_ONLY).toBe("yes");
  });

  it("skips loading .env files by default in test mode", () => {
    writeEnvFile(".env", "SOURCE=base\n");
    const runtimeEnv: NodeJS.ProcessEnv = {};

    const loaded = loadRuntimeEnv({
      envDir: fixtureDir,
      nodeEnv: "test",
      processEnv: runtimeEnv
    });

    expect(loaded).toEqual([]);
    expect(runtimeEnv.SOURCE).toBeUndefined();
  });
});
