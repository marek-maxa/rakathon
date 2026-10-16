import json
from datetime import datetime

from llm_intake.core import DEFINITIONS

COLORS = {"zelena": 1, "zluta": 2, "oranzova": 3, "cervena": 4}


def meddi_record(packet, completed_at: datetime, *, include_drafts=False):
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
                "den_sledovani": None,
                "cyklus": None,
                "den_cyklu": None,
                "stav": "vyplneno",
                "vyplnil": "pacient",
                "dotazniky": forms,
                "vitalni_funkce": {},
                "zprava_pacienta": "\n".join(
                    message["text"] for message in packet["messages"]
                ),
                "prilohy": [],
            }
        ],
    }
