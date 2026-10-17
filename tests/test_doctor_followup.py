"""Demo care loop and doctor summaries, with synthetic data and no transport."""

import json
import re
from copy import deepcopy
from datetime import datetime, timedelta

from llm_intake.master_contract import Fact
from tests.test_mvp_scenarios import demo, finish, post
from tests.test_patient_portal import baseline
from tests.test_web_triage import checkin
from web.app import app
from web.clinical_view import doctor_view
from web.patient_store import load_patient, record_team_action
from web.portal import build_portal, controls_for, new_controls, update_controls

__all__ = ["demo"]


def plan(demo, *, repeat="24"):
    baseline(demo)
    report = demo.client.get("/patients/synthetic/report").get_data(as_text=True)
    token = re.search(r'name="token" value="([^"]+)"', report)[1]
    response = demo.client.post(
        "/patients/synthetic/team-action",
        data={
            "token": token,
            "action": "plan",
            "control_id": "teplota_c",
            "due_at": (demo.at - timedelta(minutes=1)).isoformat(),
            "repeat_hours": repeat,
            "note": "Výslovně zadaný syntetický plán týmu.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Plán kontroly je uložený" in response.get_data(as_text=True)


def test_manual_plan_is_shared_then_saved_answer_rearms_only_the_explicit_interval(
    demo, monkeypatch
):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return demo.at.astimezone(tz)

    monkeypatch.setattr("web.patient_report.datetime", Clock)
    plan(demo)
    page = demo.client.get("/patient").get_data(as_text=True)
    assert "K doplnění" in page and "Výslovně zadaný" in page
    assert "Každých 24 hodin" in page
    team = demo.client.get("/team?view=overdue").get_data(as_text=True)
    assert "Synthetic Person" in team and "kontrola/y po termínu" in team
    demo.client.post("/patient", data={"follow_up": "teplota_c"})
    text = "Právě mám teplotu 36,8 °C."
    demo.findings[text] = [
        Fact("temperature_c", "present", text, "patient", 36.8, "degC")
    ]
    post(demo, text)
    saved = finish(demo)
    with app.app_context():
        patient = load_patient("synthetic")
    control = next(c for c in patient["portal_controls"] if c["id"] == "teplota_c")
    assert control["completed_checkin_id"] is None
    assert datetime.fromisoformat(control["due_at"]) == demo.at + timedelta(hours=24)
    assert control["last_completed_at"] == demo.at.isoformat()
    assert patient["checkiny"][-1]["checkin_id"] == saved["checkin_id"]
    later = build_portal(patient, demo.at + timedelta(hours=25))
    assert next(c for c in later["controls"] if c["id"] == "teplota_c")["overdue"]
    assert (
        build_portal(patient, demo.at)["assessment"]["color"]
        == saved["triage_assessment"]["color"]
    )


def test_no_interval_means_one_time_control_and_no_invented_next_due(demo):
    baseline(demo)
    with app.app_context():
        record_team_action(
            "synthetic",
            now=demo.at,
            note="Jednorázová kontrola",
            control_id="teplota_c",
            due_at=demo.at.isoformat(),
        )
        patient = load_patient("synthetic")
    controls = controls_for(patient)
    reply = checkin("NEW", "2026-10-18", feeling=0, temperature=36.8)
    update_controls(patient, controls, reply)
    control = next(c for c in controls if c["id"] == "teplota_c")
    assert control["completed_checkin_id"] == "NEW"
    assert not control["repeat_hours"]
    assert control["due_at"] == demo.at.isoformat()


def test_plan_and_future_completion_are_not_visible_before_their_availability(demo):
    initial = baseline(demo)
    future = demo.at + timedelta(days=1)
    with app.app_context():
        record_team_action(
            "synthetic",
            now=future,
            note="FUTURE_PLAN_CANARY",
            control_id="teplota_c",
            due_at=(future + timedelta(hours=1)).isoformat(),
            repeat_hours="24",
        )
        patient = load_patient("synthetic")
    earlier = build_portal(patient, demo.at)
    control = next(c for c in earlier["controls"] if c["id"] == "teplota_c")
    assert control["due"] is None and not control.get("plan_note")
    assert earlier["assessment"]["checkin_id"] == initial["checkin_id"]
    future_reply = checkin("FUTURE", "2026-10-18", feeling=0, temperature=36.8)
    future_reply["cas"] = "14:00"
    update_controls(patient, controls_for(patient), future_reply)
    patient["checkiny"].append(future_reply)
    before_reply = build_portal(patient, future)
    task = next(c for c in before_reply["controls"] if c["id"] == "teplota_c")
    assert not task.get("last_completed_at")


def test_message_only_finding_creates_a_control_without_inventing_an_answer(demo):
    text = "Nemůžu v noci spát."
    demo.findings[text] = [Fact("sleep_difficulty", "present", text, "patient")]
    post(demo, text)
    saved = finish(demo)
    controls = new_controls(saved)
    finding = next(c for c in controls if c.get("concept") == "sleep_difficulty")
    assert finding["kind"] == "finding" and finding["reason"] == text
    assert not saved["dotazniky"]
    response = demo.client.post(
        "/patient", data={"follow_up": finding["id"]}, follow_redirects=True
    )
    assert "Jak se od poslední kontroly změnila tato potíž" in response.get_data(
        as_text=True
    )


def test_plan_validation_is_atomic_and_contact_never_changes_clinical_level(demo):
    baseline(demo)
    with app.app_context():
        for interval in ("nan", "-1", "0", "nonsense"):
            try:
                record_team_action(
                    "synthetic",
                    now=demo.at,
                    note="Plan",
                    control_id="teplota_c",
                    due_at=demo.at.isoformat(),
                    repeat_hours=interval,
                )
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid interval accepted")
        assert not demo.path.exists()
        before = deepcopy(load_patient("synthetic")["checkiny"])
        record_team_action(
            "synthetic", now=demo.at, note="Telefonicky domluveno přeměření."
        )
        after = load_patient("synthetic")
    assert after["checkiny"] == before
    assert after["demo_team_events"][-1]["kind"] == "contact"


def test_doctor_context_trends_and_timeline_exclude_future_records(demo):
    one = checkin("ONE", "2026-10-15", feeling=1, temperature=36.8)
    two = checkin("TWO", "2026-10-16", feeling=1, temperature=37.4)
    demo.patient["checkiny"] = [one, two]
    demo.patient["leky"] = [
        {"lek": "KNOWN_DRUG", "od_data": "2026-10-01"},
        {"lek": "FUTURE_DRUG", "od_data": "2026-10-19"},
    ]
    demo.patient["laboratore"] = [
        {
            "test": "Known lab",
            "kod": "known",
            "hodnota": 4,
            "datum": "2026-10-15",
            "cas": "08:00",
        },
        {"test": "FUTURE_LAB", "hodnota": 5, "datum": "2026-10-20"},
    ]
    demo.patient["udalosti_tymu"] = [
        {"datum": "2026-10-15", "text": "KNOWN_CONTACT"},
        {"datum": "2026-10-20", "text": "FUTURE_CONTACT"},
    ]
    assessments = [
        {
            "checkin_id": c["checkin_id"],
            "date": c["datum"],
            "time": c["cas"],
            "color": "green",
        }
        for c in [one, two]
    ]
    view = doctor_view(demo.patient, assessments, demo.at)
    assert "FUTURE_" not in json.dumps(view, ensure_ascii=False, default=str)
    assert view["context"]["medications"] == ["KNOWN_DRUG"]
    assert view["trends"][0]["first"] == "36,8" and view["trends"][0]["last"] == "37,4"
    assert any(row["text"] == "KNOWN_CONTACT" for row in view["timeline"])
