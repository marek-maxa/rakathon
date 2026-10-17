"""Recorded patient messages -> existing extractor -> shared rule evaluation.

Only the message reaches the model. Questionnaire, treatment and comparison
remain in Python; references and unrestricted patient records never reach it.
"""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo

from llm_intake.client import APIError, Client
from llm_intake.master import MasterExtractor, validate_facts
from llm_intake.master_contract import MessageEvent
from llm_intake.pipeline import build_pipeline_packet

from .clinical_rules import OBSERVATION_FLAGS, OBSERVATION_NUMBERS
from .disposition import resolve_disposition
from .patient_inputs import build_triage_inputs
from .pipeline import evaluate_contact
from .triage import evaluate_checkin
from .validation import VITAL_FIELDS


def message_event(checkin):
    author = checkin.get("vyplnil")
    author = (
        "patient"
        if author in {"pacient", "patient"}
        else "caregiver"
        if author
        in {"dcera", "syn", "manželka", "manzelka", "manžel", "manzel", "caregiver"}
        else "caregiver"
        if author == "pecujici"
        else "unknown"
    )
    at = datetime.fromisoformat(
        f"{checkin['datum']}T{checkin.get('cas') or '00:00:00'}"
    ).replace(tzinfo=ZoneInfo("Europe/Prague"))
    return MessageEvent(
        checkin["checkin_id"],
        checkin["patient_id"],
        checkin["zprava_pacienta"],
        at.isoformat(),
        "patient_message",
        author,
    )


def extract_message(checkin, extract=None):
    """One call, with validated facts and original event retained for reuse."""
    event = message_event(checkin)
    extractor = (
        extract
        if extract is not None
        else MasterExtractor(
            Client.from_env(),
            clinical_fields=sorted(
                OBSERVATION_FLAGS | OBSERVATION_NUMBERS | set(VITAL_FIELDS.values())
            ),
        )
    )
    facts = validate_facts(
        {"facts": [asdict(fact) for fact in extractor(event)]}, event
    )
    return {
        "schema_version": 1,
        "message": asdict(event),
        "facts": [asdict(f) for f in facts],
    }


def _conflicts(result):
    """Compare explicit statements; an omitted question is never a denial."""
    inputs = result["triage_inputs"]
    symptoms = {
        "diarrhea",
        "vomiting",
        "bleeding",
        "chest_pain",
        "new_chest_pain",
        "breathlessness",
        "breathlessness_at_rest",
        "chills",
    }
    conflicts = []

    def record(answer, field, source):
        conflicts.append(
            {
                "code": "message_questionnaire_conflict",
                "questionnaire_id": answer["questionnaire_id"],
                "question_id": answer["question_id"],
                "field": field,
                "answer": deepcopy(answer),
                "message_source": deepcopy(source),
                "follow_up": f"V dotazníku uvádíte „{answer['value']}“, ve zprávě „{source['evidence']}“. Který údaj popisuje váš aktuální stav?",
            }
        )

    for answer in inputs["prepared"]["answers"]:
        if answer["questionnaire_id"] != "nezadouci_ucinky":
            continue
        q, index = answer["question_id"], answer["option_indices"]
        if q in {"prujem", "zvraceni"} and index in (0, 1, 2):
            field = (
                "stools_above_baseline_24h"
                if q == "prujem"
                else "vomiting_episodes_24h"
            )
            lower, upper = (
                {0: (1, 3), 1: (4, 6), 2: (7, None)}
                if q == "prujem"
                else {0: (1, 2), 1: (3, 5), 2: (6, None)}
            )[index]
            for observation in inputs["observations"].get(field, []):
                source = observation.get("source") or {}
                value = observation["value"]
                if source.get("kind") == "fact" and (
                    value < lower or (upper is not None and value > upper)
                ):
                    record(answer, field, source)
        fields, state = set(), None
        if q == "ucinky" and index == [12]:
            fields, state = symptoms, False
        elif q in {"prujem", "zvraceni"} and index is not None:
            fields, state = {"diarrhea" if q == "prujem" else "vomiting"}, True
        elif q == "krvaceni" and index in {0, 1}:
            fields, state = {"bleeding"}, index == 1
        elif q == "dusnost" and index is not None:
            fields, state = {"breathlessness"}, index > 0
            if index == 0:
                fields.add("breathlessness_at_rest")
        elif q == "teplota" and index is not None:
            fields, state = {"temperature_c"}, index >= 1
        elif q == "bol_hrud" and index in {0, 1}:
            fields, state = {"new_chest_pain"}, index == 1
        for field in sorted(fields):
            for observation in inputs["observations"].get(field, []):
                source = observation.get("source") or {}
                if source.get("kind") != "fact":
                    continue
                stated = (
                    observation["value"] >= 38
                    if field == "temperature_c"
                    else observation["value"]
                )
                if stated == state:
                    continue
                record(answer, field, source)
    return conflicts


