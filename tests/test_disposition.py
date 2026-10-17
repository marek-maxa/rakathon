"""Operational review, explicit next steps, and unchanged clinical evidence."""

from copy import deepcopy
from dataclasses import asdict

import pytest

from meddi.disposition import resolve_disposition
from meddi.form import prepare_checkin
from meddi.pipeline import evaluate_contact
from meddi.triage import evaluate_checkin
from tests.test_backend_pipeline import FUTURE, event, packet
from tests.test_checkin_triage import neutral_forms, prepared
from tests.test_form import answer, questionnaire


@pytest.mark.parametrize(
    "color,review,expected,step,notify",
    [
        (None, False, "yellow", "kontaktovat_tym", True),
        ("green", False, "green", "dalsi_sledovani", False),
        ("green", True, "yellow", "kontaktovat_tym", True),
        ("yellow", True, "yellow", "kontaktovat_tym", True),
        ("orange", True, "orange", "telekonzultace", True),
        ("red", True, "red", "neodkladna_pomoc", True),
    ],
)
def test_disposition_always_has_a_level_and_action_without_lowering_minimum(
    color, review, expected, step, notify
):
    source = {
        "color": color,
        "requires_review": review,
        "reasons": [],
        "scores": {"oxygen": None},
    }
    before = deepcopy(source)
    result = resolve_disposition(source, needs_clinical_review=review)
    assert result["color"] == expected
    assert result["minimum_color"] == color
    assert result["uroven"] in (1, 2, 3, 4)
    assert result["doporuceny_krok"] == step
    assert result["upozornit_tym"] is notify
    assert result["doporuceny_kontakt"]
    assert result["doporuceni_pro_pacienta"]
    assert result["scores"]["oxygen"] is None
    assert resolve_disposition(result, needs_clinical_review=review) == result
    assert source == before


def test_yellow_review_preserves_uncolored_severe_skin_and_function_answers():
    data = prepared(
        questionnaire(
            "nezadouci_ucinky",
            answer("kuze", "synthetic", 2),
            answer("sobestacnost", "synthetic", 3),
        )
    )
    result = evaluate_checkin(data)
    assert result["color"] == "yellow"
    assert result["needs_clinical_review"]
    assert result["assessment_status"] == "incomplete"
    assert result["doporuceny_krok"] == "kontaktovat_tym"
    assert result["upozornit_tym"]
    assert result["non_green_answers"] == []  # No clinical grade invented from colors.
    assert any(
        e["code"] == "unassessed_answer" for e in result["reasons"][-1]["evidence"]
    )


def test_unrelated_missing_criteria_do_not_turn_normal_assessed_contact_yellow():
    result = evaluate_checkin(prepared(*neutral_forms()))
    assert result["color"] == "green"
    assert result["skipped_rules"]  # Unasked hypothetical symptoms are unknown.
    assert result["requires_review"]
    assert not result["needs_clinical_review"]
    assert result["doporuceny_krok"] == "dalsi_sledovani"
    assert not result["upozornit_tym"]


def test_future_finding_does_not_change_current_green_disposition():
    source = packet(value=36.5)
    future = event(id="future", at=FUTURE)
    baseline = evaluate_contact(source)
    source["messages"] = [deepcopy(source["message"]), asdict(future)]
    source["facts"].append(
        {**source["facts"][0], "source_message_id": "future", "value": 40}
    )
    result = evaluate_contact(source, now=source["message"]["available_at"])
    assert baseline["color"] == result["color"] == "green"
    assert result["deferred_inputs"]
    assert not result["upozornit_tym"]


def test_unprocessed_current_fact_leads_to_yellow_with_its_source_preserved():
    source = packet(value=36.5)
    source["facts"].append(
        {**source["facts"][0], "concept": "skin_rash", "value": "severe"}
    )
    result = evaluate_contact(source)
    assert result["color"] == "yellow"
    assert result["minimum_color"] == "green"
    assert result["unprocessed_facts"]
    reasons = [
        r for r in result["reasons"] if r["rule_id"] == "clinical_review_required"
    ]
    assert len(reasons) == 1
    assert any(
        e.get("source", {}).get("fact_index") == 1 for e in reasons[0]["evidence"]
    )
    assert result["intake"] == source


@pytest.mark.parametrize("count,color", [(1, "green"), (2, "green"), (3, "yellow")])
def test_stable_missed_checkins_keep_reminder_before_three(count, color):
    data = prepare_checkin({"dotazniky": [], "stav": "nevyplneno"})
    result = evaluate_checkin(data, observations={"consecutive_missed_checkins": count})
    assert result["color"] == color
    if count < 3:
        assert "Vyplňte" in result["doporuceni_pro_pacienta"]


def test_orange_and_red_recommendations_include_immediate_out_of_hours_routes():
    data = prepared()
    data.update(date="2026-10-17", time="10:00")  # Saturday, outside center hours.
    orange = evaluate_checkin(data, observations={"orthopnea": True})
    red = evaluate_checkin(prepared(oxygen=89))
    assert "724 590 848" in orange["doporuceny_kontakt"]
    assert "Mimo pracovní dobu volejte ihned" in orange["doporuceni_pro_pacienta"]
    assert "155" in red["doporuceny_kontakt"]
    assert "Volejte ihned 155" in red["doporuceni_pro_pacienta"]
