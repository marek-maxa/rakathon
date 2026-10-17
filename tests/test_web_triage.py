"""Web/backend integration using only synthetic contacts and patient records."""

from copy import deepcopy
from datetime import datetime

import pytest

from meddi.pipeline import evaluate_contact
from web.app import app
from web.triage import assess_contact, checkin_assessments


def checkin(checkin_id="C1", date="2026-10-01", *, feeling=None, temperature=None):
    return {
        "checkin_id": checkin_id,
        "patient_id": "synthetic",
        "datum": date,
        "cas": "10:00",
        "stav": "vyplneno",
        "dotazniky": []
        if feeling is None
        else [
            {
                "dotaznik_id": "nezadouci_ucinky",
                "odpovedi": [
                    {"otazka_id": "pocit", "odpoved_index": feeling, "odpoved": "x"}
                ],
            }
        ],
        "vitalni_funkce": {}
        if temperature is None
        else {"teplota_c": {"hodnota": temperature}},
    }


def patient(*checkins, treatment=None):
    return {
        "patient_id": "synthetic",
        "lecba": treatment or {},
        "checkiny": list(checkins),
        "nazev_scenare": "MUST NOT ENTER TRIAGE",
        "ground_truth": "MUST NOT ENTER TRIAGE",
    }


def packet():
    result = {
        "kind": "llm_intake",
        "schema_version": 1,
        "message": {
            "id": "message-1",
            "patient_id": "synthetic",
            "available_at": "2026-10-01T10:00:00+02:00",
            "text": "Jsem zmatený.",
        },
        "question_answers": [],
        "facts": [
            {
                "concept": "confusion",
                "presence": "present",
                "subject": "patient",
                "evidence": "Jsem zmatený.",
            }
        ],
    }
    result["messages"] = [result["message"]]
    return result


def test_history_uses_rule_color_instead_of_questionnaire_option_color():
    raw = patient(checkin(feeling=4))
    before = deepcopy(raw)

    result = checkin_assessments(raw)[0]

    # The definition colors this option red, while the actual triage rule is orange.
    assert result["color"] == "orange"
    assert result["requires_review"]
    assert any(reason["rule_id"] == "overall_feeling" for reason in result["reasons"])
    assert raw == before


def test_history_cannot_use_future_treatment_or_carry_old_alert_to_latest():
    treatment = {
        "leky": ["doxorubicin"],
        "cykly": [{"datum_d1": "2026-10-02"}],
    }
    raw = patient(
        checkin("C3", "2026-10-03", temperature=36.5),
        checkin("C1", "2026-10-01", temperature=38.2),
        checkin("C2", "2026-10-02", temperature=38.2),
        treatment=treatment,
    )

    first, second, latest = checkin_assessments(raw)

    assert first["color"] == "red"
    assert all(reason["provisional"] for reason in first["reasons"])
    assert first["skipped_rules"]
    assert second["color"] == "red"
    assert latest["color"] == "green"
    assert latest["minimum_color"] == "green"
    assert not latest["reasons"]


def test_live_contact_uses_shared_backend_and_keeps_source_packet():
    contact = packet()
    before = deepcopy(contact)
    at = datetime.fromisoformat("2026-10-01T10:00:00+02:00")
    result = assess_contact(contact, patient(), at)
    expected = evaluate_contact(contact, now=at)

    assert result["color"] == expected["color"] == "red"
    assert result["reasons"] == expected["reasons"]
    assert result["requires_review"]
    assert result["intake"] == contact == before
    assert "MUST NOT ENTER TRIAGE" not in str(result)


def test_old_abnormal_measurement_is_not_assumed_current_in_live_contact():
    contact = packet()
    contact["message"]["text"] = "Bez nových údajů."
    contact["facts"] = []
    result = assess_contact(
        contact,
        patient(checkin("OLD", "2026-09-01", temperature=40)),
        datetime.fromisoformat("2026-10-01T10:00:00+02:00"),
    )
    assert result["color"] == "yellow"
    assert result["minimum_color"] is None
    assert not any(item["color"] == "red" for item in result["reasons"])


def test_report_does_not_use_esas_display_colors_for_triage(
    monkeypatch,
):
    first = checkin()
    first["dotazniky"] = [
        {
            "dotaznik_id": "esas",
            "odpovedi": [{"otazka_id": "unava", "odpoved": 8}],
        }
    ]
    raw = patient(first)
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: ["synthetic"])
    monkeypatch.setattr("web.patient_report.load_patient", lambda _: raw)
    html = app.test_client().get("/patients/synthetic/report").get_data(as_text=True)
    latest = html.split('<h3 id="triage-title">', 1)[1].split("<details>", 1)[0]
    assert 'triage-yellow">Žlutá' in latest
    assert 'triage-unknown">Neurčeno' not in latest
    assert "Předběžný nález" in latest
    assert "Posouzení je neúplné" in latest
    assert "klinické vyhodnocení není pokryté" not in latest

    next_checkin = deepcopy(first)
    next_checkin.update(checkin_id="C2", datum="2026-10-02")
    next_checkin["dotazniky"][0]["odpovedi"][0]["odpoved"] = 1
    raw["checkiny"].append(next_checkin)
    earlier, current = checkin_assessments(raw)
    assert earlier["color"] == "yellow"
    assert current["color"] == "yellow"
    assert not any(item["color"] == "red" for item in current["reasons"])


