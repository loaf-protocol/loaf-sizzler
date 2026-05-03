import json
import sqlite3

from .base import BaseStorage


class SQLiteStorage(BaseStorage):
    def __init__(self, db_path: str = "loaf.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_tables()

    def _init_tables(self):
        """Create tables if they don't exist."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                job_id TEXT,
                data TEXT NOT NULL,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outputs (
                job_id TEXT PRIMARY KEY,
                output TEXT NOT NULL,
                output_hash TEXT NOT NULL,
                stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def add_message(self, message: dict) -> None:
        message_type = message.get("type")
        job_id = message.get("job_id")
        self.conn.execute(
            "INSERT INTO inbox (type, job_id, data) VALUES (?, ?, ?)",
            (message_type, job_id, json.dumps(message)),
        )
        self.conn.commit()

    def get_messages(self) -> list:
        cursor = self.conn.execute("SELECT data FROM inbox ORDER BY id ASC")
        return [json.loads(row[0]) for row in cursor.fetchall()]

    def clear_messages(self) -> None:
        self.conn.execute("DELETE FROM inbox")
        self.conn.commit()

    def get_messages_by_type(self, message_type: str) -> list:
        cursor = self.conn.execute(
            "SELECT data FROM inbox WHERE type = ? ORDER BY id ASC",
            (message_type,),
        )
        return [json.loads(row[0]) for row in cursor.fetchall()]

    def store_output(self, job_id: str, output: str, output_hash: str | None = None) -> None:
        self.conn.execute(
            """
            INSERT INTO outputs (job_id, output, output_hash)
            VALUES (?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                output = excluded.output,
                output_hash = excluded.output_hash,
                stored_at = CURRENT_TIMESTAMP
            """,
            (job_id, output, output_hash or ""),
        )
        self.conn.commit()

    def get_output(self, job_id: str) -> dict | None:
        cursor = self.conn.execute(
            "SELECT output, output_hash FROM outputs WHERE job_id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {"output": row[0], "output_hash": row[1]}

    def delete_output(self, job_id: str) -> None:
        self.conn.execute("DELETE FROM outputs WHERE job_id = ?", (job_id,))
        self.conn.commit()

    def has_output(self, job_id: str) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM outputs WHERE job_id = ? LIMIT 1",
            (job_id,),
        )
        return cursor.fetchone() is not None

    def set_agent_data(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO agent (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def get_agent_data(self, key: str) -> str | None:
        cursor = self.conn.execute(
            "SELECT value FROM agent WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        return row[0] if row else None