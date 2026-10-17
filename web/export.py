import json
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

from llm_intake.core import DEFINITIONS
from meddi.validation import VITAL_FIELDS

COLORS = {"zelena": 1, "zluta": 2, "oranzova": 3, "cervena": 4}
VITAL_UNITS = {
    "teplota_c": "°C",
    "spo2_pct": "%",
    "tk_sys": "mmHg",
    "tk_dia": "mmHg",
    "glykemie_mmol_l": "mmol/l",
    "vaha_kg": "kg",
    "tepova_frekvence": "bpm",
}


def _measurements(assessment):
    """Project validated, selected inputs; never interpret the LLM packet again."""
    observations = (assessment or {}).get("triage_inputs", {}).get("observations", {})
    result = {}
    for raw, field in VITAL_FIELDS.items():
        reports = observations.get(field, [])
        if not reports:
            continue
        values = {report["value"] for report in reports}
        # Contradictory simultaneous reports remain in triage and the audit,
        # but must not become an invented single point in a chart or trend.
        source = reports[0]["source"]
        result[raw] = {
            "hodnota": next(iter(values)) if len(values) == 1 else None,
            "jednotka": VITAL_UNITS[raw],
            "zdroj": "zprava_kontaktu",
            "observed_at": source.get("observed_at"),
            "available_at": source.get("available_at"),
            "podklady": deepcopy(reports),
        }
    return result


def meddi_record(
    packet, completed_at: datetime, *, include_drafts=False, assessment=None
):
    if completed_at.utcoffset() is None:
        raise ValueError("Čas kontaktu musí obsahovat časové pásmo.")
    completed_at = completed_at.astimezone(ZoneInfo("Europe/Prague"))
    if assessment is not None and (
        assessment.get("patient_id") != packet["message"]["patient_id"]
        or assessment.get("checkin_id") != packet["message"]["id"]
        or assessment.get("intake") != packet
    ):
        raise ValueError("Hodnocení nepatří exportovanému kontaktu.")
    definitions = json.loads(DEFINITIONS.read_text(encoding="utf-8"))
    answers = {
        (item["question"]["questionnaire_id"], item["question"]["question_id"]): item
        for item in packet["question_answers"]
    }
    checkin_id = f"WEB-{packet['message']['id']}"
    forms = []
    for definition in definitions:
        rows, warnings, colors = [], [], []
        for question in definition["otazky"]:
            answer = answers.get((definition["id"], question["id"]))
            if answer is None:
                continue
            resolved = answer["confirmed"] or (
                include_drafts and answer["state"] == "needs_confirmation"
            )
            value = answer["value"] if resolved else None
            options = question.get("moznosti", [])
            indices = (
                [value]
                if question["typ"] == "jedna" and value is not None
                else value
                if question["typ"] == "vice" and value is not None
                else []
            )
            selected = [options[index] for index in indices]
            row_colors = [option["barva"] for option in selected if option.get("barva")]
            row_warnings = list(
                dict.fromkeys(
                    option["upozorneni"]
                    for option in selected
                    if option.get("upozorneni")
                )
            )
            color = max(row_colors, key=COLORS.get) if row_colors else None
            if color:
                colors.append(color)
            warnings.extend(item for item in row_warnings if item not in warnings)
            rows.append(
                {
                    "otazka_id": question["id"],
                    "otazka": question["text"],
                    "odpoved": selected[0]["text"]
                    if selected and question["typ"] == "jedna"
                    else [option["text"] for option in selected]
                    if value is not None and question["typ"] == "vice"
                    else value,
                    "odpoved_index": value
                    if question["typ"] in {"jedna", "vice"}
                    else None,
                    "barva": color,
                    "upozorneni": "\n".join(row_warnings) or None,
                }
            )
        if rows:
            forms.append(
                {
                    "vyplneni_id": f"{checkin_id}-{definition['id']}",
                    "dotaznik_id": definition["id"],
                    "dotaznik_nazev": definition["nazev"],
                    "odpovedi": rows,
                    "nejvyssi_barva": max(colors, key=COLORS.get) if colors else None,
                    "zobrazena_upozorneni": warnings,
                }
            )
    return {
        "patient_id": packet["message"]["patient_id"],
        "checkiny": [
            {
                "checkin_id": checkin_id,
                "patient_id": packet["message"]["patient_id"],
                "datum": completed_at.date().isoformat(),
                "cas": completed_at.strftime("%H:%M"),
                "available_at": completed_at.isoformat(),
                "den_sledovani": None,
                "cyklus": None,
                "den_cyklu": None,
                "stav": "vyplneno",
                "vyplnil": {
                    "patient": "pacient",
                    "caregiver": "pecujici",
                    "team": "tym",
                }.get(packet["message"].get("author"), "neznamy"),
                "dotazniky": forms,
                "vitalni_funkce": _measurements(assessment),
                "zprava_pacienta": packet["message"]["text"],
                "zdrojove_zpravy": deepcopy(packet["messages"]),
                "prilohy": [],
            }
        ],
    }