@pytest.mark.parametrize(
    "finding,value,expected",
    [
        ("esas", 8, "yellow"),
        ("pain", 8, "orange"),
        ("temperature", 38.2, "red"),
        ("skin", 2, "yellow"),
    ],
)
@pytest.mark.parametrize("saved_version", [None, 4])
def test_old_saved_assessment_is_recalculated_from_frozen_inputs(
    finding, value, expected, saved_version
):
    contact = packet()
    contact["facts"] = []
    contact["message"]["text"] = "Syntetický kontakt."
    if finding == "temperature":
        contact["facts"] = [
            {
                "concept": "temperature",
                "value": value,
                "unit": "degC",
                "subject": "patient",
                "presence": "present",
                "evidence": "Syntetický kontakt.",
            }
        ]
    else:
        contact["question_answers"] = [
            {
                "question": {
                    "questionnaire_id": {
                        "esas": "esas",
                        "skin": "nezadouci_ucinky",
                        "pain": "bolest_analgeticka_terapie",
                    }[finding],
                    "question_id": {"esas": "unava", "skin": "kuze", "pain": "nrs"}[
                        finding
                    ],
                },
                "value": value,
                "confirmed": True,
                "state": "confirmed",
            }
        ]
    saved = assess_contact(
        contact, patient(), datetime.fromisoformat("2026-10-01T10:00:00+02:00")
    )
    # Reproduce an assessment produced before this fix.
    if saved_version is None:
        saved.pop("rules_version")
    else:
        saved["rules_version"] = saved_version
    saved.update(color=None, minimum_color="green", reasons=[])
    raw = patient({**checkin("WEB-message-1"), "triage_assessment": saved})
    # Future or later treatment must not be used to resolve the frozen context.
    raw["lecba"] = {"leky": ["doxorubicin"], "cykly": [{"datum_d1": "2026-10-02"}]}
    before = deepcopy(raw)
    result = checkin_assessments(raw)[0]
    assert result["color"] == expected
    assert result["minimum_color"] == (
        None if finding in {"skin", "esas"} else expected
    )
    assert result["assessment_status"] == "incomplete"
    assert result["requires_review"]
    assert all(item["provisional"] for item in result["reasons"])
    assert result["intake"] == contact
    assert raw == before


def test_report_unknown_skin_findings_show_yellow_and_a_concrete_contact(monkeypatch):
    raw = patient(checkin())
    raw["checkiny"][0]["dotazniky"] = [
        {
            "dotaznik_id": "nezadouci_ucinky",
            "odpovedi": [
                {"otazka_id": "kuze", "odpoved_index": 2, "odpoved": "synthetic"}
            ],
        }
    ]
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: ["synthetic"])
    monkeypatch.setattr("web.patient_report.load_patient", lambda _: raw)
    html = app.test_client().get("/patients/synthetic/report").get_data(as_text=True)
    latest = html.split('<h3 id="triage-title">', 1)[1].split("<details>", 1)[0]
    assert 'triage-yellow">Žlutá' in latest
    assert "Neurčeno" not in latest
    assert "Kontaktujte monitorovací centrum" in latest
    assert "následujícího pracovního dne" in latest
    assert "Posouzení je neúplné" in latest


def test_report_displays_backend_color_findings_review_and_escaped_text(monkeypatch):
    raw = patient(checkin(feeling=4))
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: ["synthetic"])
    monkeypatch.setattr("web.patient_report.load_patient", lambda _: raw)

    response = app.test_client().get("/patients/synthetic/report")
    html = response.get_data(as_text=True)
    triage = html.split('<h3 id="triage-title">', 1)[1].split("</section>", 1)[0]

    assert response.status_code == 200
    assert 'triage-orange">Oranžová' in triage
    assert "Celkový pocit je 5" in triage
    assert "Posouzení je neúplné" in triage
    assert "Co zbývá posoudit" in triage
    assert "pravidla_triaze.md" in triage

    saved = assess_contact(
        packet(), patient(), datetime.fromisoformat("2026-10-01T10:00:00+02:00")
    )
    saved["reasons"][0]["message"] = "<script>unsafe()</script>"
    raw["checkiny"] = [{**checkin("WEB-message-1"), "triage_assessment": saved}]
    html = app.test_client().get("/patients/synthetic/report").get_data(as_text=True)
    assert "&lt;script&gt;unsafe()&lt;/script&gt;" in html
    assert "<script>unsafe()</script>" not in html