def evaluate_message_checkin(patient, checkin, *, extract=None, analysis=None):
    """Evaluate a recorded check-in, optionally reusing a saved extraction.

    No interactive answers are invented. Follow-up questions are returned to
    the caller; missing information and failures retain a concrete disposition.
    """
    raw = {"dotazniky": [], **deepcopy(checkin)}
    raw.setdefault("patient_id", patient["patient_id"])
    if raw["patient_id"] != patient["patient_id"]:
        raise ValueError("Check-in belongs to another patient")
    prepared, context, observations = build_triage_inputs(patient, raw)
    if not (raw.get("zprava_pacienta") or "").strip():
        return {
            **evaluate_checkin(prepared, context, observations),
            "message_analysis_status": "not_present",
        }
    try:
        event = message_event(raw)
        if analysis is None:
            analysis = extract_message(raw, extract)
        if analysis.get("schema_version") != 1 or analysis.get("message") != asdict(
            event
        ):
            raise ValueError("Saved analysis does not match the source message")
        facts = validate_facts({"facts": analysis["facts"]}, event)
        packet = build_pipeline_packet(event, facts)
        snapshot = {
            "patient_id": patient["patient_id"],
            "as_of": event.available_at,
            "context": {
                k: {"value": v, "source": prepared["context_sources"].get(k)}
                for k, v in context.items()
                if v is not None
            },
            "observations": observations,
        }
        # Remove the raw-text warning only after successful, validated extraction.
        prepared["patient_message"] = None
        result = evaluate_contact(
            packet, snapshot, now=event.available_at, prepared_checkin=prepared
        )
    except (APIError, ValueError, TypeError, KeyError) as exc:
        prepared["patient_message"] = raw["zprava_pacienta"]
        baseline = evaluate_checkin(prepared, context, observations)
        baseline["review_issues"].append(
            {
                "code": "message_analysis_failed",
                "message": "Zprávu se nepodařilo vyhodnotit. Je potřeba posouzení nebo opakování.",
                "evidence": [],
            }
        )
        return {
            **resolve_disposition(baseline, needs_clinical_review=True),
            "message_analysis_status": "failed",
            "message_analysis_error": (
                "missing_api_key"
                if isinstance(exc, ValueError)
                and str(exc) == "Chybí MEDDI_LLM_API_KEY."
                else "api_error"
                if isinstance(exc, APIError)
                else "invalid_analysis"
            ),
        }
    conflicts = _conflicts(result)
    followups = [item["follow_up"] for item in conflicts]
    active = {r["rule_id"] for r in result["reasons"] if r["provisional"]}
    questions_by_field = {
        "hours_without_diarrhea": "Kdy byla poslední průjmovitá stolice a kolik hodin jste nyní bez průjmu?",
        "chemotherapy_within_6_weeks": "Probíhá chemoterapie nebo kdy jste dostal(a) její poslední dávku?",
        "pain_persists_after_rescue_dose": "Užil(a) jste předepsanou SOS dávku proti bolesti a přetrvává po ní bolest?",
        "suicide_plan_intent_or_means": "Máte nyní plán, úmysl nebo prostředky, jak si ublížit?",
    }
    for skipped in result["skipped_rules"]:
        if skipped["rule_id"] in active:
            followups.extend(
                questions_by_field[field]
                for field in skipped["missing_fields"]
                if field in questions_by_field
            )
    for item in result["unprocessed_facts"]:
        if item["reason"] in {"missing_24h_window", "unsupported_or_nonexact_finding"}:
            index = item["source"]["fact_index"]
            if facts[index].concept in {
                "diarrhea.episodes",
                "diarrhea.increase_over_baseline",
            }:
                followups.append(
                    "Kolik průjmových stolic bylo za posledních 24 hodin a o kolik více oproti vašemu obvyklému stavu?"
                )
    result.update(
        message_analysis_status="complete",
        message_analysis=deepcopy(analysis),
        message_conflicts=conflicts,
        follow_up_questions=list(dict.fromkeys(followups)),
    )
    if conflicts:
        result["review_issues"].append(
            {
                "code": "message_questionnaire_conflict",
                "message": "Zpráva odporuje dotazníku. Je nutné upřesnění; do té doby platí horší podložená varianta (§6.2–4).",
                "evidence": deepcopy(conflicts),
            }
        )
        result = resolve_disposition(result, needs_clinical_review=True)
    return result
