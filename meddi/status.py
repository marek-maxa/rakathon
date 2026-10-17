"""Build a patient status snapshot from the loaded patient input."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .common_types import Severity
from .form import QUESTIONNAIRE_DEFINITIONS, answer_colors


@dataclass(frozen=True)
class QuestionnaireObservation:
    """One questionnaire answer, including green or uncolored answers."""

    checkin_id: str
    date: str
    cycle: int | None
    response: Any
    response_index: int | None
    severity: Severity | None


@dataclass(frozen=True)
class QuestionnaireIncident:
    """A questionnaire answer colored worse than green."""

    checkin_id: str
    date: str
    cycle: int | None
    questionnaire_id: str
    question_id: str
    question_text: str
    response: Any
    response_index: int | None
    severity: Severity


@dataclass(frozen=True)
class QuestionStatus:
    """Full answer history and non-green counts for one questionnaire question."""

    questionnaire_id: str
    question_id: str
    text: str
    total_count: int
    non_green_count: int
    counts_by_severity: dict[Severity, int]
    counts_by_cycle: dict[int | None, int]
    last_cycle_count: int
    last_cycle_counts_by_severity: dict[Severity, int]
    last_observation: QuestionnaireObservation
    last_non_green_observation: QuestionnaireObservation | None
    history: tuple[QuestionnaireObservation, ...]


@dataclass(frozen=True)
class MeasurementObservation:
    """A numeric vital-sign measurement recorded in one check-in."""

    checkin_id: str
    date: str
    cycle: int | None
    value: int | float
    source: str | None


@dataclass(frozen=True)
class MeasurementStatus:
    """Statistics and full history for one type of vital measurement."""

    measurement_id: str
    count: int
    minimum: int | float
    maximum: int | float
    average: float
    last_observation: MeasurementObservation
    history: tuple[MeasurementObservation, ...]


@dataclass(frozen=True)
class MeasurementIncident:
    """A measurement finding matching an explicit threshold rule."""

    checkin_id: str
    date: str
    cycle: int | None
    measurement_id: str
    value: str
    reason: str
    severity: Severity


@dataclass(frozen=True)
class PatientStatus:
    """Questionnaire and vital-sign status derived from patient check-ins."""

    patient_id: str
    questionnaire_questions: tuple[QuestionStatus, ...]
    incidents: tuple[QuestionnaireIncident, ...] = ()
    measurements: tuple[MeasurementStatus, ...] = ()
    measurement_incidents: tuple[MeasurementIncident, ...] = ()


def _ordered_checkins(patient_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return check-ins in their recorded date/time order."""
    return sorted(
        patient_data.get("checkiny", []),
        key=lambda checkin: (checkin.get("datum", ""), checkin.get("cas", "")),
    )


def _questionnaire_history(
    checkins: list[dict[str, Any]], last_cycle: int | None
) -> tuple[tuple[QuestionStatus, ...], tuple[QuestionnaireIncident, ...]]:
    histories: dict[tuple[str, str], list[QuestionnaireObservation]] = defaultdict(list)
    texts: dict[tuple[str, str], str] = {}
    incidents = []

    for checkin in checkins:
        for questionnaire in checkin.get("dotazniky", []):
            questionnaire_id = questionnaire["dotaznik_id"]
            definition = QUESTIONNAIRE_DEFINITIONS[questionnaire_id]
            questions = {question["id"]: question for question in definition["otazky"]}
            for answer in questionnaire.get("odpovedi", []):
                question_id = answer["otazka_id"]
                try:
                    question = questions[question_id]
                except KeyError as error:
                    raise ValueError(
                        f"Unknown question {question_id} in {questionnaire_id}"
                    ) from error

                colors = answer_colors(questionnaire_id, question, answer)
                non_green = [color for color in colors if color > Severity.GREEN]
                key = (questionnaire_id, question_id)
                texts[key] = question.get("text", answer.get("otazka", question_id))
                severity = max(colors) if colors else None
                observation = QuestionnaireObservation(
                    checkin_id=checkin["checkin_id"],
                    date=checkin["datum"],
                    cycle=checkin.get("cyklus"),
                    response=answer.get("odpoved"),
                    response_index=answer.get("odpoved_index"),
                    severity=severity,
                )
                histories[key].append(observation)
                if non_green:
                    incidents.append(
                        QuestionnaireIncident(
                            checkin_id=checkin["checkin_id"],
                            date=checkin["datum"],
                            cycle=checkin.get("cyklus"),
                            questionnaire_id=questionnaire_id,
                            question_id=question_id,
                            question_text=texts[key],
                            response=answer.get("odpoved"),
                            response_index=answer.get("odpoved_index"),
                            severity=max(non_green),
                        )
                    )

    statuses = []
    for (questionnaire_id, question_id), history in histories.items():
        non_green_history = [
            item
            for item in history
            if item.severity is not None and item.severity > Severity.GREEN
        ]
        counts_by_severity = Counter(item.severity for item in non_green_history)
        counts_by_cycle = Counter(item.cycle for item in non_green_history)
        last_cycle_history = (
            [item for item in non_green_history if item.cycle == last_cycle]
            if last_cycle is not None
            else []
        )
        statuses.append(
            QuestionStatus(
                questionnaire_id=questionnaire_id,
                question_id=question_id,
                text=texts[(questionnaire_id, question_id)],
                total_count=len(history),
                non_green_count=len(non_green_history),
                counts_by_severity=dict(counts_by_severity),
                counts_by_cycle=dict(counts_by_cycle),
                last_cycle_count=len(last_cycle_history),
                last_cycle_counts_by_severity=dict(
                    Counter(item.severity for item in last_cycle_history)
                ),
                last_observation=history[-1],
                last_non_green_observation=(
                    non_green_history[-1] if non_green_history else None
                ),
                history=tuple(history),
            )
        )
    return tuple(statuses), tuple(incidents)


