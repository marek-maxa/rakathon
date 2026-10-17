import json

from meddi.common_types import Severity
from meddi.status import (
    MeasurementIncident,
    MeasurementObservation,
    MeasurementStatus,
    PatientStatus,
)
from web.app import app
from web.patient_report import (
    MEASUREMENT_LABELS,
    PLOTLY_JS_VERSION,
    _measurement_chart,
)


def _assessment(checkin_id, color, *, review=False):
    return {
        "checkin_id": checkin_id,
        "color": color,
        "date": "2026-10-17",
        "time": "10:15",
        "rules_version": "synthetic-rules",
        "requires_review": review,
        "upozornit_tym": color != "green",
        "doporuceny_krok": "dalsi_sledovani" if color == "green" else "kontaktovat_tym",
        "doporuceny_kontakt": "Syntetický kontaktní pokyn",
        "reasons": [
            {
                "color": color,
                "message": f"Důvod {checkin_id}",
                "source": "Syntetické pravidlo §3",
                "provisional": review,
            }
        ],
    }


def test_team_overview_uses_latest_priority_and_keeps_incompleteness_separate(
    monkeypatch,
):
    patients = {
        key: {"patient_id": key, "demografie": {"jmeno_fiktivni": name}, "checkiny": []}
        for key, name in [
            ("green", "Zlepšený pacient"),
            ("yellow", "Žlutý pacient"),
            ("orange", "Oranžový pacient"),
            ("red", "<Červený pacient>"),
            ("empty", "Bez záznamu"),
        ]
    }
    assessments = {
        "green": [
            _assessment("old-red", "red"),
            _assessment("new-green", "green", review=True),
        ],
        "yellow": [_assessment("current-yellow", "yellow")],
        "orange": [_assessment("current-orange", "orange")],
        "red": [_assessment("current-red", "red", review=True)],
        "empty": [],
    }
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: list(patients))
    monkeypatch.setattr("web.patient_report.load_patient", patients.__getitem__)
    monkeypatch.setattr(
        "web.patient_report.checkin_assessments", lambda p: assessments[p["patient_id"]]
    )
    response = app.test_client().get("/team")
    html = response.get_data(as_text=True)
    requests = html.split('<section aria-labelledby="requests-title">')[1].split(
        "</section>"
    )[0]

    assert response.status_code == 200
    assert "K posouzení týmem (3)" in requests
    assert (
        requests.index("&lt;Červený pacient&gt;")
        < requests.index("Oranžový pacient")
        < requests.index("Žlutý pacient")
    )
    assert "Zlepšený pacient" not in requests
    assert "old-red" not in html
    assert "Zlepšený pacient" in html and "Bez check-inů" in html
    assert 'triage-red">Červená' in requests and "Posouzení je neúplné" in requests
    assert "Předání týmu: simulované" in requests
    assert "/patients/red/report#triage-title" in requests
    assert "PRO LÉKAŘE" in html
    assert 'href="/patient"' not in html
    assert 'href="/"' in html


def test_patient_card_and_detail_share_the_same_latest_assessment(monkeypatch):
    patient = {"patient_id": "synthetic", "checkiny": []}
    assessments = [
        _assessment("older", "red"),
        _assessment("latest", "yellow", review=True),
    ]
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: ["synthetic"])
    monkeypatch.setattr("web.patient_report.load_patient", lambda _: patient)
    monkeypatch.setattr("web.patient_report.checkin_assessments", lambda _: assessments)
    html = app.test_client().get("/patients/synthetic/report").get_data(as_text=True)
    card = html.split('<article class="clinical-card"')[1].split("</article>")[0]
    detail = html.split('<h3 id="triage-title">')[1].split("<details>")[0]

    assert "Důvod latest" in card and "Důvod latest" in detail
    assert "Důvod older" not in card
    assert "2026-10-17 10:15 · latest" in card
    assert "synthetic-rules" in card
    assert "Syntetický kontaktní pokyn" in card
    assert "Posouzení je neúplné" in card and "předběžné" in card
    assert "Syntetické pravidlo §3" in detail


def test_team_overview_with_no_patients_renders_empty_state(monkeypatch):
    monkeypatch.setattr("web.patient_report.list_patient_ids", list)
    response = app.test_client().get("/team")
    assert response.status_code == 200
    assert "nyní není požadavek pro tým" in response.get_data(as_text=True)


def test_report_endpoint_renders_patient_in_shared_flask_app(monkeypatch):
    patient_data = {"patient_id": "<ONC-001>", "checkiny": []}
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: ["ONC-001"])
    monkeypatch.setattr("web.patient_report.load_patient", lambda _: patient_data)

    client = app.test_client()
    response = client.get("/patients/ONC-001/report")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "<h1>Přehled stavu pacienta</h1>" in html
    assert "&lt;ONC-001&gt;" in html
    assert "Bez zaznamenaných měření." in html
    assert "patient_report.css" in html
    assert any(
        rule.rule == "/patients/<patient_id>/report"
        and rule.endpoint == "patient_report.report_patient"
        for rule in app.url_map.iter_rules()
    )


def test_report_endpoint_returns_404_for_unknown_patient(monkeypatch):
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: ["ONC-001"])
    client = app.test_client()

    response = client.get("/patients/ONC-999/report")

    assert response.status_code == 404


