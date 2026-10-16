"""Small triage prototype: 1 = green, 2 = yellow, 3 = orange, 4 = red.

None means the criterion needs review, not that the patient is fine.
Source: rakathon_meddi_onco_data/docs/pravidla_triaze.md, sections 3–4.
Only fever, absolute oxygen saturation, overall feeling, and pain are covered.
"""

import argparse
import json
from enum import IntEnum
from pathlib import Path


class Severity(IntEnum):
    GREEN = 1
    YELLOW = 2
    ORANGE = 3
    RED = 4


def fever_score(temperature, recent_chemotherapy):
    """Fever >= 38 C during chemotherapy or within 6 weeks after it is red.

    Source: rakathon_meddi_onco_data/docs/pravidla_triaze.md,
    section 3, Red / Horečka. Chills are not covered by this function.
    """
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
    if feeling is None:
        return None
    return Severity.ORANGE if feeling == 5 else Severity.GREEN


def pain_score(pain, persists_after_rescue_dose):
    """NRS 4–6 is yellow; NRS >= 7 persisting after a rescue dose is orange.

    Source: rakathon_meddi_onco_data/docs/pravidla_triaze.md,
    section 3, Orange / Bolest; section 4, pain NRS 4–6.
    Other severe-pain cases return None pending review.
    """
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
    hard rules set a minimum level. Using max is our aggregation choice;
    the partial-rule None/review handling is a prototype limitation.
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
        default=Severity.GREEN,
    )
    requires_review = None in scores.values()
    color = level.name.lower()
    if level == Severity.GREEN and requires_review:
        color = None
    return {"color": color, "scores": scores, "requires_review": requires_review}


def main():
    """Read prepared JSON and print the result; no clinical rules here."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input_file.read_text(encoding="utf-8-sig"))
    print(json.dumps(evaluate_triage(data), indent=2))


if __name__ == "__main__":
    main()
