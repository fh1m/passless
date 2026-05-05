import { z } from "zod";
import { loadRuntimeEnv } from "./load-env.js";

loadRuntimeEnv();

const DEFAULT_TRYCLOUDFLARE_ORIGIN_PATTERN = "^https://[a-z0-9-]+\\.trycloudflare\\.com$";
const DEFAULT_NGROK_ORIGIN_PATTERN =
  "^https://[a-z0-9-]+\\.(?:ngrok-free\\.app|ngrok\\.io|ngrok\\.app)$";

function normalizeOrigin(origin: string): string {
  const trimmed = origin.trim();
  if (!trimmed) {
    throw new Error("Origin cannot be empty");
  }
  const parsed = new URL(trimmed);
  return parsed.origin;
}

function parseOriginsCsv(value: string | undefined): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((origin) => normalizeOrigin(origin));
}

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  HOST: z.string().default("0.0.0.0"),
  PORT: z.coerce.number().int().positive().default(3000),
  RP_NAME: z.string().default("Passless"),
  RP_ID: z.string().default("localhost"),
  EXPECTED_ORIGIN: z.string().default("http://localhost:3000"),
  EXPECTED_ORIGINS: z.string().optional(),
  ALLOW_TRYCLOUDFLARE_ORIGIN: z
    .string()
    .optional()
    .transform((value) => value === "true"),
  TRYCLOUDFLARE_ORIGIN_PATTERN: z.string().default(DEFAULT_TRYCLOUDFLARE_ORIGIN_PATTERN),
  ALLOW_NGROK_ORIGIN: z
    .string()
    .optional()
    .transform((value) => value === "true"),
  NGROK_ORIGIN_PATTERN: z.string().default(DEFAULT_NGROK_ORIGIN_PATTERN),
  SESSION_SECRET: z.string().min(16).default("change-this-in-production-now"),
  DB_PATH: z.string().optional(),
  CHALLENGE_TTL_SECONDS: z.coerce.number().int().positive().default(300),
  HTTPS_ENABLED: z
    .string()
    .optional()
    .transform((value) => value === "true"),
  HTTPS_KEY_PATH: z.string().optional(),
  HTTPS_CERT_PATH: z.string().optional()
});

const parsed = envSchema.safeParse(process.env);
if (!parsed.success) {
  throw new Error(`Invalid environment configuration: ${parsed.error.message}`);
}

const expectedOrigins = Array.from(
  new Set([
    normalizeOrigin(parsed.data.EXPECTED_ORIGIN),
    ...parseOriginsCsv(parsed.data.EXPECTED_ORIGINS)
  ])
);

let tryCloudflareOriginRegex: RegExp | null = null;
if (parsed.data.ALLOW_TRYCLOUDFLARE_ORIGIN) {
  try {
    tryCloudflareOriginRegex = new RegExp(parsed.data.TRYCLOUDFLARE_ORIGIN_PATTERN);
  } catch (error) {
    throw new Error("Invalid TRYCLOUDFLARE_ORIGIN_PATTERN", { cause: error });
  }
}

let ngrokOriginRegex: RegExp | null = null;
if (parsed.data.ALLOW_NGROK_ORIGIN) {
  try {
    ngrokOriginRegex = new RegExp(parsed.data.NGROK_ORIGIN_PATTERN);
  } catch (error) {
    throw new Error("Invalid NGROK_ORIGIN_PATTERN", { cause: error });
  }
}

export const config = {
  ...parsed.data,
  EXPECTED_ORIGIN: expectedOrigins[0],
  EXPECTED_ORIGINS: expectedOrigins,
  TRYCLOUDFLARE_ORIGIN_REGEX: tryCloudflareOriginRegex,
  NGROK_ORIGIN_REGEX: ngrokOriginRegex,
  DB_PATH:
    parsed.data.DB_PATH ?? (parsed.data.NODE_ENV === "test" ? ":memory:" : "./data/passless.db")
};

export const cookieSettings = {
  httpOnly: true,
  secure: config.NODE_ENV === "production",
  sameSite: "lax" as const,
  maxAge: 1000 * 60 * 60 * 6
};
