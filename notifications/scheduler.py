import argparse
import json
import math
import os
import smtplib
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from meddi.loader import list_patient_ids, load_patient
from notifications import mailer
from web.event_store import EventStore

ROOT = Path(__file__).resolve().parents[1]


class NotificationStore(EventStore):
    def connect(self):
        return self._connect()

    @staticmethod
    def migrate(db):
        db.execute(
            "CREATE TABLE IF NOT EXISTS notification_schema (version INTEGER NOT NULL)"
        )
        version = db.execute("SELECT version FROM notification_schema").fetchone()
        if version and version[0] != 1:
            raise ValueError("Nepodporovaná verze notifikací.")
        if not version:
            db.execute("INSERT INTO notification_schema VALUES (1)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS notification_plans ("
            "patient_id TEXT PRIMARY KEY, interval_seconds REAL NOT NULL, "
            "reminder_seconds REAL NOT NULL, due_at REAL NOT NULL, "
            "invited INTEGER NOT NULL DEFAULT 0, reminded INTEGER NOT NULL DEFAULT 0, "
            "last_checkin TEXT)"
        )

    def schedule(self, patient_id, interval_hours, reminder_hours, now, last_checkin):
        if not all(
            math.isfinite(v) and v > 0 for v in (interval_hours, reminder_hours)
        ):
            raise ValueError("Intervaly musí být kladná konečná čísla.")
        with self.connect() as db:
            self.migrate(db)
            db.execute(
                "INSERT INTO notification_plans VALUES (?, ?, ?, ?, 0, 0, ?) "
                "ON CONFLICT(patient_id) DO UPDATE SET "
                "interval_seconds=excluded.interval_seconds, "
                "reminder_seconds=excluded.reminder_seconds, due_at=excluded.due_at, "
                "invited=0, reminded=0, last_checkin=excluded.last_checkin",
                (
                    patient_id,
                    interval_hours * 3600,
                    reminder_hours * 3600,
                    now + interval_hours * 3600,
                    last_checkin,
                ),
            )

    def plans(self):
        with self.connect() as db:
            self.migrate(db)
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM notification_plans ORDER BY due_at"
                )
            ]

    def cancel(self, patient_id):
        with self.connect() as db:
            self.migrate(db)
            db.execute(
                "DELETE FROM notification_plans WHERE patient_id=?", (patient_id,)
            )

    def run(self, now, patient_loader, send=mailer.send_notification):
        results = []
        with self.connect() as db:
            self.migrate(db)
            patients = [
                row[0]
                for row in db.execute("SELECT patient_id FROM notification_plans")
            ]
        for patient_id in patients:
            with self.connect() as db:
                self.migrate(db)
                row = db.execute(
                    "SELECT * FROM notification_plans WHERE patient_id=?", (patient_id,)
                ).fetchone()
                if row is None:
                    continue
                try:
                    patient = patient_loader(patient_id)
                    checkin = latest_checkin(patient)
                    if checkin != row["last_checkin"]:
                        db.execute(
                            "UPDATE notification_plans SET last_checkin=?, due_at=?, "
                            "invited=0, reminded=0 WHERE patient_id=?",
                            (checkin, now + row["interval_seconds"], patient_id),
                        )
                        results.append((patient_id, "completed"))
                        continue
                    if now < row["due_at"] or row["reminded"]:
                        continue
                    if row["invited"] and now < row["due_at"] + row["reminder_seconds"]:
                        continue
                    recipient = (patient.get("kontakt") or {}).get("email", "")
                    if not mailer.valid_email(recipient):
                        raise ValueError("Chybí kontakt.")
                    send(recipient)
                except (OSError, ValueError, smtplib.SMTPException):
                    results.append((patient_id, "failed"))
                    continue
                column = "reminded" if row["invited"] else "invited"
                db.execute(
                    f"UPDATE notification_plans SET {column}=1 WHERE patient_id=?",
                    (patient_id,),
                )
                if not row["invited"]:
                    db.execute(
                        "UPDATE notification_plans SET due_at=? WHERE patient_id=?",
                        (now, patient_id),
                    )
                results.append((patient_id, column))
        return results


def latest_checkin(patient):
    return json.dumps(sorted(c["checkin_id"] for c in patient.get("checkiny", [])))


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(
        description="Minimální plánovač pozvánek k dotazníku."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("MEDDI_DATA_DIR") or ROOT / "data"),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    schedule = commands.add_parser("schedule")
    schedule.add_argument("patient_id")
    schedule.add_argument("--interval-hours", type=float, required=True)
    schedule.add_argument("--reminder-hours", type=float, required=True)
    cancel = commands.add_parser("cancel")
    cancel.add_argument("patient_id")
    commands.add_parser("run")
    commands.add_parser("list")
    args = parser.parse_args()
    store = NotificationStore(args.data_dir / "events.sqlite3")

    def patient_loader(patient_id):
        if patient_id not in list_patient_ids():
            raise ValueError("Neznámý pacient.")
        path = args.data_dir / "pacienti" / f"{patient_id}.json"
        return (
            json.loads(path.read_text(encoding="utf-8-sig"))
            if path.exists()
            else load_patient(patient_id)
        )

    now = datetime.now(UTC).timestamp()
    if args.command == "schedule":
        try:
            patient = patient_loader(args.patient_id)
            if not mailer.valid_email((patient.get("kontakt") or {}).get("email", "")):
                parser.error("Nejprve uložte e-mail pacienta v lékařském rozhraní.")
            store.schedule(
                args.patient_id,
                args.interval_hours,
                args.reminder_hours,
                now,
                latest_checkin(patient),
            )
        except ValueError as error:
            parser.error(str(error))
        print("Plán uložen.")
    elif args.command == "list":
        for plan in store.plans():
            due = datetime.fromtimestamp(plan["due_at"], UTC).isoformat()
            print(
                f"{plan['patient_id']}: {due}; invited={plan['invited']}; reminded={plan['reminded']}"
            )
    elif args.command == "cancel":
        store.cancel(args.patient_id)
        print("Plán zrušen.")
    else:
        results = store.run(now, patient_loader)
        for patient_id, status in results:
            print(f"{patient_id}: {status}")
        return int(any(status == "failed" for _, status in results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
