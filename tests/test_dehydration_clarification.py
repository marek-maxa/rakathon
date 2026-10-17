"""Mentor clarification O10, supplied 2026-10-17; no model calls."""

from copy import deepcopy

import pytest

from meddi.loader import load_patient
from meddi.patient_inputs import build_triage_inputs
from meddi.pipeline import evaluate_contact
from meddi.triage import evaluate_checkin
from tests.test_backend_pipeline import OLD, TIME, packet
from tests.test_checkin_triage import neutral_forms, prepared, reason


@pytest.mark.parametrize("failure", ["cannot_keep_fluids", "cannot_drink_fluids"])
@pytest.mark.parametrize(
    "sign",
    [
        {"low_urine": True},
        {"dizziness": True},
        {"orthostatic_dizziness": True},
        {"pulse_bpm": 100.1},
        {"systolic_bp": 89.9},
    ],
)
def test_fluid_failure_with_any_dehydration_sign_is_red(failure, sign):
    result = evaluate_checkin(
        prepared(*neutral_forms()), observations={failure: True, **sign}
    )
    assert result["color"] == "red"
    assert not reason(result, "fluid_intolerance_with_dehydration")["provisional"]


@pytest.mark.parametrize("pulse", [100, 100.1])
def test_pulse_boundary_in_current_vitals(pulse):
    data = prepared(*neutral_forms())
    data["vital_signs"]["tepova_frekvence"] = {"hodnota": pulse}
    result = evaluate_checkin(data, observations={"cannot_drink_fluids": True})
    assert result["color"] == ("red" if pulse > 100 else "orange")


@pytest.mark.parametrize(
    "observations,color",
    [
        ({"cannot_drink_fluids": True}, "orange"),
        ({"cannot_drink_fluids": True, "pulse_bpm": 100}, "orange"),
        ({"cannot_drink_fluids": True, "systolic_bp": 90}, "orange"),
        ({"reduced_intake": True, "low_urine": True}, "orange"),
        ({"reduced_intake": True, "dizziness": True}, "orange"),
        ({"reduced_intake": True, "dizziness": True, "pulse_bpm": 112}, "orange"),
        ({"pulse_bpm": 112}, "green"),
        ({"cannot_drink_fluids": False, "low_urine": True}, "green"),
    ],
)
def test_no_red_without_both_established_conditions(observations, color):
    result = evaluate_checkin(prepared(*neutral_forms()), observations=observations)
    assert result["color"] == color
    assert not any(
        r["rule_id"] == "fluid_intolerance_with_dehydration"
        for r in result["reasons"]
    )


@pytest.mark.parametrize("cisplatin", [True, False, None])
def test_dehydration_red_does_not_require_cisplatin(cisplatin):
    result = evaluate_checkin(
        prepared(*neutral_forms()),
        context={"cisplatin_treatment": cisplatin},
        observations={"cannot_drink_fluids": True, "low_urine": True},
    )
    assert result["color"] == "red"


@pytest.mark.parametrize("state", ["current", "expired", "future", "resolved"])
def test_pipeline_uses_only_available_active_fluid_failure(state):
    source = packet(concept="pulse_bpm", value=112, unit="bpm")
    snapshot = {
        "patient_id": source["message"]["patient_id"],
        "as_of": TIME,
        "observations": {
            "cannot_drink_fluids": {
                "value": state != "resolved",
                "available_at": "2026-10-18T10:00:00+02:00"
                if state == "future"
                else OLD,
                "valid_until": OLD if state == "expired" else None,
                "source": "Doložené selhání polykání v probíhající epizodě.",
            }
        },
    }
    result = evaluate_contact(source, snapshot, now=TIME)
    red = [
        r for r in result["reasons"]
        if r["rule_id"] == "fluid_intolerance_with_dehydration"
    ]
    assert bool(red) is (state == "current")
    if red:
        assert result["minimum_color"] == "red"
        assert any(e["field"] == "cannot_drink_fluids" for e in red[0]["evidence"])


def _offline(patient, checkin):
    data, context, observations = build_triage_inputs(patient, checkin)
    return evaluate_checkin(data, context, observations)


def test_actual_patient_replay_without_llm_or_references():
    patient = load_patient("ONC-011")
    before = deepcopy(patient)
    c08, c09 = patient["checkiny"][7:9]
    assert _offline(patient, c08)["color"] == "orange"
    result = _offline(patient, c09)
    assert result["color"] == "red"
    why = reason(result, "fluid_intolerance_with_dehydration")
    source = next(e["source"] for e in why["evidence"] if e["field"] == "cannot_drink_fluids")
    assert source["prior_failure"]["checkin_id"] == c08["checkin_id"]
    assert source["current_report"]["checkin_id"] == c09["checkin_id"]
    assert patient == before
    for index, checkin in enumerate(patient["checkiny"]):
        checkin["patient_id"] = "renamed"
        checkin["checkin_id"] = f"arbitrary-{index}"
    patient["patient_id"] = "renamed"
    patient.pop("vychazi_ze_scenare", None)
    patient.pop("nazev_scenare", None)
    patient["checkiny"].reverse()
    assert _offline(patient, c09)["color"] == "red"


@pytest.mark.parametrize("change", ["no_failure", "future", "old", "recovery", "milder"])
def test_actual_replay_does_not_invent_or_perpetuate_fluid_failure(change):
    patient = load_patient("ONC-011")
    c08, c09 = patient["checkiny"][7:9]
    if change == "no_failure":
        c08["zprava_pacienta"] = "Polykání bolí, ale vodu piju normálně."
    elif change == "future":
        c08["datum"] = "2026-09-18"
    elif change == "old":
        c08["datum"] = "2026-09-15"
    elif change == "recovery":
        c09["zprava_pacienta"] += " Už piju vodu normálně."
    else:
        for form in c09["dotazniky"]:
            for answer in form["odpovedi"]:
                if answer["otazka_id"] == "afty":
                    answer["odpoved_index"] = 1
                    answer["odpoved"] = "Bolesti při polykání jsou silné a mění můj denní příjem stravy či tekutin."
    assert _offline(patient, c09)["color"] == "orange"


@pytest.mark.parametrize(
    "text",
    [
        "Není pravda, že nepolknu vodu.",
        "Bojím se, že nepolknu vodu.",
        "Včera jsem nemohl polknout vodu, dnes už piju normálně.",
        "Manželka říká: nepolknu vodu.",
    ],
)
def test_negation_hypothetical_history_and_other_person_are_not_current_failure(text):
    patient = load_patient("ONC-011")
    c09 = patient["checkiny"][8]
    c09["zprava_pacienta"] = text
    assert _offline(patient, c09)["color"] == "orange"


def test_caregiver_first_person_does_not_describe_patient():
    patient = load_patient("ONC-011")
    c09 = patient["checkiny"][8]
    c09["vyplnil"] = "dcera"
    c09["zprava_pacienta"] = "Nemůžu pít. Málo močím."
    assert _offline(patient, c09)["color"] == "orange"
