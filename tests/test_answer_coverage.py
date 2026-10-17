"""Resolved routine inputs and adverse counterexamples, without reference data."""

from copy import deepcopy

import pytest

from meddi.triage import evaluate_checkin
from tests.test_checkin_triage import neutral_forms, prepared
from tests.test_form import answer, questionnaire


@pytest.mark.parametrize(
    "question,mild,severe",
    [
        ("sobestacnost", 0, 3),
        ("sobestacnost", 1, 4),
        ("unava", 0, 2),
        ("unava", 1, 2),
        ("kuze", 0, 2),
        ("bol_klouby", 0, 2),
        ("brneni", 0, 2),
        ("bol_hlava", 0, 2),
    ],
)
def test_explicit_mild_answer_is_resolved_but_severe_sibling_is_not(
    question, mild, severe
):
    mild_data = prepared(
        *neutral_forms(),
        questionnaire("nezadouci_ucinky", answer(question, "synthetic", mild)),
    )
    before = deepcopy(mild_data)
    result = evaluate_checkin(mild_data)
    assert result["color"] == "green"
    assert not result["needs_clinical_review"]
    assert any(
        a["question_id"] == question and a["coverage"] == "mild"
        for a in result["covered_answers"]
    )
    assert mild_data == before
    severe_data = prepared(
        *neutral_forms(),
        questionnaire("nezadouci_ucinky", answer(question, "synthetic", severe)),
    )
    assert evaluate_checkin(severe_data)["color"] != "green"


def test_routing_requires_answers_in_every_selected_branch():
    data = prepared(
        *neutral_forms(),
        questionnaire(
            "nezadouci_ucinky",
            answer("ucinky", ["skin"], [6]),
            answer("kuze", "mild", 0),
        ),
    )
    assert evaluate_checkin(data)["color"] == "green"
    data["answers"] = [a for a in data["answers"] if a["question_id"] != "kuze"]
    result = evaluate_checkin(data)
    assert result["color"] == "yellow"
    assert any(i["code"] == "missing_followup_answer" for i in result["review_issues"])


def test_nested_routing_does_not_hide_a_missing_leaf():
    data = prepared(
        *neutral_forms(),
        questionnaire(
            "nezadouci_ucinky",
            answer("ucinky", ["nnz"], [0]),
            answer("nnz_typ", ["vomiting"], [2]),
        ),
    )
    assert evaluate_checkin(data)["color"] == "yellow"
    data = prepared(
        *neutral_forms(),
        questionnaire(
            "nezadouci_ucinky",
            answer("ucinky", ["nnz"], [0]),
            answer("nnz_typ", ["vomiting"], [2]),
            answer("zvraceni", "6+", 2),
        ),
    )
    assert evaluate_checkin(data)["color"] == "red"


def test_explicit_no_effects_is_not_the_same_as_empty_or_conflicting_selection():
    data = prepared(
        questionnaire("nezadouci_ucinky", answer("ucinky", ["none"], [12])),
        temperature=None,
        oxygen=None,
    )
    assert evaluate_checkin(data)["color"] == "green"
    for indices in ([], [6, 12]):
        data = prepared(
            questionnaire("nezadouci_ucinky", answer("ucinky", ["synthetic"], indices)),
            temperature=None,
            oxygen=None,
        )
        assert evaluate_checkin(data)["color"] == "yellow"


@pytest.mark.parametrize("question", ["trapeni", "sam", "psycholog"])
def test_psychosocial_negative_answer_is_resolved_while_affirmative_need_remains(
    question,
):
    for index, expected in ((1, "green"), (0, "yellow")):
        data = prepared(
            *neutral_forms(),
            questionnaire(
                "psychoonkologicky_screening", answer(question, "synthetic", index)
            ),
        )
        assert evaluate_checkin(data)["color"] == expected


def test_psychometric_scales_do_not_get_an_invented_low_score_cutoff():
    data = prepared(
        *neutral_forms(),
        questionnaire("psychoonkologicky_screening", answer("uzkost", 2)),
    )
    assert evaluate_checkin(data)["color"] == "yellow"


def test_known_stable_functional_limit_uses_actual_delta_but_unknown_baseline_does_not():
    data = prepared(
        *neutral_forms(),
        questionnaire("nezadouci_ucinky", answer("sobestacnost", "synthetic", 3)),
    )
    assert (
        evaluate_checkin(data, observations={"functional_status_drop": {"value": 0}})[
            "color"
        ]
        == "green"
    )
    for drop in ({"value": None}, None):
        assert (
            evaluate_checkin(data, observations={"functional_status_drop": drop})[
                "color"
            ]
            == "yellow"
        )
    assert (
        evaluate_checkin(data, observations={"functional_status_drop": 2})["color"]
        == "yellow"
    )


def test_context_alone_does_not_establish_a_green_assessment():
    data = prepared(
        questionnaire("psychoonkologicky_screening", answer("deti", "No", 1)),
        temperature=None,
        oxygen=None,
    )
    assert evaluate_checkin(data)["color"] == "yellow"


@pytest.mark.parametrize(
    "age,pulse,expected",
    [
        (48, 60, "green"),
        (48, 100, "green"),
        (48, 59, "yellow"),
        (48, 101, "yellow"),
        (None, 74, "yellow"),
        (8, 74, "yellow"),
        (True, 74, "yellow"),
        ("48", 74, "yellow"),
    ],
)
def test_normal_pulse_coverage_requires_known_adult_age_and_reference_range(
    age, pulse, expected
):
    data = prepared(*neutral_forms())
    data["patient_age"] = age
    data["vital_signs"]["tepova_frekvence"] = {"hodnota": pulse}
    result = evaluate_checkin(data)
    assert result["color"] == expected
    if expected == "green":
        assert "medlineplus.gov" in result["covered_measurements"][0]["source"]


def test_normal_pulse_and_mild_answers_never_cancel_red_or_unread_message():
    data = prepared(*neutral_forms(), oxygen=89)
    data["patient_age"] = 48
    data["vital_signs"]["tepova_frekvence"] = {"hodnota": 74}
    assert evaluate_checkin(data)["color"] == "red"
    data["vital_signs"]["spo2_pct"]["hodnota"] = 97
    data["patient_message"] = "Nový příznak, který ještě nebyl vyhodnocen."
    assert evaluate_checkin(data)["color"] == "yellow"


@pytest.mark.parametrize(
    "value,unit", [(float("nan"), None), (float("inf"), None), (True, None), (74, "Hz")]
)
def test_pulse_reference_range_cannot_bypass_input_validation(value, unit):
    data = prepared(*neutral_forms())
    data["patient_age"] = 48
    data["vital_signs"]["tepova_frekvence"] = {"hodnota": value, "jednotka": unit}
    with pytest.raises(ValueError):
        evaluate_checkin(data)
