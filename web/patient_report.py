from __future__ import annotations

from functools import lru_cache
from html import escape

import plotly.graph_objects as go
from flask import Blueprint, Response, abort, render_template
from plotly.offline import get_plotlyjs, get_plotlyjs_version

from meddi.common_types import Severity
from meddi.loader import list_patient_ids
from meddi.status import MeasurementStatus, build_patient_status
from web.patient_store import load_patient
from web.triage import checkin_assessments

patient_report = Blueprint(
    "patient_report",
    __name__,
    template_folder="templates",
)
PLOTLY_JS_VERSION = get_plotlyjs_version()
ACTION_LABELS = {
    "dalsi_sledovani": "Další sledování",
    "kontaktovat_tym": "Kontaktovat tým",
    "telekonzultace": "Telekonzultace",
    "neodkladna_pomoc": "Neodkladná pomoc",
}

SEVERITY_CLASSES = {
    Severity.GREEN: "severity-green",
    Severity.YELLOW: "severity-yellow",
    Severity.ORANGE: "severity-orange",
    Severity.RED: "severity-red",
}
SEVERITY_LABELS = {
    Severity.GREEN: "Zelená",
    Severity.YELLOW: "Žlutá",
    Severity.ORANGE: "Oranžová",
    Severity.RED: "Červená",
}
MEASUREMENT_LABELS = {
    "spo2_pct": "SpO₂ (%)",
    "tk_sys": "Systolický tlak (mmHg)",
    "tk_dia": "Diastolický tlak (mmHg)",
    "teplota_c": "Teplota (°C)",
    "tepova_frekvence": "Tepová frekvence (tepů/min)",
    "dechova_frekvence": "Dechová frekvence (dechů/min)",
    "vaha_kg": "Tělesná hmotnost (kg)",
    "puls": "Pulz (min⁻¹)",
    "dte": "Výška / Let (dte)",
    "glykemie_mmol_l": "Glykémie (mmol/l)",
}


def _severity_label(severity):
    if severity is None:
        return "Neurčeno"
    return SEVERITY_LABELS.get(severity, str(severity))


def _severity_class(severity):
    if severity is None:
        return "severity-unknown"
    return SEVERITY_CLASSES.get(severity, "severity-unknown")


def _measurement_source_label(source):
    if not source:
        return "Nezjištěno"
    mapping = {
        "pulzni_oxymetr": "Pulzní oxymetr",
        "domaci_tlakomer": "Domácí tlakoměr",
        "domaci_teplomer": "Domácí teploměr",
        "home_monitor": "Domácí přístroj",
    }
    return mapping.get(source, source)


def _measurement_severity(measurement_id: str, checkin_id: str, incidents):
    for incident in incidents:
        if (
            incident.measurement_id == measurement_id
            and incident.checkin_id == checkin_id
        ):
            return incident.severity
    return None


def _severity_counts(counts):
    if not counts:
        return "—"
    parts = []
    for severity in (Severity.GREEN, Severity.YELLOW, Severity.ORANGE, Severity.RED):
        count = counts.get(severity, 0)
        if count:
            parts.append(f"{_severity_label(severity)}: {count}")
    if not parts:
        return "—"
    return ", ".join(parts)


def _cycle_counts(counts):
    if not counts:
        return "—"
    parts = []
    for cycle in sorted(counts, key=lambda value: (value is None, value or 0)):
        parts.append(f"C{cycle}: {counts[cycle]}")
    return ", ".join(parts)


