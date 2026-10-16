"""Load patient inputs and reference evaluations from the local data bundle."""

import json
from pathlib import Path

DATA_DIRECTORY = Path(__file__).resolve().parent.parent / "rakathon_meddi_onco_data"


def list_patient_ids() -> list[str]:
    """Return patient IDs available in the dataset."""
    return sorted(path.stem for path in (DATA_DIRECTORY / "pacienti").glob("*.json"))


def load_patient(patient_id: str) -> dict:
    """Load one patient input JSON by its dataset ID."""
    path = DATA_DIRECTORY / "pacienti" / f"{patient_id}.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_ground_truth(patient_id: str) -> list[dict]:
    """Load a patient's separate reference evaluations."""
    path = DATA_DIRECTORY / "ground_truth" / f"{patient_id}.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))
