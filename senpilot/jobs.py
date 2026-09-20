"""SQLite job ledger with a conservative outbound-send boundary."""

from __future__ import annotations

from pathlib import Path
import sqlite3


class JobStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    inbound_message_id TEXT PRIMARY KEY,
                    sender_email TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN
                        ('received', 'ready', 'sending', 'completed', 'failed')),
                    outbound_message_id TEXT UNIQUE,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    error_code TEXT
                )
            """)

    def _connect(self):
        return sqlite3.connect(self.path)

    def receive(self, inbound_message_id: str, sender_email: str) -> bool:
        """Return False for a duplicate provider message ID."""
        if not inbound_message_id or not sender_email:
            raise ValueError("missing_message_identity")
        with self._connect() as db:
            result = db.execute(
                "INSERT OR IGNORE INTO jobs (inbound_message_id, sender_email, state) VALUES (?, ?, 'received')",
                (inbound_message_id, sender_email),
            )
            return result.rowcount == 1

    def mark_ready(self, inbound_message_id: str) -> None:
        with self._connect() as db:
            result = db.execute(
                "UPDATE jobs SET state='ready' WHERE inbound_message_id=? AND state='received'",
                (inbound_message_id,),
            )
            if result.rowcount != 1:
                raise ValueError("invalid_state_transition")

    def reserve_send(self, inbound_message_id: str) -> bool:
        """Reserve one send; an uncertain 'sending' state needs reconciliation."""
        with self._connect() as db:
            result = db.execute(
                "UPDATE jobs SET state='sending', attempt=attempt+1 "
                "WHERE inbound_message_id=? AND state='ready'",
                (inbound_message_id,),
            )
            return result.rowcount == 1

    def mark_sent(self, inbound_message_id: str, outbound_message_id: str) -> None:
        if not outbound_message_id:
            raise ValueError("missing_outbound_message_id")
        with self._connect() as db:
            result = db.execute(
                "UPDATE jobs SET state='completed', outbound_message_id=? "
                "WHERE inbound_message_id=? AND state='sending'",
                (outbound_message_id, inbound_message_id),
            )
            if result.rowcount != 1:
                raise ValueError("invalid_state_transition")

    def get(self, inbound_message_id: str) -> dict | None:
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM jobs WHERE inbound_message_id=?", (inbound_message_id,)
            ).fetchone()
            return dict(row) if row else None
