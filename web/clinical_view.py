"""Source-linked doctor views over existing assessments, without LLM or triage."""

from datetime import datetime, time

from web.portal import (
    MEASUREMENTS,
    PRAGUE,
    QUESTION_LABELS,
    answer_rows,
    at,
    build_portal,
    display_time,
    visible_checkins,
)

COLORS = ("green", "yellow", "orange", "red")
EXTRA_SERIES = {
    "stools_above_baseline_24h": ("Stolice nad obvyklý počet / 24 h", ""),
    "pain_nrs": ("Bolest NRS", "/ 10"),
}
FIELD_NAMES = {
    "temperature_c": "teplota_c",
    "spo2_pct": "spo2_pct",
    "weight_kg": "vaha_kg",
    "systolic_bp": "tk_sys",
    "diastolic_bp": "tk_dia",
    "pulse_bpm": "tepova_frekvence",
    "glucose_mmol_l": "glykemie_mmol_l",
    **{name: name for name in EXTRA_SERIES},
}


def record_time(row):
    if row.get("available_at"):
        value = datetime.fromisoformat(row["available_at"])
        return value.replace(tzinfo=PRAGUE) if value.tzinfo is None else value
    if row.get("datum") or row.get("date"):
        day = row.get("datum") or row["date"]
        clock = row.get("cas") or row.get("time") or time.max.isoformat()
        return datetime.fromisoformat(f"{day}T{clock}").replace(tzinfo=PRAGUE)
    return None


def value_text(value):
    return f"{value:g}".replace(".", ",") if type(value) in {int, float} else str(value)


def checkin_excerpt(checkin, reasons):
    if checkin.get("zprava_pacienta"):
        return checkin["zprava_pacienta"]
    if checkin.get("stav") == "nevyplneno":
        return "Kontrola nebyla vyplněna."
    noteworthy = [
        (topic, answer)
        for topic, answer in answer_rows(checkin)
        if answer.get("barva") in {"zluta", "oranzova", "cervena"}
    ]
    if noteworthy:
        return "; ".join(
            f"{QUESTION_LABELS.get(topic.split('/')[-1], 'Odpověď')}: {answer.get('odpoved')}"
            for topic, answer in noteworthy[:2]
        )
    return reasons[0]["message"] if reasons else "Nová odpověď nebo měření"


