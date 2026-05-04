import { z } from "zod";

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  HOST: z.string().default("0.0.0.0"),
  PORT: z.coerce.number().int().positive().default(3000),
  RP_NAME: z.string().default("Passless"),
  RP_ID: z.string().default("localhost"),
  EXPECTED_ORIGIN: z.string().default("http://localhost:3000"),
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

export const config = {
  ...parsed.data,
  DB_PATH:
    parsed.data.DB_PATH ?? (parsed.data.NODE_ENV === "test" ? ":memory:" : "./data/passless.db")
};

export const cookieSettings = {
  httpOnly: true,
  secure: config.NODE_ENV === "production",
  sameSite: "lax" as const,
  maxAge: 1000 * 60 * 60 * 6
};
