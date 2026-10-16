"""Aggregate questionnaire answer colors for one patient check-in."""

import json

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


def _answer_colors(
    questionnaire_id: str, question: dict, answer: dict
) -> list[Severity]:
    question_type = question["typ"]
    if question_type in ("jedna", "vice"):
        options = question["moznosti"]
        indices = answer["odpoved_index"]
        if question_type == "jedna":
            indices = [] if indices is None else [indices]
        elif indices is None:
            indices = []
        elif not isinstance(indices, list):
            raise ValueError(
                f"Expected a list of selected options for question {question['id']}"
            )

        colors = []
        for index in indices:
            if (
                not isinstance(index, int)
                or isinstance(index, bool)
                or not 0 <= index < len(options)
            ):
                raise ValueError(
                    f"Invalid option index for question {question['id']}: {index!r}"
                )
            color = options[index]["barva"]
            if color is not None:
                try:
                    colors.append(QUESTIONNAIRE_COLORS[color])
                except KeyError as error:
                    raise ValueError(f"Unknown questionnaire color: {color}") from error
        return colors

    if questionnaire_id == "esas" and question_type == "skala_1_10":
        value = answer["odpoved"]
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 1 <= value <= 10
        ):
            raise ValueError(
                f"Invalid ESAS score for question {question['id']}: {value!r}"
            )
        if value <= 3:
            return [Severity.GREEN]
        if value <= 5:
            return [Severity.YELLOW]
        return [Severity.RED]

    return []


def evaluate_checkin(patient: dict, checkin_id: str) -> Severity | None:
    """Return the highest color derived from the questionnaire definitions."""
    checkins = [
        checkin
        for checkin in patient["checkiny"]
        if checkin["checkin_id"] == checkin_id
    ]
    if not checkins:
        raise LookupError(f"Check-in not found: {checkin_id}")
    if len(checkins) > 1:
        raise ValueError(f"Duplicate check-in ID: {checkin_id}")

    colors = []
    for questionnaire in checkins[0]["dotazniky"]:
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
            colors.extend(_answer_colors(questionnaire_id, question, answer))
    if not colors:
        return None
    return max(colors)
