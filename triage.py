"""Compatibility entry points backed by meddi's shared deterministic rules.

New integrations use meddi.pipeline.evaluate_contact. The flat entry point
retains its four-criterion scope, but no longer duplicates their logic.
"""

import argparse
import json
from pathlib import Path

from meddi.common_types import Severity
from meddi.pipeline import evaluate_contact
from meddi.triage import (
    evaluate_triage as _evaluate_flat,
)
from meddi.triage import (
    fever_score,
    overall_feeling_score,
    oxygen_score,
    pain_score,
)

__all__ = [
    "Severity",
    "evaluate_intake",
    "evaluate_pipeline_packet",
    "evaluate_triage",
    "fever_score",
    "overall_feeling_score",
    "oxygen_score",
    "pain_score",
]


def evaluate_triage(data):
    """Legacy flat inputs; known minimum is separate from assessment completeness."""
    result = _evaluate_flat(data)
    minimum = result["color"]
    return {
        **result,
        "minimum_color": minimum,
        "color": None if minimum == "green" and result["requires_review"] else minimum,
        "assessment_status": "incomplete" if result["requires_review"] else "complete",
        "scope": "flat_four_criteria",
    }


def evaluate_pipeline_packet(packet, context=None, *, patient_snapshot=None, now=None):
    """Compatibility name for the shared full-rule backend facade."""
    return evaluate_contact(packet, patient_snapshot, context=context, now=now)


def evaluate_intake(answer, context=None):
    """Accept an existing intake v2 answer or a full LLM pipeline packet."""
    if "question_answers" in answer or answer.get("kind") == "llm_intake":
        return evaluate_pipeline_packet(answer, context=context)
    question = {
        "questionnaire_id": answer["dotaznik_id"],
        "question_id": answer["otazka_id"],
    }
    value = answer.get("odpoved_index")
    if value is None:
        value = answer.get("odpoved")
    packet = {
        "kind": "llm_intake",
        "schema_version": 1,
        "facts": [],
        "question_answers": [
            {
                "question": question,
                "confirmed": answer.get("confirmed", False),
                "state": answer.get("state"),
                "value": value,
            }
        ],
    }
    return evaluate_pipeline_packet(packet, context=context)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input_file.read_text(encoding="utf-8-sig"))
    print(json.dumps(evaluate_triage(data), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
