"""Exercise existing web flows through real Basic Auth using synthetic credentials."""

from base64 import b64encode

import pytest


@pytest.fixture(autouse=True)
def authenticated_web_clients(request, monkeypatch):
    if request.node.path.name not in {
        "test_web.py",
        "test_web_triage.py",
        "test_survey_recovery.py",
        "test_patient_report.py",
        "test_patient_mail.py",
        "test_web_events.py",
        "test_web_measurements.py",
    }:
        return
    from web.app import app

    monkeypatch.setitem(app.config, "BASIC_AUTH_USERNAME", "demo")
    monkeypatch.setitem(app.config, "BASIC_AUTH_PASSWORD", "synthetic-password")
    original = app.test_client
    authorization = "Basic " + b64encode(b"demo:synthetic-password").decode("ascii")

    def authenticated_client(*args, **kwargs):
        client = original(*args, **kwargs)
        client.environ_base["HTTP_AUTHORIZATION"] = authorization
        return client

    monkeypatch.setattr(app, "test_client", authenticated_client)