def trend_cards(history, assessments, cutoff):
    series = {}

    def add(field, value, checkin, stamp):
        if type(value) not in {int, float} or stamp > cutoff:
            return
        series.setdefault(field, {})[checkin] = (stamp, value)

    for checkin in history:
        for field, measurement in (checkin.get("vitalni_funkce") or {}).items():
            if field not in MEASUREMENTS or not measurement:
                continue
            stamp = (
                datetime.fromisoformat(measurement["observed_at"])
                if measurement.get("observed_at")
                else at(checkin)
            )
            known = (
                datetime.fromisoformat(measurement["available_at"])
                if measurement.get("available_at")
                else at(checkin)
            )
            if known <= cutoff:
                add(field, measurement.get("hodnota"), checkin["checkin_id"], stamp)
    for assessment in assessments:
        stamp = record_time(assessment)
        if stamp is None or stamp > cutoff:
            continue
        for field, row in (
            (assessment.get("triage_inputs") or {}).get("observations") or {}
        ).items():
            name = FIELD_NAMES.get(field)
            if name:
                value = row.get("value") if isinstance(row, dict) else row
                add(name, value, assessment["checkin_id"], stamp)
    cards = []
    labels = {**MEASUREMENTS, **EXTRA_SERIES}
    for field, observations in series.items():
        points = sorted(
            [(stamp, value, source) for source, (stamp, value) in observations.items()]
        )[-6:]
        if len(points) < 2:
            continue
        values = [p[1] for p in points]
        lower, upper = min(values), max(values)
        span = upper - lower or 1
        svg = " ".join(
            f"{8 + i * 184 / (len(values) - 1):.1f},{52 - (v - lower) * 40 / span:.1f}"
            for i, v in enumerate(values)
        )
        delta = values[-1] - values[0]
        label, unit = labels[field]
        cards.append(
            {
                "id": field,
                "label": label,
                "unit": unit,
                "first": value_text(values[0]),
                "last": value_text(values[-1]),
                "delta": ("+" if delta > 0 else "") + value_text(delta),
                "changed": delta != 0,
                "points": svg,
                "start": display_time(points[0][0]),
                "end": display_time(points[-1][0]),
                "sources": [
                    {
                        "id": source,
                        "when": display_time(stamp),
                        "value": value_text(value),
                    }
                    for stamp, value, source in points
                ],
            }
        )
    # A range/worded answer remains text. Show its development without
    # inventing a stool count or CTCAE grade for the miniature graph.
    for qid in ("prujem", "dusnost", "unava"):
        answers = []
        for checkin in history:
            answer = next(
                (
                    a
                    for topic, a in answer_rows(checkin)
                    if topic == f"nezadouci_ucinky/{qid}"
                    and a.get("odpoved") is not None
                ),
                None,
            )
            if answer is not None:
                answers.append(
                    (at(checkin), str(answer["odpoved"]), checkin["checkin_id"])
                )
        points = answers[-4:]
        if len(points) >= 2:
            cards.append(
                {
                    "id": f"response:{qid}",
                    "label": QUESTION_LABELS[qid],
                    "unit": "",
                    "points": None,
                    "first": points[0][1],
                    "last": points[-1][1],
                    "delta": "",
                    "changed": points[0][1] != points[-1][1],
                    "start": display_time(points[0][0]),
                    "end": display_time(points[-1][0]),
                    "sources": [
                        {"id": source, "when": display_time(stamp), "value": value}
                        for stamp, value, source in points
                    ],
                }
            )
    order = list(EXTRA_SERIES) + [
        "vaha_kg",
        "spo2_pct",
        "teplota_c",
        "tk_sys",
        "tk_dia",
        "glykemie_mmol_l",
        "tepova_frekvence",
    ]
    cards.sort(
        key=lambda c: (
            not c["changed"],
            1 if c["id"].startswith("response:") else 0,
            order.index(c["id"]) if c["id"] in order else 0,
        )
    )
    return cards[:3]


def context_view(patient, cutoff, monitoring_day=None):
    treatment = patient.get("lecba") or {}
    cycles = [
        c
        for c in treatment.get("cykly", [])
        if c.get("datum_d1")
        and datetime.fromisoformat(c["datum_d1"]).date() <= cutoff.date()
    ]
    last_cycle = max(cycles, key=lambda c: c["datum_d1"]) if cycles else None
    drugs = []
    for row in patient.get("leky", []):
        if (
            row.get("od_data")
            and datetime.fromisoformat(row["od_data"]).date() >= cutoff.date()
        ):
            continue
        if (
            row.get("do_data")
            and datetime.fromisoformat(row["do_data"]).date() < cutoff.date()
        ):
            continue
        # Day-index-only validity cannot be resolved here without a matching
        # monitoring-day record; the view must not invent current medication.
        if row.get("od_dne") and (
            monitoring_day is None or row["od_dne"] >= monitoring_day
        ):
            continue
        if row.get("do_dne") and (
            monitoring_day is None or row["do_dne"] < monitoring_day
        ):
            continue
        drugs.append(row.get("lek", ""))
    labs = [
        r
        for r in patient.get("laboratore", [])
        if record_time(r) and record_time(r) <= cutoff
    ]
    latest_labs = {}
    for row in sorted(labs, key=record_time):
        latest_labs[row.get("kod") or row.get("test")] = row
    lab_rows = sorted(
        latest_labs.values(),
        key=lambda r: (not bool(r.get("priznak")), -record_time(r).timestamp()),
    )[:4]
    return {
        "regimen": treatment.get("rezim"),
        "treatment_drugs": treatment.get("leky", []),
        "medications": drugs,
        "comorbidities": patient.get("komorbidity", []),
        "cycle": last_cycle,
        "days_since_cycle": (
            cutoff.date() - datetime.fromisoformat(last_cycle["datum_d1"]).date()
        ).days
        if last_cycle
        else None,
        "labs": [
            {
                "name": r.get("test") or r.get("kod"),
                "value": value_text(r.get("hodnota")),
                "unit": r.get("jednotka", ""),
                "flag": r.get("priznak", ""),
                "date": r["datum"],
                "source": r.get("odber_id", "laboratore"),
            }
            for r in lab_rows
        ],
    }


