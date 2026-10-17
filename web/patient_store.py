"""Patient working copies for the local, single-process web demo."""

import json
import math
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

from flask import current_app

from meddi.loader import load_patient as load_source_patient
from meddi.messages import message_event
from web.portal import PRAGUE, controls_for, remember_schedule, update_controls
from web.portal import at as checkin_at

_write_lock = Lock()


def patient_path(patient_id: str) -> Path:
    if not patient_id or Path(patient_id).name != patient_id or "\\" in patient_id:
        raise ValueError("Neplatné ID pacienta.")
    return Path(current_app.config["DATA_DIR"]) / "pacienti" / f"{patient_id}.json"


def load_patient(patient_id: str) -> dict:
    """Prefer the working copy; use the original until the first save."""
    path = patient_path(patient_id)
    patient = (
        json.loads(path.read_text(encoding="utf-8-sig"))
        if path.exists()
        else load_source_patient(patient_id)
    )
    if patient["patient_id"] != patient_id:
        raise ValueError("Data nepatří vybranému pacientovi.")
    return patient


def append_checkins(patient_id: str, checkins: list[dict]) -> Path:
    """Append without losing history or duplicating a retried submission."""
    destination = patient_path(patient_id)
    # Sessions and storage use one server process. Serialize read/append/replace
    # so two browser sessions cannot overwrite each other's new check-ins.
    with _write_lock:
        patient = deepcopy(load_patient(patient_id))
        times = [checkin_at(c) for c in checkins if c.get("datum")]
        controls = controls_for(patient, min(times)) if times else None
        known = {checkin["checkin_id"] for checkin in patient["checkiny"]}
        for checkin in checkins:
            if checkin.get("patient_id") != patient_id:
                raise ValueError("Odpovědi nepatří vybranému pacientovi.")
            if checkin["checkin_id"] not in known:
                patient["checkiny"].append(deepcopy(checkin))
                if controls is not None and checkin.get("datum"):
                    update_controls(patient, controls, checkin)
                known.add(checkin["checkin_id"])
        content = (
            json.dumps(patient, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=destination.parent) as temporary:
            path = Path(temporary) / "patient.json"
            path.write_text(content, encoding="utf-8")
            path.replace(destination)
    return destination


def record_team_action(
    patient_id, *, now, note, control_id=None, due_at=None, repeat_hours=None
):
    """A manual demo plan/contact over the existing patient working copy."""
    note = str(note or "").strip()
    if len(note) > 1000 or (control_id is None and not note):
        raise ValueError("Doplňte stručný záznam kontaktu (nejvýše 1000 znaků).")
    due = None
    repeat = None
    if control_id is not None:
        if not due_at:
            raise ValueError("Zadejte termín kontroly.")
        try:
            due = datetime.fromisoformat(due_at)
            due = (
                due.replace(tzinfo=PRAGUE)
                if due.tzinfo is None
                else due.astimezone(PRAGUE)
            )
            repeat = float(repeat_hours) if repeat_hours not in {None, ""} else None
        except (ValueError, TypeError, OverflowError):
            raise ValueError("Zadejte platný termín a interval v hodinách.") from None
        if repeat is not None and (not math.isfinite(repeat) or not 0 < repeat <= 8760):
            raise ValueError("Interval opakování musí být kladný, nejvýše 8760 hodin.")
    destination = patient_path(patient_id)
    with _write_lock:
        patient = deepcopy(load_patient(patient_id))
        controls = controls_for(patient)
        if control_id is not None:
            control = next((c for c in controls if c["id"] == control_id), None)
            if control is None:
                raise ValueError("Vybraná kontrola již není dostupná.")
            if not control.get("schedule_history"):
                remember_schedule(
                    control, datetime.fromisoformat(control["created_at"])
                )
            control.update(
                due_at=due.isoformat(),
                repeat_hours=repeat,
                requested_at=now.isoformat(),
                completed_checkin_id=None,
                plan_note=note or "Kontrola podle plánu týmu.",
            )
            remember_schedule(control, now)
            patient["portal_controls"] = controls
        patient.setdefault("demo_team_events", []).append(
            {
                "available_at": now.isoformat(),
                "kind": "plan" if control_id else "contact",
                "text": note or "Naplánována následná kontrola.",
                "control_id": control_id,
                "due_at": due.isoformat() if due else None,
                "repeat_hours": repeat,
            }
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=destination.parent) as temporary:
            path = Path(temporary) / "patient.json"
            path.write_text(
                json.dumps(patient, ensure_ascii=False, allow_nan=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            path.replace(destination)
    return destination


def save_message_analysis(patient_id, checkin_id, analysis):
    """Save extraction only if its exact source still matches the working copy."""
    with _write_lock:
        patient = deepcopy(load_patient(patient_id))
        checkin = next(
            (c for c in patient["checkiny"] if c["checkin_id"] == checkin_id), None
        )
        if checkin is None or analysis["message"] != asdict(
            message_event({"patient_id": patient_id, **checkin})
        ):
            raise ValueError("Zpráva se změnila; zopakujte vyhodnocení.")
        checkin["patient_message_analysis"] = deepcopy(analysis)
        destination = patient_path(patient_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=destination.parent) as temporary:
            path = Path(temporary) / "patient.json"
            path.write_text(
                json.dumps(patient, ensure_ascii=False, allow_nan=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            path.replace(destination)
    return destination


def save_patient_email(patient_id: str, email: str) -> None:
    destination = patient_path(patient_id)
    with _write_lock:
        patient = deepcopy(load_patient(patient_id))
        patient.setdefault("kontakt", {})["email"] = email
        content = (
            json.dumps(patient, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=destination.parent) as temporary:
            path = Path(temporary) / "patient.json"
            path.write_text(content, encoding="utf-8")
            path.replace(destination)
