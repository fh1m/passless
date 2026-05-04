import Database from "better-sqlite3";
import path from "node:path";
import { randomUUID } from "node:crypto";
import fs from "node:fs";
import { config } from "./config.js";

export interface UserRecord {
  id: string;
  username: string;
  display_name: string;
  created_at: string;
}

export interface CredentialRecord {
  id: number;
  user_id: string;
  credential_id: string;
  public_key_b64: string;
  counter: number;
  transports_json: string;
  aaguid: string;
  device_type: string;
  backed_up: number;
  created_at: string;
}

if (config.DB_PATH !== ":memory:") {
  const dbDir = path.dirname(config.DB_PATH);
  fs.mkdirSync(dbDir, { recursive: true });
}

export const db = new Database(config.DB_PATH);
db.pragma("foreign_keys = ON");

db.exec(`
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS credentials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  credential_id TEXT UNIQUE NOT NULL,
  public_key_b64 TEXT NOT NULL,
  counter INTEGER NOT NULL DEFAULT 0,
  transports_json TEXT NOT NULL DEFAULT '[]',
  aaguid TEXT NOT NULL DEFAULT '',
  device_type TEXT NOT NULL DEFAULT '',
  backed_up INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS auth_challenges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL,
  flow_type TEXT NOT NULL CHECK(flow_type IN ('register', 'auth')),
  challenge TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_challenges_lookup ON auth_challenges (username, flow_type);
`);

const insertUserStmt = db.prepare(`
  INSERT INTO users (id, username, display_name)
  VALUES (@id, @username, @display_name)
`);

const getUserByUsernameStmt = db.prepare(`
  SELECT id, username, display_name, created_at
  FROM users
  WHERE username = ?
`);

const getUserByIdStmt = db.prepare(`
  SELECT id, username, display_name, created_at
  FROM users
  WHERE id = ?
`);

const insertCredentialStmt = db.prepare(`
  INSERT INTO credentials
  (user_id, credential_id, public_key_b64, counter, transports_json, aaguid, device_type, backed_up)
  VALUES (@user_id, @credential_id, @public_key_b64, @counter, @transports_json, @aaguid, @device_type, @backed_up)
`);

const getCredentialsByUsernameStmt = db.prepare(`
  SELECT c.*
  FROM credentials c
  INNER JOIN users u ON u.id = c.user_id
  WHERE u.username = ?
`);

const getCredentialByIdStmt = db.prepare(`
  SELECT *
  FROM credentials
  WHERE credential_id = ?
`);

const updateCounterStmt = db.prepare(`
  UPDATE credentials
  SET counter = ?
  WHERE credential_id = ?
`);

const insertChallengeStmt = db.prepare(`
  INSERT INTO auth_challenges (username, flow_type, challenge, expires_at)
  VALUES (?, ?, ?, ?)
`);

const deleteChallengesForFlowStmt = db.prepare(`
  DELETE FROM auth_challenges
  WHERE username = ? AND flow_type = ?
`);

const getLatestChallengeStmt = db.prepare(`
  SELECT challenge, expires_at
  FROM auth_challenges
  WHERE username = ? AND flow_type = ?
  ORDER BY id DESC
  LIMIT 1
`);

const deleteExpiredChallengesStmt = db.prepare(`
  DELETE FROM auth_challenges
  WHERE expires_at < ?
`);

export function ensureUser(username: string, displayName: string): UserRecord {
  const existing = getUserByUsernameStmt.get(username) as UserRecord | undefined;
  if (existing) {
    return existing;
  }

  const user: Pick<UserRecord, "id" | "username" | "display_name"> = {
    id: randomUUID(),
    username,
    display_name: displayName
  };
  insertUserStmt.run(user);
  const created = getUserByUsername(username);
  if (!created) {
    throw new Error("Failed to create user record");
  }
  return created;
}

export function getUserByUsername(username: string): UserRecord | undefined {
  return getUserByUsernameStmt.get(username) as UserRecord | undefined;
}

export function getUserById(userId: string): UserRecord | undefined {
  return getUserByIdStmt.get(userId) as UserRecord | undefined;
}

export function getCredentialsByUsername(username: string): CredentialRecord[] {
  return getCredentialsByUsernameStmt.all(username) as CredentialRecord[];
}

export function getCredentialByCredentialId(credentialId: string): CredentialRecord | undefined {
  return getCredentialByIdStmt.get(credentialId) as CredentialRecord | undefined;
}

export function insertCredential(record: Omit<CredentialRecord, "id" | "created_at">): void {
  insertCredentialStmt.run(record);
}

export function updateCredentialCounter(credentialId: string, newCounter: number): void {
  updateCounterStmt.run(newCounter, credentialId);
}

export function saveChallenge(
  username: string,
  flowType: "register" | "auth",
  challenge: string
): void {
  const expiresAt = Math.floor(Date.now() / 1000) + config.CHALLENGE_TTL_SECONDS;
  deleteChallengesForFlowStmt.run(username, flowType);
  insertChallengeStmt.run(username, flowType, challenge, expiresAt);
}

export function popValidChallenge(
  username: string,
  flowType: "register" | "auth"
): string | undefined {
  const now = Math.floor(Date.now() / 1000);
  deleteExpiredChallengesStmt.run(now);
  const row = getLatestChallengeStmt.get(username, flowType) as
    | { challenge: string; expires_at: number }
    | undefined;
  deleteChallengesForFlowStmt.run(username, flowType);
  if (!row || row.expires_at < now) {
    return undefined;
  }

  return row.challenge;
}