def doctor_view(patient, assessments, now):
    if not assessments:
        return {
            "controls": [],
            "overdue_count": 0,
            "trends": [],
            "timeline": [],
            "context": {},
            "quote": None,
            "change": "Bez check-inů",
        }
    latest = assessments[-1]
    cutoff = record_time(latest) or now
    history = visible_checkins(patient, cutoff)
    controls = build_portal(patient, now, assessments=assessments)["controls"]
    previous = assessments[-2] if len(assessments) > 1 else None
    movement = (
        COLORS.index(latest["color"]) - COLORS.index(previous["color"])
        if previous
        else None
    )
    change = (
        "Vyšší naléhavost"
        if movement and movement > 0
        else "Nižší naléhavost"
        if movement and movement < 0
        else "Stejná naléhavost"
        if previous
        else "První hodnocení"
    )
    by_id = {a["checkin_id"]: a for a in assessments}
    timeline = []
    for checkin in history[-5:]:
        assessment = by_id.get(checkin["checkin_id"], {})
        reasons = assessment.get("reasons") or []
        timeline.append(
            {
                "at": at(checkin),
                "label": "Pacientská kontrola",
                "text": checkin_excerpt(checkin, reasons),
                "color": assessment.get("color", "unknown"),
                "source": checkin["checkin_id"],
                "author": checkin.get("vyplnil"),
            }
        )
    for event in patient.get("udalosti_tymu", []):
        stamp = record_time(event)
        if stamp is not None and stamp <= cutoff:
            timeline.append(
                {
                    "at": stamp,
                    "label": event.get("typ") or "Záznam týmu",
                    "text": event.get("text", ""),
                    "color": "team",
                    "source": "udalosti_tymu",
                    "author": event.get("autor"),
                }
            )
    team_events = [
        e
        for e in patient.get("demo_team_events", [])
        if record_time(e) and record_time(e) <= now
    ]
    for event in team_events:
        timeline.append(
            {
                "at": record_time(event),
                "label": "Plán kontroly · demo"
                if event["kind"] == "plan"
                else "Kontakt týmu · demo",
                "text": event["text"],
                "color": "team",
                "source": "demo_team_events",
                "author": "Tým",
            }
        )
    timeline = sorted(timeline, key=lambda row: row["at"], reverse=True)[:7]
    for row in timeline:
        row["when"] = display_time(row["at"])
    return {
        "controls": controls,
        "overdue_count": sum(c["overdue"] for c in controls),
        "trends": trend_cards(history, assessments, cutoff),
        "timeline": timeline,
        "context": context_view(
            patient, cutoff, history[-1].get("den_sledovani") if history else None
        ),
        "change": change,
        "quote": history[-1].get("zprava_pacienta") if history else None,
        "last_author": history[-1].get("vyplnil") if history else None,
        "as_of": display_time(cutoff),
        "age_label": "Dnes"
        if (now.date() - cutoff.astimezone(PRAGUE).date()).days == 0
        else f"Před {(now.date() - cutoff.astimezone(PRAGUE).date()).days} dny",
        "last_team_event": team_events[-1] if team_events else None,
        "conflicts": (latest.get("intake") or {}).get("conflicts")
        or latest.get("conflicts")
        or [],
    }
