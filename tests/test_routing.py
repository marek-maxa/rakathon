"""M4: protocol routes, Prague clock, exact boundaries and unchanged minima."""

from copy import deepcopy
from datetime import datetime, timedelta

import pytest
from flask import render_template_string

from meddi.disposition import resolve_disposition
from meddi.patient_inputs import build_triage_inputs
from meddi.pipeline import evaluate_contact
from meddi.triage import evaluate_checkin, evaluate_triage
from tests.test_backend_pipeline import packet
from tests.test_checkin_triage import prepared
from web.app import app
from web.triage import assess_contact, checkin_assessments


def disposition(color, at, **kwargs):
    return resolve_disposition(
        {"color": color, "reasons": [], "requires_review": False},
        needs_clinical_review=False,
        at=at,
        **kwargs,
    )


@pytest.mark.parametrize(
    "at,working,opening",
    [
        ("2026-10-19T06:59:59+02:00", False, "2026-10-19T07:00:00+02:00"),
        ("2026-10-19T07:00:00+02:00", True, None),
        ("2026-10-19T15:29:59+02:00", True, None),
        ("2026-10-19T15:30:00+02:00", False, "2026-10-20T07:00:00+02:00"),
        ("2026-10-16T17:00:00+02:00", False, "2026-10-19T07:00:00+02:00"),
        ("2026-10-17T10:00:00+02:00", False, "2026-10-19T07:00:00+02:00"),
        ("2026-10-18T20:00:00+02:00", False, "2026-10-19T07:00:00+02:00"),
        ("2026-10-19T05:00:00+00:00", True, None),
        ("2026-12-07T06:00:00+00:00", True, None),
    ],
)
def test_opening_boundaries_weekends_and_utc_conversion(at, working, opening):
    result = disposition("orange", at)
    route = result["routing"]
    assert route["within_working_hours"] is working
    assert route["next_center_open_at"] == opening
    assert route["contact_code"] == ("mou_doctor" if working else "mou_on_call")
    actual = datetime.fromisoformat(route["response_due_at"])
    start = datetime.fromisoformat(at)
    assert actual - start == (timedelta(hours=2) if working else timedelta())
    if not working:
        assert route["phone"] == "724 590 848"
        assert "ihned" in result["doporuceny_kontakt"]


@pytest.mark.parametrize(
    "at,due",
    [
        ("2026-10-16T10:00:00+02:00", "2026-10-19T15:30:00+02:00"),
        ("2026-10-16T15:30:00+02:00", "2026-10-19T15:30:00+02:00"),
        ("2026-10-18T23:00:00+02:00", "2026-10-19T15:30:00+02:00"),
        ("2026-10-19T06:00:00+02:00", "2026-10-19T15:30:00+02:00"),
        ("2026-10-19T07:00:00+02:00", "2026-10-20T15:30:00+02:00"),
        ("2027-12-31T10:00:00+01:00", "2028-01-03T15:30:00+01:00"),
    ],
)
def test_yellow_deadlines_follow_ordinary_weekday_calendar(at, due):
    # The MVP calendar intentionally has no public holiday/workplace schedule.
    result = disposition("yellow", at)
    assert result["routing"]["response_due_at"] == due
    assert "Při rychlém zhoršení nečekejte" in result["doporuceni_pro_pacienta"]
    assert "155" in result["doporuceni_pro_pacienta"]


@pytest.mark.parametrize(
    "at",
    [
        "2026-10-19T10:00:00+02:00",
        "2026-10-17T23:55:00+02:00",
        "2026-10-25T02:55:00+02:00",  # Fifteen real minutes cross the DST fall-back.
    ],
)
def test_red_is_immediate_and_team_deadline_is_fifteen_real_minutes(at):
    result = disposition("red", at)
    route = result["routing"]
    assert route["phone"] == "155"
    assert "Volejte ihned 155" in result["doporuceni_pro_pacienta"]
    assert datetime.fromisoformat(route["response_due_at"]) == datetime.fromisoformat(
        at
    )
    assert datetime.fromisoformat(route["team_notify_by"]) - datetime.fromisoformat(
        at
    ) == timedelta(minutes=15)
    assert result["upozornit_tym"]


@pytest.mark.parametrize("color", ["green", "yellow", "orange", "red"])
def test_routing_never_changes_clinical_minimum_and_is_repeatable(color):
    source = {
        "color": color,
        "minimum_color": color,
        "reasons": [],
        "scores": {"oxygen": 4},
        "requires_review": True,
    }
    before = deepcopy(source)
    result = resolve_disposition(
        source, needs_clinical_review=False, at="2026-10-17T10:00:00+02:00"
    )
    assert result["color"] == result["minimum_color"] == color
    assert result["scores"] == source["scores"]
    assert result["requires_review"]
    assert source == before
    assert resolve_disposition(result, needs_clinical_review=False) == result
    if color == "green":
        assert (
            not result["upozornit_tym"] and result["routing"]["response_due_at"] is None
        )


@pytest.mark.parametrize("color", ["yellow", "orange", "red"])
@pytest.mark.parametrize(
    "at", ["2026-10-19T10:00:00+02:00", "2026-10-17T10:00:00+02:00"]
)
def test_palliative_help_never_removed_or_used_to_lower_severity(color, at):
    result = disposition(color, at, palliative_care=True)
    assert result["color"] == color
    assert "24h" in result["doporuceni_pro_pacienta"]
    assert "155" in result["doporuceni_pro_pacienta"]
    if color == "red":
        assert result["routing"]["phone"] == "155"
    else:
        assert result["routing"]["contact_code"] == "palliative_team_24h"
        assert result["routing"]["phone"] is None  # Do not invent a hospice's number.


