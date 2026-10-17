"""Patient working copies for the local, single-process web demo."""

import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock

from flask import current_app

from meddi.loader import load_patient as load_source_patient

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
        known = {checkin["checkin_id"] for checkin in patient["checkiny"]}
        for checkin in checkins:
            if checkin.get("patient_id") != patient_id:
                raise ValueError("Odpovědi nepatří vybranému pacientovi.")
            if checkin["checkin_id"] not in known:
                patient["checkiny"].append(deepcopy(checkin))
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
