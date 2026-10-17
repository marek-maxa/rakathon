"""Measurement projection and live historical context, with synthetic data only."""

from copy import deepcopy
from datetime import datetime

import pytest

from meddi.status import build_patient_status
from tests.test_web_triage import checkin, packet, patient
from web.export import meddi_record
from web.patient_report import _measurement_chart
from web.triage import assess_contact

AT = datetime.fromisoformat("2026-10-01T10:00:00+02:00")


def measured_contact(concept, value, unit):
    contact = packet()
    contact["message"].update(text="Syntetické měření.", author="caregiver")
    contact["facts"] = [
        {
            "concept": concept,
            "value": value,
            "unit": unit,
            "subject": "patient",
            "presence": "present",
            "evidence": "Syntetické měření.",
            "source_message_id": contact["message"]["id"],
        }
    ]
    return contact


@pytest.mark.parametrize(
    "concept,value,unit,raw",
    [
        ("temperature", 38.2, "degC", "teplota_c"),
        ("oxygen", 93, "%", "spo2_pct"),
        ("systolic_bp", 145, "mmHg", "tk_sys"),
        ("diastolic_bp", 95, "mmHg", "tk_dia"),
        ("glucose_mmol_l", 6.1, "mmol/l", "glykemie_mmol_l"),
        ("weight_kg", 72.5, "kg", "vaha_kg"),
        ("pulse_bpm", 80, "bpm", "tepova_frekvence"),
    ],
)
def test_same_validated_measurement_reaches_triage_history_and_chart(
    concept, value, unit, raw
):
    contact = measured_contact(concept, value, unit)
    before = deepcopy(contact)
    assessment = assess_contact(contact, patient(), AT)
    saved = meddi_record(contact, AT, assessment=assessment)["checkiny"][0]
    measured = saved["vitalni_funkce"][raw]
    assert measured["hodnota"] == value
    assert measured["podklady"][0]["value"] == value
    assert measured["podklady"][0]["source"]["source_message_id"] == "message-1"
    assert measured["observed_at"] == measured["available_at"] == AT.isoformat()
    assert saved["vyplnil"] == "pecujici"
    assert saved["zdrojove_zpravy"] == contact["messages"]
    assert saved["zprava_pacienta"] == contact["message"]["text"]
    status = build_patient_status(patient(saved))
    history = status.measurements[0]
    assert history.measurement_id == raw
    assert history.count == 1
    assert history.last_observation.value == value
    assert "WEB-message-1" in _measurement_chart(history, status.measurement_incidents)
    assert contact == before


def test_live_weight_trend_uses_past_measurements_and_treatment_sources_only():
    baseline = checkin("BASELINE", "2026-09-29")
    baseline["vitalni_funkce"] = {"vaha_kg": {"hodnota": 70}}
    future = checkin("FUTURE", "2026-10-02")
    future["vitalni_funkce"] = {"vaha_kg": {"hodnota": 30}}
    raw = patient(baseline, future, treatment={"leky": ["trastuzumab"]})
    before = deepcopy(raw)
    contact = measured_contact("weight_kg", 72.5, "kg")
    result = assess_contact(contact, raw, AT)
    observation = result["triage_inputs"]["observations"]["weight_gain_3_days_kg"][0]
    assert observation["value"] == 2.5
    assert observation["source"]["source"]["baseline_checkin"] == "BASELINE"
    assert any(
        r["rule_id"] == "cardiotoxic_edema_or_weight_gain" for r in result["reasons"]
    )
    sources = result["triage_inputs"]["prepared"]["context_sources"]
    assert (
        sources["cardiotoxic_treatment"]["source"]["drugs"][0]["name"] == "trastuzumab"
    )
    assert "chemotherapy_within_6_weeks" not in result["triage_inputs"]["context"]
    assert "FUTURE" not in str(result)
    assert "MUST NOT ENTER TRIAGE" not in str(result)
    assert raw == before