def test_missing_clock_does_not_invent_a_deadline_or_block_emergency_help():
    result = disposition("red", None)
    assert result["routing"]["time_status"] == "unknown"
    assert result["routing"]["response_due_at"] is None
    assert result["routing"]["phone"] == "155"
    with pytest.raises(ValueError, match="časové pásmo"):
        disposition("orange", "2026-10-19T10:00:00")


def test_more_specific_yellow_same_day_and_before_dose_constraints():
    result = resolve_disposition(
        {"color": "yellow", "reasons": [{"rule_id": "symptomatic_hyperglycemia"}]},
        needs_clinical_review=False,
        at="2026-10-16T17:00:00+02:00",
    )
    assert result["color"] == "yellow"
    assert result["routing"]["contact_code"] == "mou_on_call"
    assert "ještě dnes" in result["doporuceni_pro_pacienta"]
    result = resolve_disposition(
        {"color": "yellow", "reasons": [{"rule_id": "cisplatin_tinnitus"}]},
        needs_clinical_review=False,
        at="2026-10-19T10:00:00+02:00",
    )
    assert result["routing"]["before_next_dose"]
    assert "před další aplikací" in result["doporuceni_pro_pacienta"]
    unknown_time = resolve_disposition(
        {"color": "yellow", "reasons": [{"rule_id": "symptomatic_hyperglycemia"}]},
        needs_clinical_review=False,
    )
    assert unknown_time["routing"]["response_due_at"] is None
    assert unknown_time["routing"]["within_working_hours"] is None
    assert "ještě dnes" in unknown_time["doporuceni_pro_pacienta"]


def test_structured_replay_flat_and_live_contacts_route_at_their_actual_time():
    data = prepared()
    data.update(date="2026-10-17", time="10:00")
    structured = evaluate_checkin(data, observations={"orthopnea": True})
    assert structured["routing"]["contact_code"] == "mou_on_call"
    at = datetime.fromisoformat("2026-10-19T10:00:00+02:00")
    source = packet(concept="overall_feeling", value=5)
    source["message"]["available_at"] = at.isoformat()
    source["messages"] = [deepcopy(source["message"])]
    direct = evaluate_contact(source, now=at)
    live = assess_contact(
        source,
        {"patient_id": source["message"]["patient_id"], "checkiny": [], "lecba": {}},
        at,
    )
    assert direct["routing"] == live["routing"]
    assert live["routing"]["response_due_at"] == "2026-10-19T12:00:00+02:00"
    flat = evaluate_triage({"overall_feeling": 5}, at=at)
    assert flat["routing"] == live["routing"]


def test_saved_assessment_gets_routing_at_its_frozen_time_without_mutation():
    at = datetime.fromisoformat("2026-10-17T10:00:00+02:00")
    source = packet(concept="overall_feeling", value=5)
    saved = evaluate_contact(source, now=at)
    saved.pop("routing")
    raw = {
        "patient_id": saved["patient_id"],
        "checkiny": [
            {
                "checkin_id": f"WEB-{saved['checkin_id']}",
                "datum": "2026-10-17",
                "cas": "10:00",
                "triage_assessment": saved,
            }
        ],
    }
    before = deepcopy(raw)
    result = checkin_assessments(raw)[0]
    assert result["routing"]["contact_code"] == "mou_on_call"
    assert result["routing"]["as_of"] == at.isoformat()
    assert raw == before


def test_only_documented_symptomatic_palliative_care_selects_palliative_route():
    raw = {
        "patient_id": "synthetic",
        "datum": "2026-10-19",
        "cas": "10:00",
        "checkin_id": "c1",
        "dotazniky": [],
    }
    patient = {
        "patient_id": "synthetic",
        "checkiny": [],
        "lecba": {"zamer": "symptomatická paliativní péče"},
    }
    data, context, observations = build_triage_inputs(patient, raw)
    result = evaluate_checkin(data, context, {**observations, "orthopnea": True})
    assert result["routing"]["contact_code"] == "palliative_team_24h"
    assert data["context_sources"]["palliative_care"]["field"] == "lecba.zamer"
    patient["lecba"]["zamer"] = "paliativní systémová léčba"
    patient["predem_vyslovena_prani"] = (
        "synthetic wishes, not a reason to withhold care"
    )
    _, context, _ = build_triage_inputs(patient, raw)
    assert context.get("palliative_care") is not True


def test_report_and_card_render_the_same_concrete_route_and_deadline():
    assessment = disposition("red", "2026-10-17T10:00:00+02:00")
    card = {
        "assessment": assessment,
        "patient_id": "synthetic",
        "name": "Synthetic",
        "summary": "Synthetic",
        "action": "Neodkladná pomoc",
        "findings": [],
        "needs_team": True,
    }
    with app.test_request_context():
        html = render_template_string(
            "{% from '_triage.html' import triage_result %}{{ triage_result(a) }}",
            a=assessment,
        )
        compact = render_template_string(
            "{% from '_clinical_card.html' import clinical_card %}{{ clinical_card(c) }}",
            c=card,
        )
    assert "17.10.2026 10:15 CEST" in html
    assert "17.10.2026 10:15 CEST" in compact
    assert "155" in html and "155" in compact
