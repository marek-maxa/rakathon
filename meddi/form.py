"""Prepare questionnaire answers and their evidence for a later triage step."""

import json
from copy import deepcopy

from .common_types import Severity
from .loader import DATA_DIRECTORY

QUESTIONNAIRE_COLORS = {
    "zelena": Severity.GREEN,
    "zluta": Severity.YELLOW,
    "oranzova": Severity.ORANGE,
    "cervena": Severity.RED,
}
QUESTIONNAIRE_DEFINITIONS = {
    questionnaire["id"]: questionnaire
    for questionnaire in json.loads(
        (DATA_DIRECTORY / "docs" / "dotazniky_definice.json").read_text(
            encoding="utf-8"
        )
    )
}


def _selected_options(question: dict, answer: dict) -> list[dict]:
    """Resolve selected indices against the definitions, including warnings."""
    if question["typ"] not in ("jedna", "vice"):
        return []
    options = question["moznosti"]
    indices = answer.get("odpoved_index")
    if question["typ"] == "jedna":
        indices = [] if indices is None else [indices]
    elif indices is None:
        indices = []
    elif not isinstance(indices, list):
        raise ValueError(
            f"Expected a list of selected options for question {question['id']}"
        )

    selected = []
    for index in indices:
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or not 0 <= index < len(options)
        ):
            raise ValueError(
                f"Invalid option index for question {question['id']}: {index!r}"
            )
        option = options[index]
        color = option["barva"]
        if color is not None:
            try:
                color = QUESTIONNAIRE_COLORS[color].name.lower()
            except KeyError as error:
                raise ValueError(f"Unknown questionnaire color: {color}") from error
        selected.append(
            {
                "index": index,
                "text": option["text"],
                "color": color,
                "warning": option.get("upozorneni"),
            }
        )
    return selected


def _prepare_answer(questionnaire: dict, question: dict, answer: dict) -> dict:
    selected = _selected_options(question, answer)
    colors = [
        Severity[option["color"].upper()]
        for option in selected
        if option["color"] is not None
    ]
    value = answer.get("odpoved")
    if (
        questionnaire["id"] == "esas"
        and question["typ"] == "skala_1_10"
        and value is not None
    ):
        # Source: dotazniky_definice.json, ESAS / poznamka (display colors).
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 1 <= value <= 10
        ):
            raise ValueError(
                f"Invalid ESAS score for question {question['id']}: {value!r}"
            )
        colors.append(
            Severity.GREEN
            if value <= 3
            else Severity.YELLOW
            if value <= 5
            else Severity.RED
        )
    color = max(colors).name.lower() if colors else None
    return {
        "questionnaire_id": questionnaire["id"],
        "questionnaire_name": questionnaire["nazev"],
        "questionnaire_note": questionnaire.get("poznamka"),
        "question_id": question["id"],
        "question": question["text"],
        "type": question["typ"],
        "condition": question.get("podminka"),
        "instructions": question.get("navod"),
        "note": question.get("poznamka"),
        "value": deepcopy(value),
        "option_indices": deepcopy(answer.get("odpoved_index")),
        "selected_options": selected,
        "color": color,
    }


def prepare_checkin(checkin: dict) -> dict:
    """Return JSON-ready evidence from a complete check-in, without triaging it.

    Colors and warnings come from docs/dotazniky_definice.json in the bundle,
    never from cached answer colors in the incoming check-in. Uncolored answers
    remain available in answers; non_green_answers contains only known yellow,
    orange, and red answers. No clinical facts are inferred from free text.
    """
    answers = []
    for questionnaire in checkin["dotazniky"]:
        questionnaire_id = questionnaire["dotaznik_id"]
        definition = QUESTIONNAIRE_DEFINITIONS[questionnaire_id]
        questions = {question["id"]: question for question in definition["otazky"]}
        for answer in questionnaire["odpovedi"]:
            try:
                question = questions[answer["otazka_id"]]
            except KeyError as error:
                raise ValueError(
                    f"Unknown question {answer['otazka_id']} in {questionnaire_id}"
                ) from error
            prepared = _prepare_answer(definition, question, answer)
            prepared["questionnaire_instance_id"] = questionnaire.get("vyplneni_id")
            answers.append(prepared)

    return {
        "patient_id": checkin.get("patient_id"),
        "checkin_id": checkin.get("checkin_id"),
        "date": checkin.get("datum"),
        "time": checkin.get("cas"),
        "monitoring_day": checkin.get("den_sledovani"),
        "cycle": checkin.get("cyklus"),
        "cycle_day": checkin.get("den_cyklu"),
        "status": checkin.get("stav"),
        "filled_by": checkin.get("vyplnil"),
        "answers": answers,
        "non_green_answers": [
            answer
            for answer in answers
            if answer["color"] in ("yellow", "orange", "red")
        ],
        "vital_signs": deepcopy(checkin.get("vitalni_funkce")),
        "patient_message": checkin.get("zprava_pacienta"),
        "attachments": deepcopy(checkin.get("prilohy")),
    }


def evaluate_checkin(checkin: dict) -> Severity | None:
    """Keep the legacy questionnaire-color comparison working; not final triage."""
    colors = [
        Severity[answer["color"].upper()]
        for answer in prepare_checkin(checkin)["answers"]
        if answer["color"] is not None
    ]
    return max(colors, default=None)
