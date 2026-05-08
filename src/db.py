"""SQLite persistence for users, credentials, and authentication challenges.

Schema:
- users: user_id (UUID), username (unique), display_name, created_at
- credentials: credential_id (unique), user_id (FK), public_key (base64url),
              counter (replay protection), transports, device type, backed_up flag
- auth_challenges: username, flow_type (register/auth), challenge (base64url),
                  expires_at (TTL enforcement)

Thread safety:
- All database operations use a threading.Lock to ensure serial access
- SQLite is opened with check_same_thread=False but internally serialized

Design patterns:
- User handles are UUIDs, not usernames, enabling username changes without
  invalidating credentials
- Challenges are single-use, deleted after verification
- Signature counter is updated on each successful authentication
- Multiple credentials per user support username-based multi-device enrollment
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import base64
import sqlite3
import threading
import time
import uuid

from .config import config


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


@dataclass(frozen=True)
class UserRecord:
    id: str
    username: str
    display_name: str
    created_at: str


@dataclass(frozen=True)
class CredentialRecord:
    id: int
    user_id: str
    credential_id: str
    public_key_b64: str
    counter: int
    transports_json: str
    aaguid: str
    device_type: str
    backed_up: int
    created_at: str


class PasslessDatabase:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or config.db_path
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
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

                CREATE INDEX IF NOT EXISTS idx_challenges_lookup
                ON auth_challenges (username, flow_type);
                """
            )

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _user_from_row(row: sqlite3.Row | None) -> UserRecord | None:
        if row is None:
            return None
        return UserRecord(
            id=row["id"],
            username=row["username"],
            display_name=row["display_name"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _credential_from_row(row: sqlite3.Row | None) -> CredentialRecord | None:
        if row is None:
            return None
        return CredentialRecord(
            id=row["id"],
            user_id=row["user_id"],
            credential_id=row["credential_id"],
            public_key_b64=row["public_key_b64"],
            counter=row["counter"],
            transports_json=row["transports_json"],
            aaguid=row["aaguid"],
            device_type=row["device_type"],
            backed_up=row["backed_up"],
            created_at=row["created_at"],
        )

    def ensure_user(self, username: str, display_name: str) -> UserRecord:
        existing = self.get_user_by_username(username)
        if existing:
            return existing

        user_id = str(uuid.uuid4())
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO users (id, username, display_name) VALUES (?, ?, ?)",
                (user_id, username, display_name),
            )
        created = self.get_user_by_username(username)
        if created is None:
            raise RuntimeError("Failed to create user record")
        return created

    def get_user_by_username(self, username: str) -> UserRecord | None:
        row = self._conn.execute(
            "SELECT id, username, display_name, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return self._user_from_row(row)

    def get_user_by_id(self, user_id: str) -> UserRecord | None:
        row = self._conn.execute(
            "SELECT id, username, display_name, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return self._user_from_row(row)

    def get_credentials_by_username(self, username: str) -> list[CredentialRecord]:
        rows = self._conn.execute(
            """
            SELECT c.*
            FROM credentials c
            INNER JOIN users u ON u.id = c.user_id
            WHERE u.username = ?
            ORDER BY c.id ASC
            """,
            (username,),
        ).fetchall()
        return [cred for row in rows if (cred := self._credential_from_row(row)) is not None]

    def get_credential_by_credential_id(self, credential_id: str) -> CredentialRecord | None:
        row = self._conn.execute(
            "SELECT * FROM credentials WHERE credential_id = ?",
            (credential_id,),
        ).fetchone()
        return self._credential_from_row(row)

    def insert_credential(self, record: dict[str, object]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO credentials
                (user_id, credential_id, public_key_b64, counter, transports_json, aaguid, device_type, backed_up)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["user_id"],
                    record["credential_id"],
                    record["public_key_b64"],
                    record["counter"],
                    record["transports_json"],
                    record["aaguid"],
                    record["device_type"],
                    record["backed_up"],
                ),
            )

    def update_credential_counter(self, credential_id: str, new_counter: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE credentials SET counter = ? WHERE credential_id = ?",
                (new_counter, credential_id),
            )

    def save_challenge(self, username: str, flow_type: str, challenge: bytes | str) -> None:
        challenge_text = challenge if isinstance(challenge, str) else _b64url_encode(challenge)
        expires_at = int(time.time()) + config.challenge_ttl_seconds
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM auth_challenges WHERE username = ? AND flow_type = ?",
                (username, flow_type),
            )
            self._conn.execute(
                "INSERT INTO auth_challenges (username, flow_type, challenge, expires_at) VALUES (?, ?, ?, ?)",
                (username, flow_type, challenge_text, expires_at),
            )

    def pop_valid_challenge(self, username: str, flow_type: str) -> bytes | None:
        now = int(time.time())
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM auth_challenges WHERE expires_at < ?", (now,))
            row = self._conn.execute(
                """
                SELECT challenge, expires_at
                FROM auth_challenges
                WHERE username = ? AND flow_type = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (username, flow_type),
            ).fetchone()
            self._conn.execute(
                "DELETE FROM auth_challenges WHERE username = ? AND flow_type = ?",
                (username, flow_type),
            )
        if row is None or row["expires_at"] < now:
            return None
        challenge = row["challenge"]
        if isinstance(challenge, bytes):
            return challenge
        return _b64url_decode(challenge)


def ensure_user(username: str, display_name: str) -> UserRecord:
    return database.ensure_user(username, display_name)


def get_user_by_username(username: str) -> UserRecord | None:
    return database.get_user_by_username(username)


def get_user_by_id(user_id: str) -> UserRecord | None:
    return database.get_user_by_id(user_id)


def get_credentials_by_username(username: str) -> list[CredentialRecord]:
    return database.get_credentials_by_username(username)


def get_credential_by_credential_id(credential_id: str) -> CredentialRecord | None:
    return database.get_credential_by_credential_id(credential_id)


def insert_credential(record: dict[str, object]) -> None:
    database.insert_credential(record)


def update_credential_counter(credential_id: str, new_counter: int) -> None:
    database.update_credential_counter(credential_id, new_counter)


def save_challenge(username: str, flow_type: str, challenge: bytes | str) -> None:
    database.save_challenge(username, flow_type, challenge)


def pop_valid_challenge(username: str, flow_type: str) -> bytes | None:
    return database.pop_valid_challenge(username, flow_type)


database = PasslessDatabase()
