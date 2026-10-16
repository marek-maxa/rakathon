"""Validation of normalized numeric inputs; no clinical severity thresholds."""

import math

# These are input domains, not boundaries for assigning a triage color.
DOMAINS = {
    "temperature_c": (0, None, False),
    "spo2_pct": (0, 100, True),
    "baseline_spo2_pct": (0, 100, True),
    "overall_feeling": (1, 5, True),
    "pain_nrs": (0, 10, True),
    "systolic_bp": (0, None, False),
    "diastolic_bp": (0, None, False),
    "weight_kg": (0, None, False),
}
UNITS = {
    "temperature_c": {None, "degC", "C", "°C", "celsius"},
    "spo2_pct": {None, "%", "percent"},
    "baseline_spo2_pct": {None, "%", "percent"},
    "systolic_bp": {None, "mmHg"},
    "diastolic_bp": {None, "mmHg"},
    "glucose_mmol_l": {None, "mmol/l", "mmol/L", "mmol_l"},
    "weight_kg": {None, "kg"},
    "pain_nrs": {None, "NRS_0_10"},
}
VITAL_FIELDS = {
    "teplota_c": "temperature_c",
    "spo2_pct": "spo2_pct",
    "tk_sys": "systolic_bp",
    "tk_dia": "diastolic_bp",
    "glykemie_mmol_l": "glucose_mmol_l",
    "vaha_kg": "weight_kg",
}


def number(field, value, unit=None):
    """Require a finite number in its documented domain, without unit guessing."""
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    lower, upper, inclusive = DOMAINS.get(field, (0, None, True))
    if field == "weight_gain_3_days_kg":
        lower = None
    if (
        lower is not None and (value < lower or (value == lower and not inclusive))
    ) or (upper is not None and value > upper):
        raise ValueError(f"{field} is outside its input domain")
    if field in {"pain_nrs", "overall_feeling"} and type(value) is not int:
        raise ValueError(f"{field} must be an integer")
    if field in UNITS and unit not in UNITS[field]:
        raise ValueError(f"{field} has an unsupported unit")
    return value


def prepared_inputs(prepared):
    """Validate known measurements and numeric answers before any rule runs."""
    for raw, measurement in (prepared.get("vital_signs") or {}).items():
        if raw not in VITAL_FIELDS or measurement is None:
            continue
        if not isinstance(measurement, dict):
            raise TypeError(f"Measurement {raw} must be a record")
        number(
            VITAL_FIELDS[raw],
            measurement.get("hodnota"),
            measurement.get("jednotka", measurement.get("unit")),
        )
    for answer in prepared.get("answers", []):
        value = answer.get("value")
        if value is None:
            continue
        if (answer.get("questionnaire_id"), answer.get("question_id")) == (
            "bolest_analgeticka_terapie",
            "nrs",
        ):
            number("pain_nrs", value)
        elif answer.get("type") == "skala_1_10":
            if type(value) is not int or not 1 <= value <= 10:
                raise ValueError("Scale answer must be an integer from 1 to 10")
        elif answer.get("type") == "cislo":
            number("numeric_answer", value)
