"""Durable synthetic sources, immutable retries and SQLite transaction boundaries."""

import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace

import pytest

from llm_intake.master_contract import MessageEvent
from web.event_store import EventStore


def message(**changes):
    return replace(
        MessageEvent(
            "synthetic-message",
            "synthetic-patient",
            "  Mám potíže.\n",
            "2026-10-17T10:00:00+02:00",
            "master_question",
            "caregiver",
            "Jak se dnes cítí pacient?",
        ),
        **changes,
    )


def test_original_survives_a_new_python_process(tmp_path):
    path = tmp_path / "data" / "events.sqlite3"
    original = message()
    EventStore(path).accept("owner", "contact", original)
    script = (
        "import json, sys; from pathlib import Path; from dataclasses import asdict; "
        "from web.event_store import EventStore; "
        "print(json.dumps(asdict(EventStore(Path(sys.argv[1])).get("
        "'owner', 'synthetic-message').message)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == asdict(original)


def test_retry_keeps_original_timestamp_and_one_source(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    first = store.accept("owner", "contact", message())
    retried = store.accept(
        "owner", "contact", message(available_at="2026-10-17T11:00:00+02:00")
    )
    assert retried == first
    assert store.contact_messages("owner", "contact") == [first]


@pytest.mark.parametrize(
    "changes",
    [
        {"text": "Jiný text."},
        {"question": "Jiná otázka?"},
        {"author": "patient"},
        {"source": "targeted_answer"},
    ],
)
def test_same_submission_cannot_overwrite_original(tmp_path, changes):
    store = EventStore(tmp_path / "events.sqlite3")
    first = store.accept("owner", "contact", message())
    with pytest.raises(ValueError, match="jinou zprávu"):
        store.accept("owner", "contact", message(**changes))
    assert store.contact_messages("owner", "contact") == [first]


def test_contacts_and_corrections_cannot_cross_patients_or_owners(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    first = store.accept("owner", "contact", message())
    for owner, contact, candidate, correction in [
        ("other", "contact", message(id="new"), None),
        ("owner", "contact", message(id="new", patient_id="other-patient"), None),
        ("owner", "other-contact", message(id="new"), first.message.id),
        ("owner", "contact", message(id="new"), "missing-source"),
        ("owner", "other-contact", message(), None),
    ]:
        with pytest.raises(ValueError):
            store.accept(owner, contact, candidate, corrects_event_id=correction)
    assert store.get("other", first.message.id) is None
    assert store.contact_messages("other", "contact") == []
    assert store.contact_messages("owner", "contact") == [first]
    assert store.contact_messages("owner", "other-contact") == []


def test_correction_retains_both_originals_and_canonical_question(tmp_path):
    store = EventStore(tmp_path / "events.sqlite3")
    original = store.accept("owner", "contact", message())
    correction = store.accept(
        "owner",
        "contact",
        message(id="correction", text="Oprava.", source="targeted_answer"),
        question_id="synthetic/question",
        corrects_event_id=original.message.id,
    )
    assert store.contact_messages("owner", "contact") == [original, correction]
    assert correction.question_id == "synthetic/question"
    assert correction.corrects_event_id == original.message.id
    with pytest.raises(ValueError):
        store.accept("owner", "contact", correction.message, question_id="other")


def test_concurrent_retries_are_one_source_and_other_sources_are_not_lost(tmp_path):
    path = tmp_path / "events.sqlite3"

    def receive(index):
        # Exercise fresh connections, including simultaneous schema creation.
        return EventStore(path).accept(
            "owner", "contact", message(id=f"message-{index % 4}")
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(receive, range(16)))
    assert len(EventStore(path).contact_messages("owner", "contact")) == 4
    for result in results:
        assert result == EventStore(path).get("owner", result.message.id)


def test_failed_insert_rolls_back_and_can_be_retried(tmp_path):
    path = tmp_path / "events.sqlite3"
    store = EventStore(path)
    store.accept("owner", "contact", message())
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TRIGGER fail_receipt BEFORE INSERT ON message_events "
            "BEGIN SELECT RAISE(ABORT, 'synthetic disk failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.accept("owner", "new-contact", message(id="new"))
    assert store.get("owner", "new") is None
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM contacts WHERE id='new-contact'"
            ).fetchone()[0]
            == 0
        )
        connection.execute("DROP TRIGGER fail_receipt")
    assert store.accept("owner", "new-contact", message(id="new"))


def test_future_schema_is_rejected_without_changing_the_database(tmp_path):
    path = tmp_path / "events.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 2")
    original = path.read_bytes()
    with pytest.raises(ValueError, match="verze"):
        EventStore(path).accept("owner", "contact", message())
    assert path.read_bytes() == original
