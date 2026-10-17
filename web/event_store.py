"""Append-only source messages for the local prototype; independent of Flask."""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from llm_intake.master_contract import MessageEvent


@dataclass(frozen=True)
class StoredMessage:
    contact_id: str
    message: MessageEvent
    question_id: str | None
    corrects_event_id: str | None


class EventStore:
    """Commit the original before external work; never overwrite a source.

    The caller supplies a stable message ID per submission. An identical retry
    returns the first accepted timestamp; a changed payload needs a new ID.
    Existing patient JSONs remain the separate store for confirmed check-ins.
    """

    def __init__(self, path: Path):
        self.path = Path(path)

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in {0, 1}:
                raise ValueError("Nepodporovaná verze úložiště událostí.")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS contacts ("
                "id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, owner_id TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS message_events ("
                "id TEXT PRIMARY KEY, contact_id TEXT NOT NULL REFERENCES contacts(id), "
                "message_json TEXT NOT NULL, question_id TEXT, "
                "corrects_event_id TEXT REFERENCES message_events(id))"
            )
            connection.execute("PRAGMA user_version = 1")
            yield connection

    @contextmanager
    def _connection(self):
        # sqlite3's transaction context commits/rolls back but does not close.
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _stored(row):
        return StoredMessage(
            row["contact_id"],
            MessageEvent(**json.loads(row["message_json"])),
            row["question_id"],
            row["corrects_event_id"],
        )

    def get(self, owner_id: str, event_id: str) -> StoredMessage | None:
        """Return a message only to the browser owner of its contact."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT e.* FROM message_events e JOIN contacts c ON c.id=e.contact_id "
                "WHERE e.id=? AND c.owner_id=?",
                (event_id, owner_id),
            ).fetchone()
            return self._stored(row) if row else None

    def contact_messages(self, owner_id: str, contact_id: str) -> list[StoredMessage]:
        """Read the original receipt order, including failed/corrected inputs."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT e.* FROM message_events e JOIN contacts c ON c.id=e.contact_id "
                "WHERE e.contact_id=? AND c.owner_id=? ORDER BY e.rowid",
                (contact_id, owner_id),
            ).fetchall()
            return [self._stored(row) for row in rows]

    def accept(
        self,
        owner_id: str,
        contact_id: str,
        message: MessageEvent,
        *,
        question_id: str | None = None,
        corrects_event_id: str | None = None,
    ) -> StoredMessage:
        """Atomically accept a new source or return an unchanged prior source."""
        if not owner_id or not contact_id:
            raise ValueError("Událost potřebuje vlastníka a ID kontaktu.")
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO contacts VALUES (?, ?, ?) ON CONFLICT(id) DO NOTHING",
                (contact_id, message.patient_id, owner_id),
            )
            contact = connection.execute(
                "SELECT * FROM contacts WHERE id=?", (contact_id,)
            ).fetchone()
            if (contact["patient_id"], contact["owner_id"]) != (
                message.patient_id,
                owner_id,
            ):
                raise ValueError("Událost nepatří tomuto kontaktu.")
            row = connection.execute(
                "SELECT * FROM message_events WHERE id=?", (message.id,)
            ).fetchone()
            if row:
                stored = self._stored(row)
                # The timestamp belongs to the first receipt, not the retry.
                original = {
                    **asdict(stored.message),
                    "available_at": message.available_at,
                }
                if (
                    original != asdict(message)
                    or stored.contact_id != contact_id
                    or stored.question_id != question_id
                    or stored.corrects_event_id != corrects_event_id
                ):
                    raise ValueError("Toto odeslání již obsahuje jinou zprávu.")
                return stored
            if corrects_event_id is not None:
                corrected = connection.execute(
                    "SELECT contact_id FROM message_events WHERE id=?",
                    (corrects_event_id,),
                ).fetchone()
                if corrected is None or corrected["contact_id"] != contact_id:
                    raise ValueError("Opravovaná zpráva nepatří tomuto kontaktu.")
            connection.execute(
                "INSERT INTO message_events VALUES (?, ?, ?, ?, ?)",
                (
                    message.id,
                    contact_id,
                    json.dumps(asdict(message), ensure_ascii=False, allow_nan=False),
                    question_id,
                    corrects_event_id,
                ),
            )
            return StoredMessage(contact_id, message, question_id, corrects_event_id)