def _measurement_history(
    checkins: list[dict[str, Any]],
) -> tuple[MeasurementStatus, ...]:
    histories: dict[str, list[MeasurementObservation]] = defaultdict(list)
    for checkin in checkins:
        for measurement_id, measurement in (
            checkin.get("vitalni_funkce") or {}
        ).items():
            if measurement is None or measurement.get("hodnota") is None:
                continue
            value = measurement["hodnota"]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(
                    f"Expected numeric value for vital measurement {measurement_id}"
                )
            histories[measurement_id].append(
                MeasurementObservation(
                    checkin_id=checkin["checkin_id"],
                    date=(
                        datetime.fromisoformat(measurement["observed_at"])
                        .astimezone(ZoneInfo("Europe/Prague"))
                        .date()
                        .isoformat()
                        if measurement.get("observed_at")
                        else checkin["datum"]
                    ),
                    cycle=checkin.get("cyklus"),
                    value=value,
                    source=measurement.get("zdroj"),
                )
            )

    for history in histories.values():
        history.sort(key=lambda item: item.date)

    return tuple(
        MeasurementStatus(
            measurement_id=measurement_id,
            count=len(history),
            minimum=min(item.value for item in history),
            maximum=max(item.value for item in history),
            average=sum(item.value for item in history) / len(history),
            last_observation=history[-1],
            history=tuple(history),
        )
        for measurement_id, history in histories.items()
    )


def _measurement_incidents(
    checkins: list[dict[str, Any]],
) -> tuple[MeasurementIncident, ...]:
    incidents = []
    elevated_blood_pressure_count = 0

    for checkin in checkins:
        vital_signs = checkin.get("vitalni_funkce") or {}
        systolic = (vital_signs.get("tk_sys") or {}).get("hodnota")
        diastolic = (vital_signs.get("tk_dia") or {}).get("hodnota")
        spo2 = (vital_signs.get("spo2_pct") or {}).get("hodnota")

        if systolic is not None or diastolic is not None:
            elevated = (systolic is not None and systolic >= 140) or (
                diastolic is not None and diastolic >= 90
            )
            if elevated:
                elevated_blood_pressure_count += 1

            if systolic is not None and systolic < 90:
                blood_pressure_severity = Severity.RED
                reason = "Systolický tlak pod 90 mmHg"
            elif (systolic is not None and systolic >= 180) or (
                diastolic is not None and diastolic >= 110
            ):
                blood_pressure_severity = Severity.RED
                reason = "Tlak dosáhl hranice 180/110 mmHg"
            elif elevated and elevated_blood_pressure_count >= 3:
                blood_pressure_severity = Severity.YELLOW
                reason = "Opakovaný tlak ≥ 140/90 mmHg (nejméně 3 měření)"
            else:
                blood_pressure_severity = None
                reason = ""

            if blood_pressure_severity is not None:
                incidents.append(
                    MeasurementIncident(
                        checkin_id=checkin["checkin_id"],
                        date=checkin["datum"],
                        cycle=checkin.get("cyklus"),
                        measurement_id="krevni_tlak",
                        value=f"{systolic if systolic is not None else '—'}/"
                        f"{diastolic if diastolic is not None else '—'} mmHg",
                        reason=reason,
                        severity=blood_pressure_severity,
                    )
                )

        if spo2 is not None and spo2 < 92:
            incidents.append(
                MeasurementIncident(
                    checkin_id=checkin["checkin_id"],
                    date=checkin["datum"],
                    cycle=checkin.get("cyklus"),
                    measurement_id="spo2_pct",
                    value=f"{spo2} %",
                    reason=("SpO₂ pod 90 %" if spo2 < 90 else "SpO₂ pod 92 %"),
                    severity=Severity.RED if spo2 < 90 else Severity.ORANGE,
                )
            )

    return tuple(incidents)


def build_patient_status(patient_data: dict[str, Any]) -> PatientStatus:
    """Build a status snapshot from data returned by ``load_patient``.

    Questionnaire colors are recalculated from their definitions. All recorded
    answers are preserved in each question's history; only worse-than-green
    answers are collected as incidents. Measurement incidents use only
    context-independent explicit thresholds. Only patient_id and checkiny are
    read from the patient data.
    """
    checkins = _ordered_checkins(patient_data)
    last_cycle = next(
        (
            checkin.get("cyklus")
            for checkin in reversed(checkins)
            if checkin.get("cyklus") is not None
        ),
        None,
    )
    questionnaire_questions, incidents = _questionnaire_history(checkins, last_cycle)
    return PatientStatus(
        patient_id=patient_data["patient_id"],
        questionnaire_questions=questionnaire_questions,
        incidents=incidents,
        measurements=_measurement_history(checkins),
        measurement_incidents=_measurement_incidents(checkins),
    )
