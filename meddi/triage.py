"""Small triage prototype: 1 = green, 2 = yellow, 3 = orange, 4 = red.

None means the criterion needs review, not that the patient is fine.
Source: rakathon_meddi_onco_data/docs/pravidla_triaze.md, sections 3–4.
evaluate_triage handles flat facts; evaluate_checkin consumes prepared forms.
The check-in evaluator supports the color conditions from protocol sections 3–5.
Text interpretation, contact routing and clinical validation are separate work.
"""

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

from .clinical_rules import HANDLED_QUESTIONS, HANDLED_VITALS, evaluate_clinical_rules
from .common_types import Severity
from .validation import number, prepared_inputs

RULES_SOURCE = "rakathon_meddi_onco_data/docs/pravidla_triaze.md"


def fever_score(temperature, recent_chemotherapy):
    """Fever >= 38 C during chemotherapy or within 6 weeks after it is red.

    Source: rakathon_meddi_onco_data/docs/pravidla_triaze.md,
    section 3, Red / Horečka. Chills are not covered by this function.
    """
    number("temperature_c", temperature)
    if recent_chemotherapy is not None and type(recent_chemotherapy) is not bool:
        raise ValueError("chemotherapy_within_6_weeks must be bool or None")
    if temperature is None:
        return None
    if temperature < 38:
        return Severity.GREEN
    if recent_chemotherapy is None:
        return None
    return Severity.RED if recent_chemotherapy else Severity.GREEN


def oxygen_score(spo2):
    """SpO2 < 90% is red; otherwise SpO2 < 92% is orange.

    Source: rakathon_meddi_onco_data/docs/pravidla_triaze.md,
    section 3, Red and Orange / Dýchání. Baseline changes are not covered.
    """
    number("spo2_pct", spo2)
    if spo2 is None:
        return None
    if spo2 < 90:
        return Severity.RED
    if spo2 < 92:
        return Severity.ORANGE
    return Severity.GREEN


def overall_feeling_score(feeling):
    """An overall feeling score of 5 (very poor) is orange.

    Source: rakathon_meddi_onco_data/docs/pravidla_triaze.md,
    section 3, Orange / Celkový stav.
    """
    number("overall_feeling", feeling)
    if feeling is None:
        return None
    return Severity.ORANGE if feeling == 5 else Severity.GREEN


def pain_score(pain, persists_after_rescue_dose):
    """NRS 4–6 is yellow; NRS >= 7 persisting after a rescue dose is orange.

    Source: rakathon_meddi_onco_data/docs/pravidla_triaze.md,
    section 3, Orange / Bolest; section 4, pain NRS 4–6.
    Other severe-pain cases return None pending review.
    """
    number("pain_nrs", pain)
    if (
        persists_after_rescue_dose is not None
        and type(persists_after_rescue_dose) is not bool
    ):
        raise ValueError("pain_persists_after_rescue_dose must be bool or None")
    if pain is None:
        return None
    if pain < 4:
        return Severity.GREEN
    if pain <= 6:
        return Severity.YELLOW
    if persists_after_rescue_dose is True:
        return Severity.ORANGE
    # Severe pain without a confirmed rescue-dose response needs review.
    return None


def evaluate_triage(data):
    """Take the highest known severity; unresolved criteria still need review.

    Source: rakathon_meddi_onco_data/docs/pravidla_triaze.md, section 3:
    hard rules set a minimum level. Missing inputs are saved as skipped rules
    and do not suppress the result of the evaluated criteria.
    """
    scores = {
        "fever": fever_score(
            data.get("temperature_c"), data.get("chemotherapy_within_6_weeks")
        ),
        "oxygen": oxygen_score(data.get("spo2_pct")),
        "overall_feeling": overall_feeling_score(data.get("overall_feeling")),
        "pain": pain_score(
            data.get("pain_nrs"), data.get("pain_persists_after_rescue_dose")
        ),
    }
    level = max(
        (score for score in scores.values() if score is not None),
        default=None,
    )
    requires_review = None in scores.values()
    inputs = {
        "fever": ["temperature_c", "chemotherapy_within_6_weeks"],
        "oxygen": ["spo2_pct"],
        "overall_feeling": ["overall_feeling"],
        "pain": ["pain_nrs"]
        + (
            ["pain_persists_after_rescue_dose"]
            if data.get("pain_nrs") is not None and data["pain_nrs"] >= 7
            else []
        ),
    }
    skipped_rules = []
    for criterion, fields in inputs.items():
        missing = [field for field in fields if data.get(field) is None]
        if scores[criterion] is None and missing:
            skipped_rules.append(
                {"rule_id": criterion, "missing_fields": missing, "evidence": []}
            )
    return {
        "color": level.name.lower() if level is not None else None,
        "scores": scores,
        "requires_review": requires_review,
        "skipped_rules": skipped_rules,
    }