@pytest.mark.parametrize("time_text", ["Právě", "prave", "právě teď", "prave ted"])
@pytest.mark.parametrize("temperature", [36.8, 38.2])
def test_just_measured_temperature_reaches_export_and_keeps_urgent_minimum(
    time_text, temperature
):
    contact = measured_contact("temperature_c", temperature, "degC")
    text = f"{time_text} jsem naměřil {temperature} °C."
    contact["message"]["text"] = text
    contact["facts"][0].update(evidence=text, time_text=time_text)
    raw = patient(
        treatment={"leky": ["doxorubicin"], "cykly": [{"datum_d1": "2026-09-25"}]}
    )
    assessment = assess_contact(contact, raw, AT)
    saved = meddi_record(contact, AT, assessment=assessment)["checkiny"][0]
    assert saved["vitalni_funkce"]["teplota_c"]["hodnota"] == temperature
    assert (
        saved["vitalni_funkce"]["teplota_c"]["observed_at"]
        == contact["message"]["available_at"]
    )
    assert not assessment["unprocessed_facts"]
    assert assessment["color"] == ("red" if temperature >= 38 else "green")
    if temperature >= 38:
        assert assessment["minimum_color"] == "red"


@pytest.mark.parametrize("time_text", ["právě včera", "prave pred tydnem"])
def test_just_prefix_does_not_turn_an_unresolved_historical_time_into_now(time_text):
    contact = measured_contact("temperature_c", 36.8, "degC")
    text = f"{time_text} jsem naměřil 36,8 °C."
    contact["message"]["text"] = text
    contact["facts"][0].update(evidence=text, time_text=time_text)
    assessment = assess_contact(contact, patient(), AT)
    saved = meddi_record(contact, AT, assessment=assessment)["checkiny"][0]
    assert "teplota_c" not in saved["vitalni_funkce"]
    assert any(
        item["reason"] == "unresolved_observation_time"
        for item in assessment["unprocessed_facts"]
    )


def test_live_pressure_trend_counts_current_and_two_past_readings():
    history = [checkin("B1", "2026-09-29"), checkin("B2", "2026-09-30")]
    for item in history:
        item["vitalni_funkce"] = {"tk_sys": {"hodnota": 145}}
    result = assess_contact(
        measured_contact("systolic_bp", 145, "mmHg"), patient(*history), AT
    )
    obs = result["triage_inputs"]["observations"]["elevated_bp_measurements"][0]
    assert obs["value"] == 3
    assert [row["checkin_id"] for row in obs["source"]["source"]] == [
        "B1",
        "B2",
        "WEB-message-1",
    ]


def test_live_functional_trend_uses_confirmed_answer_and_baseline():
    contact = packet()
    contact["facts"] = []
    contact["question_answers"] = [
        {
            "question": {
                "questionnaire_id": "nezadouci_ucinky",
                "question_id": "sobestacnost",
            },
            "confirmed": True,
            "state": "confirmed",
            "value": 2,
        }
    ]
    result = assess_contact(contact, {**patient(), "ecog_vychozi": 0}, AT)
    assert (
        result["triage_inputs"]["observations"]["functional_status_drop"][0]["value"]
        == 2
    )


@pytest.mark.parametrize(
    "change",
    [
        {"subject": "caregiver"},
        {"certainty": "uncertain"},
        {"value": {"lower": 70, "upper": 75}},
        {"observed_at": "2026-10-02T10:00:00+02:00"},
    ],
)
def test_unusable_measurement_does_not_become_a_chart_point(change):
    contact = measured_contact("weight_kg", 72.5, "kg")
    contact["facts"][0].update(change)
    # A future message is possible in a supplied packet, never available now.
    if "observed_at" in change:
        contact["message"]["available_at"] = change["observed_at"]
    assessment = assess_contact(contact, patient(), AT)
    assert (
        meddi_record(contact, AT, assessment=assessment)["checkiny"][0][
            "vitalni_funkce"
        ]
        == {}
    )


