"""Small patient views and follow-up tasks over the existing saved check-ins."""

from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from llm_intake.core import load_questions
from meddi.routing import checkin_time
from web.triage import checkin_assessments

PRAGUE = ZoneInfo("Europe/Prague")
MEASUREMENTS = {
    "teplota_c": ("Tělesná teplota", "°C"),
    "spo2_pct": ("Saturace kyslíku", "%"),
    "tk_sys": ("Systolický tlak", "mmHg"),
    "tk_dia": ("Diastolický tlak", "mmHg"),
    "vaha_kg": ("Hmotnost", "kg"),
    "tepova_frekvence": ("Tepová frekvence", "tepů/min"),
    "glykemie_mmol_l": ("Glykémie", "mmol/l"),
}
QUESTION_LABELS = {
    "pocit": "Celkový stav",
    "unava": "Únava",
    "prujem": "Potíže se stolicí",
    "nevolnost": "Příjem stravy a tekutin",
    "zvraceni": "Zvracení",
    "dusnost": "Dýchání",
    "nrs": "Bolest",
    "teplota": "Zvýšená teplota",
}


@lru_cache(maxsize=1)
def questions():
    return {f"{q.questionnaire_id}/{q.id}": q for q in load_questions()}


def at(checkin):
    return (
        datetime.fromisoformat(checkin["available_at"])
        if checkin.get("available_at")
        else checkin_time({"date": checkin["datum"], "time": checkin.get("cas")})
    )


def visible_checkins(patient, now):
    return sorted([c for c in patient.get("checkiny", []) if at(c) <= now], key=at)


def display_time(value):
    if not value:
        return "Čas není uveden"
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return parsed.astimezone(PRAGUE).strftime("%d. %m. %Y · %H:%M")


def answer_rows(checkin):
    for form in checkin.get("dotazniky", []):
        for answer in form.get("odpovedi", []):
            yield f"{form['dotaznik_id']}/{answer['otazka_id']}", answer


def controls_for(patient, now=None):
    """Keep a few explicit tasks; no inferred medical interval or episode engine."""
    if "portal_controls" in patient:
        return [
            deepcopy(c)
            for c in patient["portal_controls"]
            if now is None or datetime.fromisoformat(c["created_at"]) <= now
        ]
    history = patient.get("checkiny", [])
    if now is not None:
        history = [c for c in history if at(c) <= now]
    return new_controls(max(history, key=at)) if history else []


def new_controls(checkin):
    controls = []
    for topic, answer in answer_rows(checkin):
        if (
            topic in questions()
            and answer.get("barva") in {"zluta", "oranzova", "cervena"}
            and answer.get("odpoved") is not None
        ):
            q = questions()[topic]
            controls.append(
                {
                    "id": topic,
                    "kind": "question",
                    "label": QUESTION_LABELS.get(q.id, q.text),
                }
            )
            if len(controls) == 3:
                break
    for field, (label, _) in MEASUREMENTS.items():
        if ((checkin.get("vitalni_funkce") or {}).get(field) or {}).get(
            "hodnota"
        ) is not None:
            controls.append({"id": field, "kind": "measurement", "label": label})
            if sum(c["kind"] == "measurement" for c in controls) == 3:
                break
    return [
        {
            **c,
            "source_checkin_id": checkin["checkin_id"],
            "created_at": at(checkin).isoformat(),
            "completed_checkin_id": None,
        }
        for c in controls
    ]


def update_controls(patient, controls, checkin):
    """Completion means a saved new answer/value, never clinical resolution."""
    answers = {
        key for key, row in answer_rows(checkin) if row.get("odpoved") is not None
    }
    measurements = {
        key: datetime.fromisoformat(row["observed_at"])
        if row.get("observed_at")
        else at(checkin)
        for key, row in (checkin.get("vitalni_funkce") or {}).items()
        if row and row.get("hodnota") is not None
    }
    for control in controls:
        if (
            control["source_checkin_id"] != checkin["checkin_id"]
            and at(checkin) >= datetime.fromisoformat(control["created_at"])
            and control["id"]
            in (answers if control["kind"] == "question" else measurements)
            and (
                control["kind"] == "question"
                or measurements[control["id"]]
                >= datetime.fromisoformat(control["created_at"])
            )
        ):
            control["completed_checkin_id"] = checkin["checkin_id"]
    known = {c["id"] for c in controls}
    for candidate in new_controls(checkin):
        if candidate["id"] not in known and len(controls) < 6:
            controls.append(candidate)
            known.add(candidate["id"])
    patient["portal_controls"] = controls


def follow_up(control):
    if control["kind"] == "question":
        q = questions()[control["id"]]
        return {
            "id": control["id"],
            "question": q.text,
            "instruction": q.instruction,
            "options": q.patient_options(),
            "topic": control["id"],
        }
    label, unit = MEASUREMENTS[control["id"]]
    return {
        "id": control["id"],
        "question": f"Jaká je vaše aktuálně naměřená hodnota: {label.lower()}?",
        "instruction": f"Uveďte novou naměřenou hodnotu v {unit}. Můžete připsat i nové potíže.",
        "topic": None,
    }


def build_portal(patient, now):
    history = visible_checkins(patient, now)
    current = {**patient, "checkiny": history}
    assessments = checkin_assessments(current)
    controls = controls_for(current, now)
    rows = []
    for control in controls:
        observations = []
        for checkin in history:
            if control["kind"] == "question":
                answer = next(
                    (row for key, row in answer_rows(checkin) if key == control["id"]),
                    None,
                )
                value = answer.get("odpoved") if answer else None
                has_observation = answer is not None
                observed = at(checkin)
            else:
                measured = (checkin.get("vitalni_funkce") or {}).get(
                    control["id"]
                ) or {}
                value = measured.get("hodnota")
                has_observation = control["id"] in (checkin.get("vitalni_funkce") or {})
                if value is not None:
                    value = f"{value} {MEASUREMENTS[control['id']][1]}"
                observed = (
                    datetime.fromisoformat(measured["observed_at"])
                    if measured.get("observed_at")
                    else at(checkin)
                )
            if has_observation and observed <= now:
                observations.append((value, observed))
        observations.sort(key=lambda entry: entry[1])
        value, observed = observations[-1] if observations else (None, None)
        due = control.get("due_at")
        completed = control.get("completed_checkin_id") in {
            c["checkin_id"] for c in history
        }
        overdue = bool(due and datetime.fromisoformat(due) <= now and not completed)
        rows.append(
            {
                **control,
                "value": ", ".join(map(str, value))
                if isinstance(value, list)
                else value,
                "time": display_time(observed),
                "due": display_time(due) if due else None,
                "status": "K upřesnění"
                if observations and value is None
                else "Aktualizováno"
                if completed
                else "K doplnění"
                if overdue
                else "Ke sledování",
            }
        )
    latest = assessments[-1] if assessments else None
    return {
        "assessment": latest,
        "time": display_time(at(history[-1])) if history else None,
        "controls": rows,
        "history": [
            {
                "date": display_time(at(c)),
                "text": c.get("zprava_pacienta") or "Kontrola a měření",
            }
            for c in reversed(history[-3:])
        ],
        "profile": patient.get("demografie") or {},
        "diagnosis": (patient.get("diagnoza") or {}).get("diagnoza"),
    }
