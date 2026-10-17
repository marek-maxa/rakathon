"""Load treatment context and measured history available at a check-in.

No patient messages, narrative treatment notes, scenario names or reference
evaluations are interpreted. The organizer's cycle dates describe D1 treatment
(bundle README §5). Medication doses can contain future changes, so only drug
names and their explicit validity dates are used.
"""

import re
import unicodedata
from calendar import monthrange
from copy import deepcopy
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .form import prepare_checkin

# Name-to-class mapping only: thresholds and decisions live in triage.
# Sources and limitations are documented in docs/architecture.md.
DRUG_CLASSES = {
    "chemotherapy_within_6_weeks": r"doxorubicin|cyklofosfamid|cyclophosphamid|5-fu|fluorouracil|kapecitabin|capecitabin|irinotekan|irinotecan|oxaliplatin|cisplatin|karboplatin|carboplatin|etoposid|vinkristin|vincristin",
    "fluoropyrimidine_treatment": r"5-fu|fluorouracil|kapecitabin|capecitabin",
    "irinotecan_treatment": r"irinotekan|irinotecan",
    "immunotherapy": r"ipilimumab|nivolumab|atezolizumab",
    "antiangiogenic_treatment": r"sunitinib|bevacizumab",
    "cardiotoxic_treatment": r"doxorubicin|trastuzumab",
    "cisplatin_treatment": r"(?<![a-z])cisplatin",
    "anticoagulation": r"warfarin",
    "opioid_treatment": r"morfin|morphin",
    "insulin_treatment": r"inzulin|insulin",
}


def normalized(text):
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(c)
    )


def _local_instant(stamp):
    """Organizer dates are local; timestamped web inputs carry their offset."""
    return (
        datetime.fromisoformat(stamp)
        .astimezone(ZoneInfo("Europe/Prague"))
        .replace(tzinfo=None)
    )


def instant(item):
    if item.get("available_at"):
        return _local_instant(item["available_at"])
    return datetime.fromisoformat(f"{item['datum']}T{item.get('cas') or '23:59:59'}")


