"""Resolve explicit mild answers and routing/context without clinical guesses.

Source: resources/questionnaires.json and resources/triage_rules.md §1, §4, §6.3.
No thresholds for psycho scales, vital signs or free text are inferred here.
"""

from .form import QUESTIONNAIRE_DEFINITIONS

ROUTING_QUESTIONS = {"ucinky", "nnz_typ", "stolice_typ", "bolesti_typ"}
# These exact choices explicitly describe no limitation or only mild symptoms.
# Other choices in the same questions remain unresolved unless a rule covers them.
MILD_CHOICES = {
    "sobestacnost": {0, 1},
    "unava": {0, 1},
    "kuze": {0},
    "bol_klouby": {0},
    "brneni": {0},
    "bol_hlava": {0},
}


def answer_coverage(
    answer: dict, answers: list[dict], observations: dict
) -> tuple[str, list[str]] | None:
    """Return mild/context/routing coverage, or leave an input for review.

    Context-only answers establish no severity. Routing is resolved only when
    every selected branch has an actual answer; its descendants are still
    evaluated separately. Targeted answers need not supply their parents.
    """
    form, question = answer["questionnaire_id"], answer["question_id"]
    index, value = answer["option_indices"], answer["value"]
    if form == "nezadouci_ucinky":
        if isinstance(index, int) and index in MILD_CHOICES.get(question, set()):
            return "mild", []
        drop = observations.get("functional_status_drop")
        entries = drop if isinstance(drop, list) else [drop]
        known_drop = any(
            (item.get("value") if isinstance(item, dict) else item) is not None
            for item in entries
        )
        if question == "sobestacnost" and known_drop:
            # The shared clinical rule already evaluates the actual change from
            # baseline (§4); a stable chronic limitation is not a new alarm.
            return "context", []
        if question in ROUTING_QUESTIONS and index:
            if question == "ucinky" and 12 in index and len(index) > 1:
                return None  # Contradictory "no effects" and positive selections.
            if question == "ucinky" and index == [12]:
                return (
                    "mild",
                    [],
                )  # Explicitly no adverse effects, not an empty selection.
            definitions = QUESTIONNAIRE_DEFINITIONS[form]["otazky"]
            selected = set(index)
            children = []
            for child in definitions:
                condition = child.get("podminka")
                if not condition:
                    continue
                parent, choice = condition.split(":")
                if parent == question and int(choice) in selected:
                    children.append(child["id"])
            present = {
                item["question_id"]
                for item in answers
                if item["questionnaire_id"] == form
                and (item["value"] is not None or item["option_indices"] is not None)
            }
            return "routing", sorted(set(children) - present)
    elif form == "psychoonkologicky_screening":
        if question in {"deti", "psychiatr"}:
            return "context", []  # Family/history, not a current symptom grade.
        if question in {"trapeni", "sam", "psycholog"} and index == 1:
            return "context", []  # Explicitly negative, no affirmative need ignored.
    elif form == "bolest_analgeticka_terapie":
        if question == "spokojenost" and index == 0:
            return "context", []  # Satisfaction never cancels a high pain score.
        if question == "nu" and index == [] and value == []:
            return "context", []  # Explicitly no selected adverse effects.
    return None
