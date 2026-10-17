from web.app import app, sessions


def _mock_patients(monkeypatch):
    patients = {
        "ONC-001": {"demografie": {"jmeno_fiktivni": "Jana K."}},
        "ONC-002": {"demografie": {"jmeno_fiktivni": "Petr M."}},
    }
    monkeypatch.setattr("web.app.list_patient_ids", lambda: list(patients))
    monkeypatch.setattr("web.app.load_patient", patients.__getitem__)


def test_patient_profile_is_selected_before_intake(monkeypatch):
    _mock_patients(monkeypatch)
    client = app.test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Kdo jste?" in html
    assert "Jana K. (ONC-001)" in html
    assert "Petr M. (ONC-002)" in html
    assert "<textarea" not in html

    response = client.post("/", data={"patient_id": "ONC-002"})
    assert response.status_code == 302

    response = client.get("/")
    html = response.get_data(as_text=True)
    assert "Úvodní otázka" in html
    assert "Profil: Petr M." in html
    assert "/patients/ONC-002/report" in html
    assert "<textarea" in html

    with client.session_transaction() as flask_session:
        session_id = flask_session["id"]
    assert sessions[session_id]["patient_id"] == "ONC-002"
    assert sessions[session_id]["contact"] is None


def test_invalid_patient_profile_does_not_start_intake(monkeypatch):
    _mock_patients(monkeypatch)
    client = app.test_client()

    response = client.post("/", data={"patient_id": "ONC-999"})
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Vyberte platný profil pacienta." in html
    assert "Kdo jste?" in html
    assert "<textarea" not in html
