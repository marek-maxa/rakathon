from web.app import app, sessions


def test_entry_page_offers_patient_and_doctor_interfaces():
    response = app.test_client().get("/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'href="/patient"' in html
    assert 'href="/team"' in html
    assert "Pokračovat jako pacient" in html
    assert "Pokračovat jako lékař" in html
    assert "<textarea" not in html


def _mock_patients(monkeypatch):
    patients = {
        "ONC-001": {
            "patient_id": "ONC-001",
            "checkiny": [],
            "demografie": {"jmeno_fiktivni": "Jana K."},
        },
        "ONC-002": {
            "patient_id": "ONC-002",
            "checkiny": [],
            "demografie": {"jmeno_fiktivni": "Petr M."},
        },
    }
    monkeypatch.setattr("web.app.list_patient_ids", lambda: list(patients))
    monkeypatch.setattr("web.app.load_patient", patients.__getitem__)
    monkeypatch.setattr("web.app.load_working_patient", patients.__getitem__)


def test_patient_profile_is_selected_before_intake(monkeypatch):
    _mock_patients(monkeypatch)
    client = app.test_client()

    response = client.get("/patient")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Váš přístupový kód" in html
    assert "Jana K." not in html
    assert "Petr M." not in html
    assert "<select" not in html
    assert "<textarea" not in html

    response = client.post("/patient", data={"patient_id": "ONC-002"})
    assert response.status_code == 302

    response = client.get("/patient")
    html = response.get_data(as_text=True)
    assert "Úvodní otázka" in html
    assert "Profil: Petr M." in html
    assert "/patients/ONC-002/report" not in html
    assert 'href="/team"' not in html
    assert "PRO PACIENTY" in html
    assert "<textarea" in html

    with client.session_transaction() as flask_session:
        session_id = flask_session["id"]
    assert sessions[session_id]["patient_id"] == "ONC-002"
    assert sessions[session_id]["contact"] is None
    assert "Pokračovat jako lékař" in client.get("/").get_data(as_text=True)
    # Navigating between interfaces does not discard the selected profile.
    assert "Profil: Petr M." in client.get("/patient").get_data(as_text=True)
    assert sessions[session_id]["patient_id"] == "ONC-002"


def test_invalid_patient_profile_does_not_start_intake(monkeypatch):
    _mock_patients(monkeypatch)
    client = app.test_client()

    response = client.post("/patient", data={"patient_id": "ONC-999"})
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Demo kód není platný." in html
    assert "Váš přístupový kód" in html
    assert "<textarea" not in html
