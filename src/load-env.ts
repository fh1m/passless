import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

interface LoadRuntimeEnvOptions {
  envDir?: string;
  nodeEnv?: string;
  processEnv?: NodeJS.ProcessEnv;
  loadInTest?: boolean;
}

function resolveEnvDir(explicitEnvDir: string | undefined): string {
  if (explicitEnvDir) {
    return path.resolve(explicitEnvDir);
  }

  const cwd = process.cwd();
  const moduleRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const cwdEnvPath = path.join(cwd, ".env");
  return fs.existsSync(cwdEnvPath) ? cwd : moduleRoot;
}

function candidateEnvFiles(nodeEnv: string): string[] {
  return [
    `.env.${nodeEnv}.local`,
    ...(nodeEnv === "test" ? [] : [".env.local"]),
    `.env.${nodeEnv}`,
    ".env"
  ];
}

export function loadRuntimeEnv(options: LoadRuntimeEnvOptions = {}): string[] {
  const nodeEnv = options.nodeEnv ?? process.env.NODE_ENV ?? "development";
  if (nodeEnv === "test" && options.loadInTest !== true) {
    return [];
  }

  const processEnv = options.processEnv ?? process.env;
  const envDir = resolveEnvDir(options.envDir);
  const loadedFiles: string[] = [];

  for (const fileName of candidateEnvFiles(nodeEnv)) {
    const envPath = path.join(envDir, fileName);
    if (!fs.existsSync(envPath)) {
      continue;
    }

    const parsed = dotenv.parse(fs.readFileSync(envPath, "utf-8"));
    for (const [key, value] of Object.entries(parsed)) {
      if (processEnv[key] === undefined) {
        processEnv[key] = value;
      }
    }
    loadedFiles.push(envPath);
  }

  return loadedFiles;
}
