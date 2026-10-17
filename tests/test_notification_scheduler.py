import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from notifications.scheduler import NotificationStore, latest_checkin


@pytest.fixture
def plan(tmp_path):
    patient = {"kontakt": {"email": "synthetic@example.com"}, "checkiny": []}
    store = NotificationStore(tmp_path / "events.sqlite3")
    store.schedule("synthetic", 1, 2, 0, latest_checkin(patient))
    return store, patient, Mock()


def test_one_invitation_one_reminder_and_no_more_after_restart(plan):
    store, patient, send = plan
    load = lambda _: patient
    assert store.run(3599, load, send) == []
    assert store.run(3600, load, send) == [("synthetic", "invited")]
    assert store.run(10799, load, send) == []
    restarted = NotificationStore(store.path)
    assert restarted.run(10800, load, send) == [("synthetic", "reminded")]
    assert restarted.run(999999, load, send) == []
    assert send.call_count == 2
    send.assert_called_with("synthetic@example.com")


def test_completion_cancels_old_reminder_and_schedules_next_cycle(plan):
    store, patient, send = plan
    store.run(3600, lambda _: patient, send)
    patient["checkiny"].append({"checkin_id": "confirmed"})
    assert store.run(10800, lambda _: patient, send) == [("synthetic", "completed")]
    assert store.run(14399, lambda _: patient, send) == []
    assert send.call_count == 1
    assert store.run(14400, lambda _: patient, send) == [("synthetic", "invited")]


def test_completion_before_invitation_suppresses_overdue_mail(plan):
    store, patient, send = plan
    patient["checkiny"].append({"checkin_id": "confirmed"})
    store.run(10000, lambda _: patient, send)
    send.assert_not_called()


def test_late_invitation_gets_full_reminder_interval(plan):
    store, patient, send = plan
    store.run(20000, lambda _: patient, send)
    assert store.run(20001, lambda _: patient, send) == []
    assert store.run(27200, lambda _: patient, send) == [("synthetic", "reminded")]


def test_failure_retries_and_missing_contact_never_sends(plan):
    store, patient, send = plan
    patient["kontakt"]["email"] = "invalid"
    assert store.run(3600, lambda _: patient, send) == [("synthetic", "failed")]
    send.assert_not_called()
    patient["kontakt"]["email"] = "new@example.com"
    send.side_effect = OSError("Synthetic SMTP failure")
    assert store.run(3600, lambda _: patient, send) == [("synthetic", "failed")]
    send.side_effect = None
    assert store.run(3601, lambda _: patient, send) == [("synthetic", "invited")]
    send.assert_called_with("new@example.com")


def test_cancel_and_concurrent_workers(plan):
    store, patient, send = plan
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: store.run(3600, lambda _: patient, send), range(2)))
    send.assert_called_once()
    store.cancel("synthetic")
    assert store.run(99999, lambda _: patient, send) == []


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf")])
def test_invalid_intervals_rejected(plan, interval):
    store, _, _ = plan
    with pytest.raises(ValueError):
        store.schedule("synthetic", interval, 1, 0, "[]")


def test_migration_preserves_event_tables_and_schema_version(plan):
    store, _, _ = plan
    with sqlite3.connect(store.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT version FROM notification_schema").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM message_events").fetchone()[0] == 0
