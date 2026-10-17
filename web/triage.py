"""Connect web views to the shared triage backend, without clinical rules."""

from copy import deepcopy
from datetime import datetime

from meddi.disposition import resolve_disposition
from meddi.patient_inputs import build_triage_inputs
from meddi.pipeline import evaluate_contact
from meddi.triage import TRIAGE_RULES_VERSION, evaluate_checkin
from web.export import meddi_record


def assess_contact(packet: dict, patient: dict, at: datetime) -> dict:
    """Use the contact's facts and time-bounded treatment context.

    Only the contact's validated measurements become current vital signs.
    The existing patient adapter supplies derived trends and treatment sources,
    but no narrative notes, old raw vitals or reference data enter the pipeline.
    """
    if packet["message"]["patient_id"] != patient["patient_id"]:
        raise ValueError("Kontakt nepatří vybranému pacientovi.")
    current = evaluate_contact(packet, now=at)
    checkin = meddi_record(packet, at, assessment=current)["checkiny"][0]
    prepared, context, observations = build_triage_inputs(patient, checkin)
    snapshot = {
        "patient_id": patient["patient_id"],
        "as_of": at.isoformat(),
        "context": {
            field: {
                "value": value,
                "source": prepared["context_sources"].get(field),
            }
            for field, value in context.items()
            if value is not None
        },
        "observations": observations,
    }
    return evaluate_contact(packet, snapshot, now=at)


def checkin_assessments(patient: dict) -> list[dict]:
    """Replay each recorded check-in at its own time; reuse saved web results."""
    assessments = []
    for checkin in sorted(
        patient.get("checkiny", []),
        key=lambda item: (item["datum"], item.get("cas") or ""),
    ):
        saved = checkin.get("triage_assessment")
        if saved is not None:
            if (
                saved.get("kind") != "meddi_contact_assessment"
                or saved.get("patient_id") != patient["patient_id"]
                or f"WEB-{saved.get('checkin_id')}" != checkin["checkin_id"]
            ):
                raise ValueError("Uložená triáž nepatří tomuto check-inu.")
            result = deepcopy(saved)
            if saved.get("rules_version") != TRIAGE_RULES_VERSION:
                # Re-evaluate the frozen, time-bounded inputs, never today's
                # patient history. The stored assessment remains an audit record.
                inputs = saved["triage_inputs"]
                current = evaluate_checkin(
                    inputs["prepared"], inputs["context"], inputs["observations"]
                )
                incomplete = saved["requires_review"] or current["requires_review"]
                result.update(current)
                result.update(
                    requires_review=incomplete,
                    assessment_status="incomplete" if incomplete else "complete",
                )
                result = resolve_disposition(
                    result,
                    needs_clinical_review=bool(
                        current["needs_clinical_review"]
                        or saved.get("adapter_issues")
                        or saved.get("unprocessed_facts")
                        or (saved.get("intake") or {}).get("unmapped_concepts")
                        or (saved.get("intake") or {}).get(
                            "unknown_subject_fact_indices"
                        )
                    ),
                )
        else:
            # The shared adapter expects the organizer's complete check-in
            # shape; empty histories/measurements are valid for web profiles.
            raw = {"dotazniky": [], **checkin}
            prepared, context, observations = build_triage_inputs(patient, raw)
            result = evaluate_checkin(prepared, context, observations)
        assessments.append(
            {
                **result,
                "checkin_id": checkin["checkin_id"],
                "date": checkin["datum"],
                "time": checkin.get("cas"),
            }
        )
    return assessments