def test_report_renders_measurement_chart_and_warning_details(monkeypatch):
    history = (
        MeasurementObservation(
            checkin_id="CHECKIN-1",
            date="2026-10-01",
            cycle=1,
            value=89,
            source="pulzni_oxymetr",
        ),
        MeasurementObservation(
            checkin_id="CHECKIN-2",
            date="2026-10-02",
            cycle=1,
            value=91,
            source="pulzni_oxymetr",
        ),
    )
    measurement = MeasurementStatus(
        measurement_id="spo2_pct",
        count=2,
        minimum=89,
        maximum=91,
        average=90,
        last_observation=history[-1],
        history=history,
    )
    status = PatientStatus(
        patient_id="ONC-001",
        questionnaire_questions=(),
        measurements=(measurement,),
        measurement_incidents=(
            MeasurementIncident(
                checkin_id="CHECKIN-1",
                date="2026-10-01",
                cycle=1,
                measurement_id="spo2_pct",
                value="89 %",
                reason="SpO₂ pod 90 %",
                severity=Severity.RED,
            ),
        ),
    )
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: ["ONC-001"])
    monkeypatch.setattr(
        "web.patient_report.load_patient",
        lambda _: {"patient_id": "ONC-001", "checkiny": []},
    )
    monkeypatch.setattr(
        "web.patient_report.build_patient_status", lambda _, status=status: status
    )

    response = app.test_client().get("/patients/ONC-001/report")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'class="plotly-graph-div"' in html
    assert "Plotly.newPlot(" in html
    assert "SpO₂ (%)" in html
    assert html.count("/assets/plotly-") == 1
    assert "Varovné nálezy měření" in html
    assert "SpO₂ pod 90 %" in html
    assert "2026-10-01" in html
    assert html.index("Varovné nálezy měření") < html.index(
        "Varovné odpovědi v dotaznících"
    )
    assert html.index("Varovné odpovědi v dotaznících") < html.index(
        "Statistiky měření a průběh"
    )


def test_plotly_javascript_is_served_locally_with_immutable_cache():
    client = app.test_client()

    response = client.get(f"/assets/plotly-{PLOTLY_JS_VERSION}.min.js")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert response.cache_control.immutable
    assert b"Plotly" in response.data
    assert client.get("/assets/plotly-unexpected.min.js").status_code == 404


def test_measurement_ids_in_patient_data_have_readable_labels(monkeypatch):
    expected_labels = {
        "dechova_frekvence": "Dechová frekvence (dechů/min)",
        "glykemie_mmol_l": "Glykémie (mmol/l)",
        "teplota_c": "Teplota (°C)",
        "tepova_frekvence": "Tepová frekvence (tepů/min)",
        "tk_dia": "Diastolický tlak (mmHg)",
        "tk_sys": "Systolický tlak (mmHg)",
        "vaha_kg": "Tělesná hmotnost (kg)",
    }
    observation = MeasurementObservation(
        checkin_id="CHECKIN-1",
        date="2026-10-01",
        cycle=1,
        value=5.6,
        source=None,
    )
    monkeypatch.setattr("web.patient_report.list_patient_ids", lambda: ["ONC-001"])
    monkeypatch.setattr(
        "web.patient_report.load_patient",
        lambda _: {"patient_id": "ONC-001", "checkiny": []},
    )
    client = app.test_client()

    for measurement_id, label in expected_labels.items():
        assert MEASUREMENT_LABELS[measurement_id] == label
        measurement = MeasurementStatus(
            measurement_id=measurement_id,
            count=1,
            minimum=5.6,
            maximum=5.6,
            average=5.6,
            last_observation=observation,
            history=(observation,),
        )
        chart = _measurement_chart(measurement, ())
        status = PatientStatus(
            patient_id="ONC-001",
            questionnaire_questions=(),
            measurements=(measurement,),
            measurement_incidents=(),
        )
        monkeypatch.setattr(
            "web.patient_report.build_patient_status", lambda _, status=status: status
        )
        html = client.get("/patients/ONC-001/report").get_data(as_text=True)

        assert "Plotly.newPlot(" in chart
        assert measurement_id not in chart
        assert f"<h4>{label}</h4>" in html
        assert measurement_id not in html


def test_measurement_chart_includes_hover_details_and_explicit_threshold_zones():
    first = MeasurementObservation(
        checkin_id="CHECKIN-1",
        date="2026-09-01",
        cycle=1,
        value=89,
        source="pulzni_oxymetr",
    )
    last = MeasurementObservation(
        checkin_id="CHECKIN-2",
        date="2026-09-02",
        cycle=1,
        value=91,
        source="pulzni_oxymetr",
    )
    measurement = MeasurementStatus(
        measurement_id="spo2_pct",
        count=2,
        minimum=89,
        maximum=91,
        average=90,
        last_observation=last,
        history=(first, last),
    )

    chart = _measurement_chart(measurement, ())

    assert "Hodnota:" in chart
    assert "Datum:" in chart
    assert "Check-in:" in chart
    assert "Cyklus:" in chart
    assert json.dumps("Pulzní oxymetr", ensure_ascii=True)[1:-1] in chart
    red_label = json.dumps("Červené pásmo: <90 %", ensure_ascii=True)[1:-1].replace(
        "<", r"\u003c"
    )
    orange_label = json.dumps("Oranžové pásmo: 90–<92 %", ensure_ascii=True)[
        1:-1
    ].replace("<", r"\u003c")
    assert red_label in chart
    assert orange_label in chart
