"""Load the synthetic patient profiles bundled with the application."""

import json
from pathlib import Path

DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "resources"


def list_patient_ids() -> list[str]:
    """Return patient IDs available in the dataset."""
    return sorted(path.stem for path in (DATA_DIRECTORY / "patients").glob("*.json"))


def load_patient(patient_id: str) -> dict:
    """Load one patient input JSON by its dataset ID."""
    if patient_id not in list_patient_ids():
        raise ValueError("Unknown patient ID.")
    path = DATA_DIRECTORY / "patients" / f"{patient_id}.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))