def evaluate_checkin(
    prepared: dict, context: dict | None = None, observations: dict | None = None
) -> dict:
    """Apply supported rules to form.prepare_checkin output with source evidence.

    Context contains explicit facts available at the check-in time, never a
    whole patient file or reference evaluation. Supported context fields are
    chemotherapy_within_6_weeks, pain_persists_after_rescue_dose, and
    suicide_plan_intent_or_means (bool/None).
    Missing rule inputs are retained in skipped_rules and excluded from color
    selection, as requested for this development step. Review issues remain
    visible even when the evaluated rules return green.
    Additional treatment flags and symptom observations are documented in
    clinical_rules.py and docs/architecture.md; only explicit facts are used.
    """
    prepared_inputs(prepared)
    context = context or {}
    clinical = evaluate_clinical_rules(prepared, context, observations or {})
    for field in (
        "chemotherapy_within_6_weeks",
        "pain_persists_after_rescue_dose",
        "suicide_plan_intent_or_means",
    ):
        if context.get(field) is not None and type(context[field]) is not bool:
            raise ValueError(f"Context field {field} must be bool or None")
    reasons = []
    review_issues = []
    skipped_rules = []
    supplied_criteria = set()
    fever_observations = []
    scores = {"fever": None, "oxygen": None, "overall_feeling": None, "pain": None}

    def issue(code, message, evidence):
        review_issues.append({"code": code, "message": message, "evidence": evidence})

    def skip(rule_id, missing_fields, evidence):
        skipped_rules.append(
            {
                "rule_id": rule_id,
                "missing_fields": missing_fields,
                "evidence": deepcopy(evidence),
            }
        )

    def record(rule_id, score, message, evidence, section, provisional=False):
        previous = scores.get(rule_id)
        if score is not None and (previous is None or score > previous):
            scores[rule_id] = score
        if score is not None and score > Severity.GREEN:
            reasons.append(
                {
                    "rule_id": rule_id,
                    "color": score.name.lower(),
                    "message": message,
                    "source": f"{RULES_SOURCE}, {section}",
                    "evidence": evidence,
                    "provisional": provisional,
                    "uncertainty_source": f"{RULES_SOURCE}, §6.4"
                    if provisional
                    else None,
                }
            )

    def check_fever(has_fever, evidence):
        supplied_criteria.add("fever")
        fever_observations.append((has_fever, evidence))
        chemotherapy = context.get("chemotherapy_within_6_weeks")
        if not has_fever:
            record("fever", Severity.GREEN, "", evidence, "§3 / Horečka")
            return
        treatment_evidence = {
            "kind": "context",
            "field": "chemotherapy_within_6_weeks",
            "value": chemotherapy,
        }
        if chemotherapy is None:
            skip("fever", ["chemotherapy_within_6_weeks"], evidence)
            issue(
                "chemotherapy_context_unknown",
                "Ověřte probíhající chemoterapii nebo podání v posledních 6 týdnech; pravidlo bylo přeskočeno.",
                evidence,
            )
            return
        if chemotherapy is False:
            record("fever", Severity.GREEN, "", evidence, "§3 / Horečka")
            issue(
                "fever_outside_chemotherapy",
                "Horečka mimo kontext chemoterapie vyžaduje samostatné posouzení.",
                evidence,
            )
            return
        record(
            "fever",
            Severity.RED,
            "Teplota alespoň 38 °C v kontextu chemoterapie vyžaduje červenou úroveň.",
            evidence + [treatment_evidence],
            "§3 / Červená / Horečka",
        )

    vitals = prepared.get("vital_signs") or {}
    for field, measurement in vitals.items():
        if measurement is None or measurement.get("hodnota") is None:
            continue
        value = measurement["hodnota"]
        evidence = [{"kind": "vital_sign", "field": field, **deepcopy(measurement)}]
        if field == "teplota_c":
            check_fever(value >= 38, evidence)
        elif field == "spo2_pct":
            supplied_criteria.add("oxygen")
            record(
                "oxygen",
                oxygen_score(value),
                "Saturace kyslíku je pod 90 %."
                if value < 90
                else "Saturace kyslíku je pod 92 %.",
                evidence,
                "§3 / Dýchání",
            )
        elif field not in HANDLED_VITALS:
            issue(
                "unassessed_measurement",
                "Měření zatím není pokryté pravidly tohoto kroku.",
                evidence,
            )

    for answer in prepared["answers"]:
        key = (answer["questionnaire_id"], answer["question_id"])
        index = answer["option_indices"]
        value = answer["value"]
        evidence = [{"kind": "answer", **deepcopy(answer)}]
        if value is None and index is None:
            issue(
                "missing_answer",
                "Odpověď chybí; nelze ji považovat za popření příznaku.",
                evidence,
            )
            continue
        if (
            key in HANDLED_QUESTIONS
            and not (key == ("nezadouci_ucinky", "prujem") and index == 3)
        ) or (key == ("nezadouci_ucinky", "zvraceni") and index in (0, 1, 2)):
            continue
        if key == ("nezadouci_ucinky", "pocit") and index is not None:
            supplied_criteria.add("overall_feeling")
            record(
                "overall_feeling",
                overall_feeling_score(index + 1),
                "Celkový pocit je 5 = velmi špatně.",
                evidence,
                "§3 / Oranžová / Celkový stav",
            )
        elif key == ("nezadouci_ucinky", "teplota") and index is not None:
            # The selected range proves the threshold, not an exact temperature.
            check_fever(index >= 1, evidence)
        elif key == ("bolest_analgeticka_terapie", "nrs") and value is not None:
            supplied_criteria.add("pain")
            persists = context.get("pain_persists_after_rescue_dose")
            score = pain_score(value, persists)
            if value >= 7 and persists is None:
                skip("pain", ["pain_persists_after_rescue_dose"], evidence)
                issue(
                    "rescue_dose_response_unknown",
                    "Ověřte, zda silná bolest nepovolila po SOS dávce; pravidlo bylo přeskočeno.",
                    evidence,
                )
            elif score is None:
                issue(
                    "severe_pain_needs_review",
                    "Silná bolest vyžaduje upřesnění aktuálního stavu po SOS dávce.",
                    evidence,
                )
            pain_evidence = (
                evidence
                + [
                    {
                        "kind": "context",
                        "field": "pain_persists_after_rescue_dose",
                        "value": persists,
                    }
                ]
                if value >= 7
                else evidence
            )
            record(
                "pain",
                score,
                "Bolest NRS je mezi 4 a 6."
                if value <= 6
                else "Bolest NRS je alespoň 7 a nepovolila po SOS dávce."
                if persists is True
                else "Silná bolest vyžaduje upřesnění účinku SOS dávky.",
                pain_evidence,
                "§4 / Bolest" if value <= 6 else "§3 / Oranžová / Bolest",
            )
        elif key == ("bolest_analgeticka_terapie", "sos") and value is not None:
            record(
                "rescue_dose_count",
                Severity.YELLOW if value >= 3 else Severity.GREEN,
                "Pacient potřebuje alespoň 3 SOS dávky analgetik denně.",
                evidence,
                "§4 / Bolest",
            )
        elif key == ("nezadouci_ucinky", "dusnost") and index in (0, 3):
            record(
                "breathlessness_at_rest",
                Severity.RED if index == 3 else Severity.GREEN,
                "Pacient udává dušnost i v klidu.",
                evidence,
                "§3 / Červená / Dýchání",
            )
        elif key == ("nezadouci_ucinky", "bol_hrud") and index in (0, 1):
            record(
                "new_chest_pain",
                Severity.RED if index == 1 else Severity.GREEN,
                "Pacient udává nově vzniklou bolest na hrudi.",
                evidence,
                "§3 / Červená / Hrudník",
            )
        elif key == ("nezadouci_ucinky", "prujem") and index == 2:
            record(
                "diarrhea",
                Severity.RED,
                "Zvolená odpověď udává více než 7 stolic nad normál za 24 hodin.",
                evidence,
                "§3 / Červená / Průjem",
            )
        elif key == ("psychoonkologicky_screening", "sebevrazda") and index in (0, 1):
            if index == 0:
                details = context.get("suicide_plan_intent_or_means")
                record(
                    "suicidal_thoughts",
                    Severity.RED if details is True else Severity.ORANGE,
                    "Pacient udává myšlenky na sebevraždu a plán, úmysl nebo prostředky."
                    if details is True
                    else "Pacient odpověděl ano na otázku o myšlenkách na sebevraždu.",
                    evidence
                    + [
                        {
                            "kind": "context",
                            "field": "suicide_plan_intent_or_means",
                            "value": details,
                        }
                    ],
                    "§3 / Psychika",
                )
                if details is None:
                    skip(
                        "suicide_plan_intent_or_means",
                        ["suicide_plan_intent_or_means"],
                        evidence,
                    )
                    issue(
                        "suicide_risk_details_unknown",
                        "Je nutné ověřit plán, úmysl nebo prostředky; červené pravidlo bylo přeskočeno, známá oranžová zůstává.",
                        evidence,
                    )
            else:
                record(
                    "suicidal_thoughts", Severity.GREEN, "", evidence, "§3 / Psychika"
                )
        else:
            issue(
                "unassessed_answer",
                "Odpověď zatím není pokryta pravidly tohoto kroku.",
                evidence,
            )

    if len({has_fever for has_fever, _ in fever_observations}) > 1:
        issue(
            "conflicting_temperature",
            "Měření a odpověď se liší v přítomnosti horečky; do vyjasnění platí horší varianta (§6.4).",
            [item for _, evidence in fever_observations for item in evidence],
        )
    for criterion in ("fever", "oxygen", "overall_feeling", "pain"):
        if scores[criterion] is None:
            issue("unresolved_criterion", f"Kritérium {criterion} nelze uzavřít.", [])
            if criterion not in supplied_criteria:
                fields = {
                    "fever": "temperature_c",
                    "oxygen": "spo2_pct",
                    "overall_feeling": "overall_feeling",
                    "pain": "pain_nrs",
                }
                skip(criterion, [fields[criterion]], [])
    if prepared.get("patient_message"):
        issue(
            "unassessed_patient_message",
            "Zpráva pacienta vyžaduje zpracování a má přednost před dotazníkem (§6.2).",
            [
                {"kind": "patient_message", "value": prepared["patient_message"]},
            ],
        )
    if prepared.get("attachments"):
        issue(
            "unassessed_attachments",
            "Přílohy vyžadují posouzení.",
            deepcopy(prepared["attachments"]),
        )
    if prepared.get("status") != "vyplneno":
        issue("checkin_not_completed", "Check-in není označen jako vyplněný.", [])

    scores.update(clinical["scores"])
    reasons.extend(clinical["reasons"])
    skipped_rules.extend(clinical["skipped_rules"])
    review_issues.extend(clinical["review_issues"])
    level = max((score for score in scores.values() if score is not None), default=None)
    return {
        "patient_id": prepared.get("patient_id"),
        "checkin_id": prepared.get("checkin_id"),
        "color": level.name.lower() if level is not None else None,
        "scores": scores,
        "reasons": reasons,
        "non_green_answers": deepcopy(prepared["non_green_answers"]),
        "skipped_rules": skipped_rules,
        "requires_review": bool(review_issues or skipped_rules),
        "review_issues": review_issues,
        "scope": "supported_structured_checkin_rules",
    }


def main():
    """Read prepared JSON and print the result; no clinical rules here."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", type=Path)
    parser.add_argument(
        "--checkin", action="store_true", help="evaluate prepare_checkin output"
    )
    parser.add_argument(
        "--context", type=Path, help="explicit facts available at check-in time"
    )
    parser.add_argument(
        "--observations",
        type=Path,
        help="explicit symptom observations available at check-in time",
    )
    args = parser.parse_args()
    data = json.loads(args.input_file.read_text(encoding="utf-8-sig"))
    if args.context and not args.checkin:
        parser.error("--context requires --checkin")
    if args.observations and not args.checkin:
        parser.error("--observations requires --checkin")
    context = (
        json.loads(args.context.read_text(encoding="utf-8-sig"))
        if args.context
        else None
    )
    observations = (
        json.loads(args.observations.read_text(encoding="utf-8-sig"))
        if args.observations
        else None
    )
    result = (
        evaluate_checkin(data, context, observations)
        if args.checkin
        else evaluate_triage(data)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