def test_conflict_is_preserved_without_inventing_a_single_chart_point():
    contact = measured_contact("weight_kg", 72.5, "kg")
    contact["facts"].append({**contact["facts"][0], "value": 75})
    result = assess_contact(contact, patient(), AT)
    saved = meddi_record(contact, AT, assessment=result)["checkiny"][0]
    measured = saved["vitalni_funkce"]["vaha_kg"]
    assert measured["hodnota"] is None
    assert [r["value"] for r in measured["podklady"]] == [72.5, 75]
    assert not build_patient_status(patient(saved)).measurements
    assert any(
        i["code"] == "conflicting_current_values" for i in result["adapter_issues"]
    )


def test_export_rejects_assessment_from_a_different_packet():
    contact = measured_contact("weight_kg", 72.5, "kg")
    result = assess_contact(contact, patient(), AT)
    contact["message"]["text"] = "Jiný kontakt."
    with pytest.raises(ValueError, match="nepatří"):
        meddi_record(contact, AT, assessment=result)


def test_corrected_measurement_exports_only_latest_value_with_its_source():
    contact = measured_contact("weight_kg", 72.5, "kg")
    correction = {
        **contact["message"],
        "id": "correction",
        "available_at": "2026-10-01T10:01:00+02:00",
    }
    contact["messages"].append(correction)
    contact["facts"].append(
        {**contact["facts"][0], "value": 71, "source_message_id": "correction"}
    )
    at = datetime.fromisoformat(correction["available_at"])
    assessment = assess_contact(contact, patient(), at)
    saved = meddi_record(contact, at, assessment=assessment)["checkiny"][0]
    measured = saved["vitalni_funkce"]["vaha_kg"]
    assert measured["hodnota"] == 71
    assert measured["podklady"][0]["source"]["source_message_id"] == "correction"
    assert build_patient_status(patient(saved)).measurements[0].count == 1
    assert len(saved["zdrojove_zpravy"]) == 2


def test_delayed_and_unavailable_history_cannot_create_a_three_day_weight_gain():
    delayed = checkin("DELAYED", "2026-09-30")
    delayed["vitalni_funkce"] = {
        "vaha_kg": {
            "hodnota": 70,
            "observed_at": "2026-09-25T10:00:00+02:00",
            "available_at": "2026-09-30T10:00:00+02:00",
        }
    }
    unavailable = checkin("UNAVAILABLE", "2026-09-30")
    unavailable["vitalni_funkce"] = {
        "vaha_kg": {
            "hodnota": 50,
            "available_at": "2026-10-02T10:00:00+02:00",
        }
    }
    result = assess_contact(
        measured_contact("weight_kg", 72.5, "kg"), patient(delayed, unavailable), AT
    )
    obs = result["triage_inputs"]["observations"]
    assert "weight_gain_3_days_kg" not in obs
    assert obs["weight_loss_month_pct"][0]["value"] == 0
    assert "UNAVAILABLE" not in str(result)
    assert (
        build_patient_status(patient(delayed)).measurements[0].last_observation.date
        == "2026-09-25"
    )


def test_export_uses_prague_date_even_when_server_supplies_utc():
    at = datetime.fromisoformat("2026-09-30T22:30:00+00:00")
    contact = measured_contact("weight_kg", 72.5, "kg")
    contact["message"]["available_at"] = at.isoformat()
    result = assess_contact(contact, patient(), at)
    saved = meddi_record(contact, at, assessment=result)["checkiny"][0]
    assert saved["datum"] == "2026-10-01"
    assert saved["cas"] == "00:30"
    assert saved["available_at"] == "2026-10-01T00:30:00+02:00"
    assert (
        build_patient_status(patient(saved)).measurements[0].last_observation.date
        == "2026-10-01"
    )