def _measurement_chart(measurement: MeasurementStatus, incidents) -> str:
    color_map = {
        Severity.GREEN: "#37b36b",
        Severity.YELLOW: "#f7b500",
        Severity.ORANGE: "#f97316",
        Severity.RED: "#dc2626",
        None: "#8ea2b6",
    }
    severity_labels = {
        Severity.GREEN: "Zelená",
        Severity.YELLOW: "Žlutá",
        Severity.ORANGE: "Oranžová",
        Severity.RED: "Červená",
        None: "Nezařazeno",
    }
    label = escape(
        MEASUREMENT_LABELS.get(measurement.measurement_id, measurement.measurement_id)
    )
    history = measurement.history
    x_values = list(range(len(history)))
    values = [point.value for point in history]
    point_severities = [
        _measurement_severity(measurement.measurement_id, point.checkin_id, incidents)
        for point in history
    ]
    customdata = [
        [
            escape(point.date),
            escape(point.checkin_id),
            escape("—" if point.cycle is None else f"C{point.cycle}"),
            escape(_measurement_source_label(point.source)),
        ]
        for point in history
    ]

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=values,
            mode="lines",
            line={"color": "#287888", "width": 2},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    for severity in (
        Severity.GREEN,
        Severity.YELLOW,
        Severity.ORANGE,
        Severity.RED,
        None,
    ):
        indexes = [
            index
            for index, point_severity in enumerate(point_severities)
            if point_severity == severity
        ]
        if not indexes:
            continue
        figure.add_trace(
            go.Scatter(
                x=[x_values[index] for index in indexes],
                y=[values[index] for index in indexes],
                customdata=[customdata[index] for index in indexes],
                mode="markers",
                name=severity_labels[severity],
                marker={
                    "color": color_map[severity],
                    "size": 8,
                    "line": {"color": "#ffffff", "width": 1},
                },
                hovertemplate=(
                    f"<b>{label}</b><br>"
                    "Hodnota: %{y}<br>"
                    "Datum: %{customdata[0]}<br>"
                    "Check-in: %{customdata[1]}<br>"
                    "Cyklus: %{customdata[2]}<br>"
                    "Zdroj: %{customdata[3]}<br>"
                    f"Stav: {severity_labels[severity]}<extra></extra>"
                ),
            )
        )

    minimum = min(values)
    maximum = max(values)
    padding = max((maximum - minimum) * 0.12, abs(minimum) * 0.03, 1)
    y_min = minimum - padding
    y_max = maximum + padding

    thresholds = {
        "spo2_pct": [
            (y_min, 90, "rgba(220, 38, 38, 0.12)", "Červené pásmo: <90 %"),
            (90, 92, "rgba(249, 115, 22, 0.13)", "Oranžové pásmo: 90–<92 %"),
        ],
        "tk_sys": [
            (y_min, 90, "rgba(220, 38, 38, 0.12)", "Červené pásmo: <90 mmHg"),
            (180, y_max, "rgba(220, 38, 38, 0.12)", "Červené pásmo: ≥180 mmHg"),
        ],
        "tk_dia": [
            (110, y_max, "rgba(220, 38, 38, 0.12)", "Červené pásmo: ≥110 mmHg"),
        ],
    }
    for lower, upper, fill, legend in thresholds.get(measurement.measurement_id, []):
        visible_lower = max(lower, y_min)
        visible_upper = min(upper, y_max)
        if visible_lower >= visible_upper:
            continue
        figure.add_hrect(
            y0=visible_lower,
            y1=visible_upper,
            fillcolor=fill,
            line_width=0,
            layer="below",
        )
        figure.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="lines",
                name=legend,
                line={"color": fill, "width": 10},
                hoverinfo="skip",
            )
        )

    count = len(history)
    tick_indexes = sorted({0, count // 2, count - 1})
    figure.update_layout(
        template="plotly_white",
        autosize=True,
        height=310,
        margin={"l": 52, "r": 12, "t": 12, "b": 75},
        hovermode="closest",
        dragmode="zoom",
        font={"family": "Inter, system-ui, sans-serif", "size": 10, "color": "#435466"},
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.28,
            "x": 0,
            "font": {"size": 9},
        },
        xaxis={
            "title": None,
            "tickmode": "array",
            "tickvals": tick_indexes,
            "ticktext": [escape(history[index].date) for index in tick_indexes],
            "range": [-0.5, max(count - 0.5, 0.5)],
            "showgrid": False,
            "zeroline": False,
            "fixedrange": False,
        },
        yaxis={
            "title": None,
            "range": [y_min, y_max],
            "nticks": 4,
            "tickformat": "~g",
            "gridcolor": "#e8edf2",
            "zeroline": False,
            "fixedrange": False,
        },
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
    )
    return figure.to_html(
        full_html=False,
        include_plotlyjs=False,
        default_width="100%",
        default_height="310px",
        config={
            "responsive": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        },
    )


@lru_cache(maxsize=1)
def _plotly_javascript() -> str:
    return get_plotlyjs()


@patient_report.route("/assets/plotly-<version>.min.js")
def plotly_js(version: str):
    if version != PLOTLY_JS_VERSION:
        abort(404)
    response = Response(_plotly_javascript(), mimetype="application/javascript")
    response.cache_control.public = True
    response.cache_control.max_age = 31_536_000
    response.cache_control.immutable = True
    return response


@patient_report.route("/patients/<patient_id>/report")
def report_patient(patient_id):
    if patient_id not in list_patient_ids():
        abort(404)
    patient = load_patient(patient_id)
    status = build_patient_status(patient)
    assessments = checkin_assessments(patient)
    charts = {
        measurement.measurement_id: _measurement_chart(
            measurement, status.measurement_incidents
        )
        for measurement in status.measurements
    }
    return render_template(
        "report.html",
        status=status,
        assessments=assessments,
        clinical_card=_clinical_card(patient, assessments),
        charts=charts,
        plotly_js_version=PLOTLY_JS_VERSION,
        severity_classes=SEVERITY_CLASSES,
        severity_labels=SEVERITY_LABELS,
        measurement_labels=MEASUREMENT_LABELS,
        severity_counts=_severity_counts,
        cycle_counts=_cycle_counts,
        measurement_severity=_measurement_severity,
        measurement_source_label=_measurement_source_label,
    )


def _clinical_card(patient, assessments):
    """A short view of the same latest assessment used by the detailed report."""
    if not assessments:
        return None
    latest = assessments[-1]
    reasons = sorted(
        latest.get("reasons", []),
        key=lambda item: ("green", "yellow", "orange", "red").index(item["color"]),
        reverse=True,
    )
    findings = list(dict.fromkeys(reason["message"] for reason in reasons))
    action = ACTION_LABELS.get(latest.get("doporuceny_krok"), "K posouzení týmem")
    return {
        "patient_id": patient["patient_id"],
        "name": (patient.get("demografie") or {}).get("jmeno_fiktivni")
        or patient["patient_id"],
        "assessment": latest,
        "action": action,
        "summary": f"{action}. "
        + (findings[0] if findings else "Bez doloženého důvodu ke zvýšení úrovně."),
        "findings": findings[:3],
        "needs_team": bool(latest.get("upozornit_tym")),
    }


@patient_report.route("/team")
def team_overview():
    cards, other_patients = [], []
    for patient_id in list_patient_ids():
        patient = load_patient(patient_id)
        card = _clinical_card(patient, checkin_assessments(patient))
        if card and card["needs_team"]:
            cards.append(card)
        else:
            other_patients.append({"patient_id": patient_id, "card": card})
    cards.sort(
        key=lambda card: (
            -("green", "yellow", "orange", "red").index(card["assessment"]["color"]),
            card["assessment"]["date"],
            card["assessment"].get("time") or "",
            card["patient_id"],
        )
    )
    return render_template("team.html", cards=cards, other_patients=other_patients)
