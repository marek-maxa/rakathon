import importlib
import re
import smtplib
from unittest.mock import Mock

import pytest

from notifications import mailer
from tests.test_patient_report import _assessment
from web.app import app

report = importlib.import_module("web.patient_report")
patient_mail = importlib.import_module("web.patient_mail")


@pytest.fixture
def setup(monkeypatch, tmp_path):
    patients = {
        key: {
            "patient_id": key,
            "demografie": {"jmeno_fiktivni": key},
            "kontakt": {"email": "recipient@example.com"},
            "checkiny": [],
        }
        for key in ("synthetic-1", "synthetic-2")
    }
    monkeypatch.setitem(app.config, "TESTING", True)
    monkeypatch.setattr(report, "list_patient_ids", lambda: list(patients))
    store = importlib.import_module("web.patient_store")
    monkeypatch.setitem(app.config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "load_source_patient", patients.__getitem__)
    monkeypatch.setattr(report, "load_patient", store.load_patient)
    monkeypatch.setattr(
        report,
        "checkin_assessments",
        lambda _: [_assessment("synthetic-checkin", "yellow")],
    )
    monkeypatch.setattr(patient_mail, "list_patient_ids", lambda: list(patients))
    send = Mock()
    monkeypatch.setattr(mailer, "send_notification", send)
    return app.test_client(), send


def token(client, patient_id="synthetic-1"):
    page = client.get(f"/patients/{patient_id}/report")
    assert page.status_code == 200
    return re.search(r'name="email_token" value="([^"]+)"', page.text).group(1)


def test_team_and_report_offer_single_email_form_per_patient(setup):
    client, send = setup
    team = client.get("/team")
    assert team.status_code == 200
    assert team.text.count('class="patient-email"') == 2
    assert "/patients/synthetic-1/email" in team.text
    assert "/patients/synthetic-2/email" in team.text
    assert 'name="subject"' not in team.text
    page = client.get("/patients/synthetic-1/report")
    assert page.text.count('class="patient-email"') == 1
    assert "Odeslat zprávu" in page.text
    send.assert_not_called()


@pytest.mark.parametrize(
    "return_to,target", [("team", "/team"), ("report", "/patients/synthetic-1/report")]
)
def test_doctor_sends_predefined_notification_through_shared_transport(
    setup, return_to, target
):
    client, send = setup
    response = client.post(
        "/patients/synthetic-1/email",
        data={
            "email_token": token(client),
            "email": "attacker@example.com",
            "return_to": return_to,
            "subject": "Ignored",
            "message": "Ignored",
        },
    )
    assert response.status_code == 302
    assert response.location == target
    send.assert_called_once_with("recipient@example.com")
    page = client.get(target)
    assert "byla předána poštovnímu serveru" in page.text
    client.get(target)
    send.assert_called_once()


def test_repeated_post_does_not_send_same_form_twice(setup):
    client, send = setup
    values = {
        "email_token": token(client),
        "email": "recipient@example.com",
        "return_to": "team",
    }
    client.post("/patients/synthetic-1/email", data=values)
    page = client.post(
        "/patients/synthetic-1/email", data=values, follow_redirects=True
    )
    assert "neposíláme znovu" in page.text
    send.assert_called_once()


@pytest.mark.parametrize(
    "email",
    [
        "",
        "invalid",
        "first@example.com,second@example.com",
        "first@example.com\r\nBcc: second@example.com",
    ],
)
def test_invalid_recipient_does_not_send(setup, email):
    client, send = setup
    page = client.post(
        "/patients/synthetic-1/email",
        data={"email_token": token(client), "email": email, "action": "save_contact"},
        follow_redirects=True,
    )
    assert "Zadejte platnou" in page.text
    send.assert_not_called()


@pytest.mark.parametrize(
    "failure,expected",
    [
        (ValueError("SMTP config"), "není nastavené"),
        (smtplib.SMTPException("Synthetic failure"), "nepodařilo odeslat"),
    ],
)
def test_failure_does_not_claim_success_and_same_form_can_retry(
    setup, failure, expected
):
    client, send = setup
    values = {"email_token": token(client), "email": "recipient@example.com"}
    send.side_effect = failure
    page = client.post(
        "/patients/synthetic-1/email", data=values, follow_redirects=True
    )
    assert expected in page.text
    assert "byla předána" not in page.text
    send.side_effect = None
    page = client.post(
        "/patients/synthetic-1/email", data=values, follow_redirects=True
    )
    assert "byla předána" in page.text
    assert send.call_count == 2


def test_token_is_bound_to_patient_and_browser(setup):
    client, send = setup
    ticket = token(client)
    for browser, target in [
        (client, "synthetic-2"),
        (app.test_client(), "synthetic-1"),
    ]:
        response = browser.post(
            f"/patients/{target}/email",
            data={"email_token": ticket, "email": "recipient@example.com"},
        )
        assert response.status_code == 302
    for ticket in ("", "invalid"):
        client.post(
            "/patients/synthetic-1/email",
            data={"email_token": ticket, "email": "recipient@example.com"},
        )
    send.assert_not_called()


def test_unknown_patient_and_external_redirect_are_not_accepted(setup):
    client, send = setup
    values = {"email_token": token(client), "email": "recipient@example.com"}
    assert client.post("/patients/unknown/email", data=values).status_code == 404
    send.assert_not_called()
    response = client.post(
        "/patients/synthetic-1/email",
        data={**values, "return_to": "https://example.com"},
    )
    assert response.location == "/patients/synthetic-1/report"


def test_patient_without_checkins_can_still_be_contacted(setup, monkeypatch):
    client, _ = setup
    monkeypatch.setattr(report, "checkin_assessments", lambda _: [])
    page = client.get("/patients/synthetic-1/report")
    assert page.status_code == 200
    assert 'class="patient-email"' in page.text


def test_contact_is_saved_and_used_after_reload(setup):
    client, send = setup
    response = client.post(
        "/patients/synthetic-1/email",
        data={
            "email_token": token(client),
            "action": "save_contact",
            "email": "saved@example.com",
        },
        follow_redirects=True,
    )
    assert "saved@example.com" in response.text
    send.assert_not_called()
    client.post("/patients/synthetic-1/email", data={"email_token": token(client)})
    send.assert_called_once_with("saved@example.com")


def test_missing_contact_disables_sending(setup):
    client, send = setup
    with app.app_context():
        patient_mail.save_patient_email("synthetic-1", "")
    page = client.get("/patients/synthetic-1/report")
    assert "Není uveden" in page.text
    assert 'value="send"' not in page.text
    client.post(
        "/patients/synthetic-1/email",
        data={"email_token": token(client), "email": "forged@example.com"},
    )
    send.assert_not_called()