def build_triage_inputs(patient, checkin):
    """Return prepared form, treatment flags and structured observations.

    Unknown names do not prove absence of a treatment class. Missing chemo
    administration dates remain unknown. Date-only new medications are not
    assumed available earlier on their start day.
    """
    prepared = prepare_checkin(checkin)
    # Age is static patient context, needed before applying adult reference
    # ranges. Do not infer adulthood from the diagnosis or medication names.
    if "vek" in (patient.get("demografie") or {}):
        prepared["patient_age"] = patient["demografie"]["vek"]
        prepared["patient_age_source"] = "demografie.vek"
    # Without a current time, do not expose other records from that day.
    now = instant({**checkin, "cas": checkin.get("cas") or "00:00:00"})
    today = now.date()
    current_day = checkin.get("den_sledovani")
    history = sorted(
        (
            item
            for item in patient["checkiny"]
            if item["checkin_id"] != checkin["checkin_id"] and instant(item) < now
        ),
        key=instant,
    )
    context, sources, observations = {}, {}, {}

    def observe(field, value, source):
        observations[field] = {"value": value, "source": source}

    treatment = patient.get("lecba") or {}
    if normalized(treatment.get("zamer") or "") == "symptomaticka paliativni pece":
        context["palliative_care"] = True
        sources["palliative_care"] = {
            "field": "lecba.zamer",
            "value": treatment["zamer"],
        }
    drugs = [
        {"name": name, "source": "lecba.leky"} for name in treatment.get("leky", [])
    ]
    for drug in patient.get("leky", []):
        start, end = drug.get("od_data"), drug.get("do_data")
        start_day, end_day = drug.get("od_dne"), drug.get("do_dne")
        if start and date.fromisoformat(start) >= today:
            continue
        if end and date.fromisoformat(end) < today:
            continue
        if start_day and (current_day is None or start_day >= current_day):
            continue
        if end_day and (current_day is None or end_day < current_day):
            continue
        drugs.append(
            {
                "name": drug["lek"],
                "source": "leky.lek",
                "od_data": start,
                "do_data": end,
                "od_dne": start_day,
                "do_dne": end_day,
            }
        )
    cycles = [
        c
        for c in treatment.get("cykly", [])
        if c.get("datum_d1") and date.fromisoformat(c["datum_d1"]) <= today
    ]
    for field, pattern in DRUG_CLASSES.items():
        matched = [d for d in drugs if re.search(pattern, normalized(d["name"]))]
        context[field] = True if matched else None
        sources[field] = {"drugs": matched}
        if field == "chemotherapy_within_6_weeks" and matched:
            recent = [
                c
                for c in cycles
                if (today - date.fromisoformat(c["datum_d1"])).days <= 42
            ]
            context[field] = True if recent else None
            sources[field]["cycles"] = recent
    if "komorbidity" in patient:
        context["diabetes"] = (
            True
            if any("diabet" in normalized(c) for c in patient["komorbidity"])
            else None
        )
        sources["diabetes"] = {"field": "komorbidity", "value": patient["komorbidity"]}

    def measurement_time(item, field):
        raw = (item.get("vitalni_funkce") or {}).get(field) or {}
        stamp = raw.get("observed_at")
        return _local_instant(stamp) if stamp else instant(item)

    def measurement(item, field):
        raw = (item.get("vitalni_funkce") or {}).get(field) or {}
        known = raw.get("available_at")
        if (known and _local_instant(known) > now) or measurement_time(
            item, field
        ) > now:
            return None
        return raw.get("hodnota")

    available = history + [checkin]
    bp = sorted(
        [
            item
            for item in available
            if measurement(item, "tk_sys") is not None
            or measurement(item, "tk_dia") is not None
        ],
        key=lambda item: max(
            measurement_time(item, field)
            for field in ("tk_sys", "tk_dia")
            if measurement(item, field) is not None
        ),
    )[-3:]
    if bp and bp[-1]["checkin_id"] == checkin["checkin_id"]:
        count = sum(
            (measurement(item, "tk_sys") or 0) >= 140
            or (measurement(item, "tk_dia") or 0) >= 90
            for item in bp
        )
        observe(
            "elevated_bp_measurements",
            count,
            [
                {
                    "checkin_id": item["checkin_id"],
                    "measurements": item["vitalni_funkce"],
                }
                for item in bp
            ],
        )
    weight = measurement(checkin, "vaha_kg")
    if weight is not None:
        measured_at = measurement_time(checkin, "vaha_kg")
        prior = sorted(
            [
                item
                for item in history
                if measurement(item, "vaha_kg") is not None
                and timedelta(0)
                < measured_at - measurement_time(item, "vaha_kg")
                <= timedelta(days=3)
            ],
            key=lambda item: measurement_time(item, "vaha_kg"),
        )
        if prior:
            baseline = prior[0]
            observe(
                "weight_gain_3_days_kg",
                weight - measurement(baseline, "vaha_kg"),
                {
                    "baseline_checkin": baseline["checkin_id"],
                    "baseline": measurement(baseline, "vaha_kg"),
                    "current": weight,
                },
            )
        start = (patient.get("obdobi_sledovani") or {}).get("od")
        baseline = (patient.get("antropometrie") or {}).get("vaha_kg_vychozi")
        baseline_date = date.fromisoformat(start) if start else None
        measured_day = measured_at.date()
        year = measured_day.year - (measured_day.month == 1)
        month = (measured_day.month - 2) % 12 + 1
        month_start = date(
            year, month, min(measured_day.day, monthrange(year, month)[1])
        )
        candidates = [
            (
                measurement_time(item, "vaha_kg").date(),
                measurement(item, "vaha_kg"),
                {"checkin_id": item["checkin_id"]},
            )
            for item in history
            if measurement(item, "vaha_kg") is not None
            and month_start <= measurement_time(item, "vaha_kg").date() <= measured_day
            and measurement_time(item, "vaha_kg") < measured_at
        ]
        if baseline and baseline_date and month_start <= baseline_date <= measured_day:
            candidates.append(
                (baseline_date, baseline, {"field": "antropometrie.vaha_kg_vychozi"})
            )
        if candidates:
            measured_date, baseline, source = min(candidates, key=lambda item: item[0])
            observe(
                "weight_loss_month_pct",
                max(0, (baseline - weight) / baseline * 100),
                {
                    **source,
                    "date": measured_date.isoformat(),
                    "baseline": baseline,
                    "current": weight,
                },
            )
    for answer in prepared["answers"]:
        if (
            answer["questionnaire_id"] == "nezadouci_ucinky"
            and answer["question_id"] == "sobestacnost"
            and answer["option_indices"] is not None
        ):
            baseline = patient.get("ecog_vychozi")
            if baseline is not None:
                observe(
                    "functional_status_drop",
                    max(0, answer["option_indices"] - baseline),
                    {"field": "ecog_vychozi", "baseline": baseline, "answer": answer},
                )
    missed = []
    for item in reversed(available):
        if item.get("stav") == "vyplneno":
            break
        missed.append(item["checkin_id"])
    if checkin.get("stav") != "vyplneno":
        observe("consecutive_missed_checkins", len(missed), {"checkin_ids": missed})
    prepared["context_sources"] = deepcopy(sources)
    return prepared, context, deepcopy(observations)
