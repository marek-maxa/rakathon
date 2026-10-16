"""Compare questionnaire colors with reference triage levels for one patient."""

import argparse

from meddi.common_types import Severity
from meddi.form import evaluate_checkin
from meddi.loader import list_patient_ids, load_ground_truth, load_patient


def compare_patient(patient: dict, references: list[dict]) -> list[dict]:
    """Compare questionnaire colors and references, paired by check-in ID."""
    checkins = patient["checkiny"]
    checkin_ids = [checkin["checkin_id"] for checkin in checkins]
    if len(checkin_ids) != len(set(checkin_ids)):
        raise ValueError("Duplicate check-in ID in patient data")

    references_by_id = {}
    for reference in references:
        checkin_id = reference["checkin_id"]
        if checkin_id in references_by_id:
            raise ValueError(f"Duplicate check-in ID in ground truth: {checkin_id}")
        references_by_id[checkin_id] = reference

    if set(checkin_ids) != set(references_by_id):
        raise ValueError("Patient check-ins and ground-truth check-ins do not match")

    results = []
    for checkin in checkins:
        checkin_id = checkin["checkin_id"]
        questionnaire_color = evaluate_checkin(checkin)
        reference_color = Severity(references_by_id[checkin_id]["uroven"])
        comparison = (
            "no_questionnaire_color"
            if questionnaire_color is None
            else "match"
            if questionnaire_color == reference_color
            else "lower"
            if questionnaire_color < reference_color
            else "higher"
        )
        results.append(
            {
                "checkin_id": checkin_id,
                "questionnaire_color": (
                    questionnaire_color.name.lower()
                    if questionnaire_color is not None
                    else None
                ),
                "reference_color": reference_color.name.lower(),
                "comparison": comparison,
            }
        )
    return results


def compare_patients(patient_ids: list[str]) -> list[dict]:
    """Load and compare each requested patient's check-ins."""
    return [
        {
            "patient_id": patient_id,
            "checkins": compare_patient(
                load_patient(patient_id), load_ground_truth(patient_id)
            ),
        }
        for patient_id in patient_ids
    ]


def count_matches(patients: list[dict]) -> tuple[int, int]:
    """Return the number of matching check-ins and the total check-in count."""
    checkins = [checkin for patient in patients for checkin in patient["checkins"]]
    matches = sum(checkin["comparison"] == "match" for checkin in checkins)
    return matches, len(checkins)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "patient_id",
        nargs="?",
        help="compare one patient instead of all patients in the dataset",
    )
    args = parser.parse_args()

    patient_ids = [args.patient_id] if args.patient_id else list_patient_ids()
    matches, total = count_matches(compare_patients(patient_ids))
    print(f"{matches}/{total}")


if __name__ == "__main__":
    main()
