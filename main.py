"""Print ground truth and rule-based triage for each patient check-in."""

import argparse
import sys

from meddi.common_types import Severity
from meddi.loader import list_patient_ids, load_ground_truth, load_patient
from meddi.messages import evaluate_message_checkin
from meddi.patient_inputs import build_triage_inputs
from meddi.triage import evaluate_checkin


def compare_patient(
    patient: dict, references: list[dict], *, with_messages=False, extract=None
) -> list[dict]:
    """Compare rule results with separate references, paired by check-in ID."""
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
        # The adapter only sees patient facts available at the current instant.
        if with_messages:
            triage = evaluate_message_checkin(
                patient,
                checkin,
                extract=extract,
                analysis=checkin.get("patient_message_analysis"),
            )
        else:
            prepared, context, observations = build_triage_inputs(patient, checkin)
            triage = evaluate_checkin(
                prepared, context=context, observations=observations
            )
        rules_color = Severity[triage["color"].upper()] if triage["color"] else None
        winning_reasons = [
            reason for reason in triage["reasons"] if reason["color"] == triage["color"]
        ]
        reference = references_by_id[checkin_id]
        reference_color = Severity(reference["uroven"])
        comparison = (
            "undetermined"
            if rules_color is None
            else "match"
            if rules_color == reference_color
            else "lower"
            if rules_color < reference_color
            else "higher"
        )
        results.append(
            {
                "checkin_id": checkin_id,
                "rules_color": triage["color"],
                "reference_color": reference_color.name.lower(),
                "reference_reason": reference.get("zduvodneni"),
                "comparison": comparison,
                "requires_review": triage["requires_review"],
                "provisional": bool(winning_reasons)
                and all(reason["provisional"] for reason in winning_reasons),
                "reasons": triage["reasons"],
                "review_issues": triage["review_issues"],
                "skipped_rules": triage["skipped_rules"],
                "message_analysis_status": triage.get(
                    "message_analysis_status", "not_requested"
                ),
                "message_analysis_error": triage.get("message_analysis_error"),
                "message_conflicts": triage.get("message_conflicts", []),
                "follow_up_questions": triage.get("follow_up_questions", []),
            }
        )
    return results


def compare_patients(patient_ids: list[str], *, with_messages=False) -> list[dict]:
    """Load and compare each requested patient's check-ins."""
    return [
        {
            "patient_id": patient_id,
            "checkins": compare_patient(
                load_patient(patient_id),
                load_ground_truth(patient_id),
                with_messages=with_messages,
            ),
        }
        for patient_id in patient_ids
    ]


def count_matches(patients: list[dict]) -> tuple[int, int]:
    """Return the number of matching check-ins and the total check-in count."""
    checkins = [checkin for patient in patients for checkin in patient["checkins"]]
    matches = sum(checkin["comparison"] == "match" for checkin in checkins)
    return matches, len(checkins)


def print_comparison(
    patients: list[dict], details: bool = False, comparison: str | None = None
) -> None:
    """Print one row per check-in, including unresolved and provisional results."""
    print(
        f"{'CHECK-IN':<20} {'GROUND TRUTH':<13} {'RULES':<14} {'COMPARISON':<13} {'REVIEW':<7} MESSAGE"
    )
    for patient in patients:
        for checkin in patient["checkins"]:
            if comparison and checkin["comparison"] != comparison:
                continue
            rules = checkin["rules_color"] or "undetermined"
            if checkin["provisional"]:
                rules += "*"
            review = "yes" if checkin["requires_review"] else "no"
            print(
                f"{checkin['checkin_id']:<20} {checkin['reference_color']:<13} "
                f"{rules:<14} {checkin['comparison']:<13} {review:<7} {checkin.get('message_analysis_status', 'not_requested')}"
            )
            if details:
                if checkin.get("message_analysis_status") != "not_requested":
                    print(f"  Message: {checkin.get('message_analysis_status')}")
                if checkin.get("message_analysis_error"):
                    print(f"  Message error: {checkin['message_analysis_error']}")
                for question in checkin.get("follow_up_questions", []):
                    print(f"  Follow-up: {question}")
                print(
                    f"  Ground truth: {checkin['reference_reason'] or '(no reason supplied)'}"
                )
                for reason in checkin["reasons"]:
                    marker = " (provisional)" if reason["provisional"] else ""
                    print(f"  Rules [{reason['color']}{marker}]: {reason['message']}")
                    print(f"    Source: {reason['source']}")
                    print(f"    Evidence: {reason['evidence']}")
                if not checkin["reasons"]:
                    print(
                        "  Rules: no escalation established by the implemented rules."
                    )
                if checkin["review_issues"]:
                    codes = sorted(
                        {issue["code"] for issue in checkin["review_issues"]}
                    )
                    print(f"  Review: {', '.join(codes)}")
                for skipped in checkin["skipped_rules"]:
                    print(
                        f"  Skipped [{skipped['rule_id']}]: missing {', '.join(skipped['missing_fields'])}"
                    )
    matches, total = count_matches(patients)
    checkins = [checkin for patient in patients for checkin in patient["checkins"]]
    undetermined = sum(checkin["rules_color"] is None for checkin in checkins)
    needs_review = sum(checkin["requires_review"] for checkin in checkins)
    lower = sum(checkin["comparison"] == "lower" for checkin in checkins)
    higher = sum(checkin["comparison"] == "higher" for checkin in checkins)
    print(
        f"Matches: {matches}/{total}; undetermined: {undetermined}; review: {needs_review}"
    )
    print(
        f"Lower: {lower}; higher: {higher}. Missing inputs are skipped and retained for review; treatment context and prior check-ins are time-filtered."
    )
    states = [c.get("message_analysis_status", "not_requested") for c in checkins]
    print(
        f"Messages: complete={states.count('complete')}; failed={states.count('failed')}; "
        f"not_present={states.count('not_present')}; not_requested={states.count('not_requested')}"
    )


def main():
    # Reference explanations contain symbols that legacy Windows encodings lack.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "patient_id",
        nargs="?",
        help="compare one patient instead of all patients in the dataset",
    )
    parser.add_argument(
        "--details", action="store_true", help="show ground-truth and rule reasons"
    )
    parser.add_argument(
        "--comparison",
        choices=("lower", "higher", "match", "undetermined"),
        help="print only this comparison; summary still covers all check-ins",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--with-messages",
        action="store_true",
        default=True,
        help="Extract patient messages via the configured LLM (enabled by default)",
    )
    mode.add_argument(
        "--without-messages",
        dest="with_messages",
        action="store_false",
        help="Explicit offline baseline: evaluate structured data without LLM message extraction",
    )
    args = parser.parse_args()
    if args.with_messages:
        from pathlib import Path

        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent / "llm_intake/.env")

    patient_ids = [args.patient_id] if args.patient_id else list_patient_ids()
    patients = compare_patients(patient_ids, with_messages=args.with_messages)
    print_comparison(
        patients,
        details=args.details,
        comparison=args.comparison,
    )
    failed = [
        c
        for p in patients
        for c in p["checkins"]
        if c.get("message_analysis_status") == "failed"
    ]
    if failed:
        print(
            f"CHYBA: {len(failed)} zpráv nebylo vyhodnoceno LLM. U těchto řádků je pouze záložní výsledek strukturovaných pravidel.",
            file=sys.stderr,
        )
        if any(c.get("message_analysis_error") == "missing_api_key" for c in failed):
            print(
                "Chybí MEDDI_LLM_API_KEY. Nastavte jej v prostředí nebo v llm_intake/.env (nikoli pouze v Azure nebo v .env.example).",
                file=sys.stderr,
            )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
