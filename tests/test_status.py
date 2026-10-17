from meddi.common_types import Severity
from meddi.loader import list_patient_ids, load_patient
from meddi.status import build_patient_status


def _answer(question_id, answer, index):
    return {
        "otazka_id": question_id,
        "odpoved": answer,
        "odpoved_index": index,
    }


def _checkin(checkin_id, date, cycle, answers):
    return {
        "checkin_id": checkin_id,
        "datum": date,
        "cas": "12:00",
        "cyklus": cycle,
        "dotazniky": [
            {
                "dotaznik_id": "nezadouci_ucinky",
                "odpovedi": answers,
            }
        ],
    }


def test_build_patient_status_counts_only_non_green_answers_by_cycle():
    patient = {
        "patient_id": "TEST-001",
        "diagnoza": object(),
        "komorbidity": object(),
        "leky": object(),
        "lecba": object(),
        "laboratore": object(),
        "vysetreni": object(),
        "udalosti_tymu": object(),
        "checkiny": [
            _checkin(
                "C01",
                "2026-01-01",
                1,
                [
                    _answer("pocit", "5 = velmi špatně", 4),
                    _answer("sobestacnost", "Jsem plně soběstačný", 0),
                ],
            ),
            _checkin(
                "C02",
                "2026-01-02",
                2,
                [_answer("pocit", "1 = nejlépe", 0)],
            ),
            _checkin(
                "C03",
                "2026-01-03",
                2,
                [_answer("pocit", "5 = velmi špatně", 4)],
            ),
        ],
    }

    status = build_patient_status(patient)

    assert status.patient_id == "TEST-001"

    question = next(
        question
        for question in status.questionnaire_questions
        if question.question_id == "pocit"
    )
    assert question.question_id == "pocit"
    assert question.total_count == 3
    assert question.non_green_count == 2
    assert question.counts_by_severity == {Severity.RED: 2}
    assert question.counts_by_cycle == {1: 1, 2: 1}
    assert question.last_cycle_count == 1
    assert question.last_cycle_counts_by_severity == {Severity.RED: 1}
    assert question.last_observation.checkin_id == "C03"
    assert [observation.checkin_id for observation in question.history] == [
        "C01",
        "C02",
        "C03",
    ]
    assert [observation.severity for observation in question.history] == [
        Severity.RED,
        Severity.GREEN,
        Severity.RED,
    ]
    assert [observation.response_index for observation in question.history] == [
        4,
        0,
        4,
    ]
    assert len(status.incidents) == 2
    assert all(incident.severity > Severity.GREEN for incident in status.incidents)


def test_build_patient_status_supports_questionnaire_scale_colors():
    patient = {
        "patient_id": "TEST-002",
        "checkiny": [
            {
                "checkin_id": "C01",
                "datum": "2026-01-01",
                "cyklus": 1,
                "dotazniky": [
                    {
                        "dotaznik_id": "esas",
                        "odpovedi": [
                            _answer("pohoda", 4, None),
                            _answer("bolest", 7, None),
                        ],
                    }
                ],
            }
        ],
    }

    questions = {
        question.question_id: question
        for question in build_patient_status(patient).questionnaire_questions
    }

    assert questions["pohoda"].counts_by_severity == {Severity.YELLOW: 1}
    assert questions["bolest"].counts_by_severity == {Severity.RED: 1}


def test_build_patient_status_does_not_treat_missing_cycle_as_last_cycle():
    patient = {
        "patient_id": "TEST-003",
        "checkiny": [
            {
                "checkin_id": "C01",
                "datum": "2026-01-01",
                "cyklus": None,
                "dotazniky": [
                    {
                        "dotaznik_id": "nezadouci_ucinky",
                        "odpovedi": [_answer("pocit", "5 = velmi špatně", 4)],
                    }
                ],
            }
        ],
    }

    status = build_patient_status(patient)

    question = status.questionnaire_questions[0]
    assert question.counts_by_cycle == {None: 1}
    assert question.last_cycle_count == 0


def test_build_patient_status_summarizes_measurements_and_preserves_history():
    patient = {
        "patient_id": "TEST-004",
        "checkiny": [
            {
                "checkin_id": "C01",
                "datum": "2026-01-01",
                "cyklus": 1,
                "vitalni_funkce": {
                    "tk_sys": {"hodnota": 140, "zdroj": "domaci_tlakomer"},
                    "teplota_c": {"hodnota": 36.8, "zdroj": "teplomer"},
                },
            },
            {
                "checkin_id": "C02",
                "datum": "2026-01-02",
                "cyklus": 2,
                "vitalni_funkce": {
                    "tk_sys": {"hodnota": 160, "zdroj": "domaci_tlakomer"},
                    "teplota_c": {"hodnota": None, "zdroj": None},
                },
            },
        ],
    }

    status = build_patient_status(patient)

    pressure = next(
        measurement
        for measurement in status.measurements
        if measurement.measurement_id == "tk_sys"
    )
    assert pressure.measurement_id == "tk_sys"
    assert pressure.count == 2
    assert pressure.minimum == 140
    assert pressure.maximum == 160
    assert pressure.average == 150
    assert pressure.last_observation.checkin_id == "C02"
    assert [item.value for item in pressure.history] == [140, 160]


def test_build_patient_status_finds_measurement_incidents_from_explicit_rules():
    checkins = []
    measurements = [
        (142, 92, 96),
        (145, 94, 91),
        (139, 88, 89),
        (144, 90, 96),
        (180, 110, 96),
        (89, 60, 96),
    ]
    for index, (systolic, diastolic, spo2) in enumerate(measurements, start=1):
        checkins.append(
            {
                "checkin_id": f"C{index:02}",
                "datum": f"2026-01-{index:02}",
                "cyklus": index,
                "vitalni_funkce": {
                    "tk_sys": {"hodnota": systolic, "zdroj": "tlakomer"},
                    "tk_dia": {"hodnota": diastolic, "zdroj": "tlakomer"},
                    "spo2_pct": {"hodnota": spo2, "zdroj": "oximetr"},
                    "teplota_c": {"hodnota": 38.2, "zdroj": "teplomer"},
                },
            }
        )

    status = build_patient_status({"patient_id": "TEST-005", "checkiny": checkins})

    findings = [
        (incident.checkin_id, incident.measurement_id, incident.severity)
        for incident in status.measurement_incidents
    ]
    assert findings == [
        ("C02", "spo2_pct", Severity.ORANGE),
        ("C03", "spo2_pct", Severity.RED),
        ("C04", "krevni_tlak", Severity.YELLOW),
        ("C05", "krevni_tlak", Severity.RED),
        ("C06", "krevni_tlak", Severity.RED),
    ]
    assert all(
        incident.measurement_id != "teplota_c"
        for incident in status.measurement_incidents
    )


def test_build_patient_status_accepts_all_loaded_patients():
    for patient_id in list_patient_ids():
        status = build_patient_status(load_patient(patient_id))
        assert status.patient_id == patient_id
