import importlib
import smtplib
from unittest.mock import MagicMock

import pytest

mail = importlib.import_module("notifications.app")


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setitem(mail.app.config, "TESTING", True)
    for name, value in {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_SECURITY": "starttls",
        "SMTP_FROM": "sender@example.com",
        "SMTP_USERNAME": "synthetic-user",
        "SMTP_PASSWORD": "synthetic-password",
    }.items():
        monkeypatch.setenv(name, value)
    smtp = MagicMock()
    smtp.return_value.__enter__.return_value = smtp.return_value
    monkeypatch.setattr(mail.smtplib, "SMTP", smtp)
    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", smtp)
    client = mail.app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        token = session["csrf_token"]
    return client, smtp, token


def test_single_email_form_and_styles(setup):
    client, _, _ = setup
    page = client.get("/")
    assert page.status_code == 200
    assert b'name="email"' in page.data
    assert b'name="subject"' not in page.data
    assert b"<textarea" not in page.data
    assert b"/static/style.css" in page.data
    assert client.get("/static/style.css").status_code == 200


@pytest.mark.parametrize("security,port", [("starttls", "587"), ("ssl", "465")])
def test_submits_predefined_message_and_refresh_does_not_resend(
    setup, monkeypatch, security, port
):
    client, smtp, token = setup
    monkeypatch.setenv("SMTP_SECURITY", security)
    monkeypatch.setenv("SMTP_PORT", port)
    response = client.post(
        "/send",
        data={
            "email": "recipient@example.com",
            "csrf_token": token,
            "subject": "Ignored subject",
            "message": "Ignored body",
        },
        follow_redirects=True,
    )
    assert "Your notification has been sent." in response.text
    message = smtp.return_value.send_message.call_args.args[0]
    assert message["To"] == "recipient@example.com"
    assert message["From"] == "sender@example.com"
    assert message["Subject"] == mail.SUBJECT
    assert message.get_content() == mail.BODY
    assert smtp.call_args.kwargs["timeout"] == 15
    smtp.return_value.login.assert_called_once_with(
        "synthetic-user", "synthetic-password"
    )
    assert smtp.return_value.starttls.call_count == (security == "starttls")
    client.get("/")
    smtp.return_value.send_message.assert_called_once()


@pytest.mark.parametrize(
    "email",
    [
        "",
        "invalid",
        "a@example.com,b@example.com",
        "a@example.com\r\nBcc: b@example.com",
    ],
)
def test_invalid_recipient_never_connects(setup, email):
    client, smtp, token = setup
    response = client.post("/send", data={"email": email, "csrf_token": token})
    assert response.status_code == 400
    smtp.assert_not_called()


def test_missing_configuration_is_visible_without_sending(setup, monkeypatch):
    client, smtp, token = setup
    monkeypatch.delenv("SMTP_HOST")
    response = client.post(
        "/send", data={"email": "recipient@example.com", "csrf_token": token}
    )
    assert response.status_code == 503
    assert "not configured" in response.text
    smtp.assert_not_called()


def test_delivery_error_keeps_recipient_and_does_not_claim_success(setup):
    client, smtp, token = setup
    smtp.return_value.send_message.side_effect = smtplib.SMTPException(
        "Synthetic failure"
    )
    response = client.post(
        "/send", data={"email": "recipient@example.com", "csrf_token": token}
    )
    assert response.status_code == 502
    assert "could not be sent" in response.text
    assert 'value="recipient@example.com"' in response.text
    assert "has been sent" not in response.text


def test_missing_or_invalid_csrf_never_sends(setup):
    client, smtp, _ = setup
    for token in ("", "invalid", "ž"):
        assert (
            client.post(
                "/send", data={"email": "recipient@example.com", "csrf_token": token}
            ).status_code
            == 400
        )
    smtp.assert_not_called()
