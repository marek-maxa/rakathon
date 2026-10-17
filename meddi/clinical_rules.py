"""Deterministic color conditions from pravidla_triaze.md, sections 3–5.

Only explicit observations, measurements, and selected answers enter rules.
True/False/None represent a proven condition, its rejection, or missing data.
"""

from copy import deepcopy
from dataclasses import dataclass

from .common_types import Severity
from .validation import number

RULES_SOURCE = "rakathon_meddi_onco_data/docs/pravidla_triaze.md"
CONTEXT_FLAGS = {
    "chemotherapy_within_6_weeks",
    "fluoropyrimidine_treatment",
    "irinotecan_treatment",
    "cardiotoxic_treatment",
    "cisplatin_treatment",
    "palliative_care",
    "anticoagulation",
    "antiangiogenic_treatment",
    "diabetes",
    "immunotherapy",
    "insulin_treatment",
    "brain_tumor",
    "opioid_treatment",
}
OBSERVATION_FLAGS = {
    "grade_2_symptom_without_warning_signs",
    "loperamide_scheme_followed",
    "suicidal_thoughts",
    "suicide_plan_intent_or_means",
    "high_blood_pressure",
    "chills",
    "breathlessness_at_rest",
    "sudden_breathlessness",
    "palpitations",
    "new_chest_pain",
    "orthopnea",
    "diarrhea",
    "diarrhea_current",
    "diarrhea_with_blood",
    "loperamide_ineffective",
    "unilateral_calf_swelling",
    "calf_pain",
    "hopelessness",
    "worsening_despite_planned_examination",
    "paronychia_limits_activity",
    "hand_foot_limits_activity",
    "neuropathy_persistent_between_cycles",
    "neuropathy_limits_fine_motor_skills",
    "new_tinnitus",
    "edema_grade_2",
    "progressive_intake_decline",
    "moderate_sadness",
    "moderate_anxiety",
    "caregiver_exhaustion",
    "medication_nonadherence",
    "unfavorable_trend",
    "new_cough",
    "new_diarrhea",
    "new_breathlessness",
    "new_fatigue",
    "new_thirst",
    "nausea_reduced_intake",
    "mouth_sores_limit_eating",
    "reduced_intake",
    "severe_headache",
    "vision_disturbance",
    "speech_disturbance",
    "chest_pain",
    "hypotension",
    "orthostatic_dizziness",
    "blood_in_stool",
    "blood_in_vomit",
    "black_stool",
    "blood_in_urine",
    "head_injury",
    "bleeding_or_new_bruises",
    "bleeding",
    "new_bruises",
    "fainting",
    "cannot_keep_fluids",
    "dehydration_signs",
    "new_only_liquid_food",
    "pain_uncontrolled",
    "low_urine",
    "drinking_maintained",
    "confusion",
    "consciousness_disturbance",
    "difficulty_waking",
    "seizure",
    "new_limb_weakness",
    "morning_headache",
    "vomiting",
    "abdominal_pain",
    "rapid_breathing",
    "polydipsia",
    "frequent_urination",
    "weight_loss",
    "new_marked_drowsiness",
    "unresponsiveness",
    "slow_breathing",
    "no_gas",
    "no_stool",
    "colicky_abdominal_pain",
}
OBSERVATION_NUMBERS = {
    "temperature_c",
    "stools_above_baseline_24h",
    "baseline_spo2_pct",
    "spo2_pct",
    "constipation_days",
    "weight_gain_3_days_kg",
    "weight_loss_month_pct",
    "functional_status_drop",
    "consecutive_missed_checkins",
    "hours_without_diarrhea",
    "systolic_bp",
    "diastolic_bp",
    "glucose_mmol_l",
    "elevated_bp_measurements",
    "nosebleed_minutes",
    "hours_without_urine",
    "vomiting_episodes_24h",
}
HANDLED_VITALS = {"tk_sys", "tk_dia", "glykemie_mmol_l", "vaha_kg"}
HANDLED_QUESTIONS = {
    ("nezadouci_ucinky", name)
    for name in (
        "nevolnost",
        "nechutenstvi",
        "afty",
        "krvaceni",
        "bol_bricho",
        "prujem",
    )
}


@dataclass
class Condition:
    value: bool | None
    missing: list[str]
    evidence: list[dict]


def all_of(*conditions: Condition) -> Condition:
    """A known false term rejects AND even if another term is unknown."""
    rejected = [condition for condition in conditions if condition.value is False]
    selected = rejected or list(conditions)
    value = (
        False
        if rejected
        else None
        if any(c.value is None for c in conditions)
        else True
    )
    return Condition(
        value,
        sorted({field for c in selected for field in c.missing}),
        [item for c in selected for item in c.evidence],
    )


def any_of(*conditions: Condition) -> Condition:
    """A known true term proves OR without needing the remaining terms."""
    proven = [condition for condition in conditions if condition.value is True]
    selected = proven or list(conditions)
    value = (
        True if proven else None if any(c.value is None for c in conditions) else False
    )
    return Condition(
        value,
        sorted({field for c in selected for field in c.missing}),
        [item for c in selected for item in c.evidence],
    )


def evaluate_clinical_rules(prepared: dict, context: dict, observations: dict) -> dict:
    """Evaluate the requested rule groups; return reasons and exact missing inputs.

    Observations may be bare values or {value: ..., source: ...} records.
    All supplied observations must be available at the current check-in time.
    No raw text parsing, medication classification, or history loading occurs.
    """
    facts = {}
    issues = []

    def put(field, value, evidence):
        if value is None:
            return
        if field in OBSERVATION_NUMBERS:
            number(field, value)
        facts.setdefault(field, []).append((value, evidence))

    for field in CONTEXT_FLAGS:
        value = context.get(field)
        if value is not None and type(value) is not bool:
            raise ValueError(f"Context field {field} must be bool or None")
        put(
            field,
            value,
            {
                "kind": "context",
                "field": field,
                "value": value,
                "source": deepcopy(prepared.get("context_sources", {}).get(field)),
            },
        )
    if context.get("suicide_plan_intent_or_means") is not None:
        put(
            "suicide_plan_intent_or_means",
            context["suicide_plan_intent_or_means"],
            {
                "kind": "context",
                "field": "suicide_plan_intent_or_means",
                "value": context["suicide_plan_intent_or_means"],
            },
        )
    for field in OBSERVATION_FLAGS | OBSERVATION_NUMBERS:
        supplied_values = observations.get(field)
        # A list of source records preserves contradictory CURRENT reports.
        # The adapter chooses the episode/time; predicates keep every value.
        entries = (
            supplied_values if isinstance(supplied_values, list) else [supplied_values]
        )
        for supplied in entries:
            if isinstance(supplied_values, list) and not isinstance(supplied, dict):
                raise TypeError("Multiple observations require source records")
            value = supplied.get("value") if isinstance(supplied, dict) else supplied
            if (
                field in OBSERVATION_FLAGS
                and value is not None
                and type(value) is not bool
            ):
                raise ValueError(f"Observation {field} must be bool or None")
            if field in OBSERVATION_NUMBERS:
                number(
                    field,
                    value,
                    supplied.get("unit") if isinstance(supplied, dict) else None,
                )
            evidence = {"kind": "observation", "field": field, "value": value}
            if isinstance(supplied, dict) and "source" in supplied:
                evidence["source"] = deepcopy(supplied["source"])
            put(field, value, evidence)
            if field == "vomiting_episodes_24h" and value is not None:
                put("vomiting", value > 0, evidence)
                put("vomiting_3_to_5", 3 <= value <= 5, evidence)
                put("vomiting_over_5", value > 5, evidence)
            if field == "stools_above_baseline_24h" and value is not None:
                put("diarrhea", value > 0, evidence)
                put("diarrhea_4_to_6", 4 <= value <= 6, evidence)
                put("diarrhea_up_to_3", 0 < value <= 3, evidence)
                put("diarrhea_at_least_7", value >= 7, evidence)

    for raw_field, field in (
        ("tk_sys", "systolic_bp"),
        ("tk_dia", "diastolic_bp"),
        ("glykemie_mmol_l", "glucose_mmol_l"),
        ("spo2_pct", "spo2_pct"),
    ):
        measurement = (prepared.get("vital_signs") or {}).get(raw_field)
        if measurement:
            put(
                field,
                measurement.get("hodnota"),
                {"kind": "vital_sign", "field": raw_field, **deepcopy(measurement)},
            )

    for answer in prepared["answers"]:
        if answer["questionnaire_id"] != "nezadouci_ucinky":
            continue
        name, index = answer["question_id"], answer["option_indices"]
        if index is None:
            continue
        evidence = {"kind": "answer", **deepcopy(answer)}
        if name == "nevolnost":
            put("nausea_reduced_intake", index >= 1, evidence)
            put("reduced_intake", index >= 1, evidence)
        elif name == "nechutenstvi":
            put("reduced_intake", index >= 1, evidence)
        elif name == "afty":
            put("mouth_sores_limit_eating", index >= 1, evidence)
            put("reduced_intake", index >= 1, evidence)
        elif name == "krvaceni":
            # Composite question: yes can mean bleeding OR bruising.
            put("bleeding_or_new_bruises", index == 1, evidence)
        elif name == "bol_bricho":
            put("abdominal_pain", True, evidence)
        elif name == "bol_hrud":
            # Both options report pain; only the second reports NEW pain.
            put("chest_pain", True, evidence)
        elif name == "prujem":
            put("diarrhea", True, evidence)
            if index in (0, 1, 2):
                put("diarrhea_4_to_6", index == 1, evidence)
                put("diarrhea_up_to_3", index == 0, evidence)
                put("diarrhea_at_least_7", index == 2, evidence)
        elif name == "zvraceni":
            put("vomiting", True, evidence)
            # Preserve a range as a predicate, never invent an exact count.
            if index in (0, 1, 2):
                put("vomiting_3_to_5", index == 1, evidence)
                put("vomiting_over_5", index == 2, evidence)

    for field, entries in facts.items():
        if len({value for value, _ in entries}) > 1:
            issues.append(
                {
                    "code": "conflicting_observation",
                    "message": f"Rozdílné údaje pro {field}; použita horší doložená varianta.",
                    "evidence": [e for _, e in entries],
                }
            )

    def test(field, predicate=lambda value: value):
        entries = facts.get(field, [])
        if not entries:
            if field == "spo2_drop":
                return Condition(
                    None,
                    [
                        name
                        for name in ("baseline_spo2_pct", "spo2_pct")
                        if not facts.get(name)
                    ],
                    [],
                )
            missing = (
                "stools_above_baseline_24h"
                if field.startswith("diarrhea_")
                and field
                in ("diarrhea_4_to_6", "diarrhea_up_to_3", "diarrhea_at_least_7")
                else "vomiting_episodes_24h"
                if field in ("vomiting_3_to_5", "vomiting_over_5")
                else field
            )
            return Condition(None, [missing], [])
        matches = [e for value, e in entries if predicate(value)]
        return Condition(bool(matches), [], matches or [e for _, e in entries])

    def high_bp(systolic, diastolic):
        # Conservative interpretation of the protocol's paired BP thresholds:
        # crossing either component is sufficient. See architecture.md.
        return any_of(
            test("systolic_bp", lambda v: v >= systolic),
            test("diastolic_bp", lambda v: v >= diastolic),
        )

    vomiting = test("vomiting")
    vomiting_3_to_5 = test("vomiting_3_to_5")
    bleeding = any_of(
        *(
            test(field)
            for field in (
                "bleeding_or_new_bruises",
                "bleeding",
                "new_bruises",
                "blood_in_stool",
                "blood_in_vomit",
                "black_stool",
                "blood_in_urine",
            )
        ),
        test("nosebleed_minutes", lambda v: v > 0),
    )
    dehydration = any_of(
        test("dehydration_signs"),
        test("low_urine"),
        test("orthostatic_dizziness"),
        test("hours_without_urine", lambda v: v > 10),
    )
    hypertension_warnings = any_of(
        *(
            test(field)
            for field in (
                "severe_headache",
                "vision_disturbance",
                "speech_disturbance",
                "chest_pain",
            )
        )
    )
    scores, reasons, skipped = {}, [], []

    def rule(identifier, severity, message, section, condition):
        # A reported diarrhea episode during irinotecan treatment does not prove
        # twelve symptom-free hours. Keep the rule's yellow level provisionally
        # until timing is supplied; missing unrelated symptoms cannot trigger it.
        uncertain_diarrhea_timing = (
            identifier == "irinotecan_diarrhea_not_resolved"
            and condition.value is None
            and test("irinotecan_treatment").value is True
            and test("diarrhea").value is True
            and not facts.get("hours_without_diarrhea")
            and set(condition.missing) <= {"diarrhea_current", "hours_without_diarrhea"}
        )
        if uncertain_diarrhea_timing:
            condition.evidence.extend(test("diarrhea").evidence)
        # Only established symptoms with missing treatment/risk context qualify.
        # Unknown symptoms or a known false AND term must not create an alarm.
        provisional = uncertain_diarrhea_timing or (
            condition.value is None
            and bool(condition.missing)
            and set(condition.missing)
            <= CONTEXT_FLAGS | {"suicide_plan_intent_or_means"}
            and any(item["kind"] != "context" for item in condition.evidence)
        )
        scores[identifier] = (
            None
            if condition.value is None and not provisional
            else severity
            if condition.value or provisional
            else Severity.GREEN
        )
        if condition.value is None:
            skipped.append(
                {
                    "rule_id": identifier,
                    "missing_fields": condition.missing,
                    "evidence": condition.evidence,
                }
            )
        if condition.value or provisional:
            reasons.append(
                {
                    "rule_id": identifier,
                    "color": severity.name.lower(),
                    "message": (
                        f"Nelze vyloučit závažnější variantu: {message} "
                        f"Ověřte: {', '.join(condition.missing)}."
                        if provisional
                        else message
                    ),
                    "source": f"{RULES_SOURCE}, {section}",
                    "evidence": condition.evidence,
                    "provisional": provisional,
                    "uncertainty_source": f"{RULES_SOURCE}, §6.4"
                    if provisional
                    else None,
                }
            )

    rule(
        "grade_two_symptom",
        Severity.YELLOW,
        "Je doložen příznak druhého stupně bez varovných příznaků.",
        "§4 / Příznak 2. stupně",
        test("grade_2_symptom_without_warning_signs"),
    )
    rule(
        "nausea_reduced_intake",
        Severity.YELLOW,
        "Nevolnost omezuje příjem jídla.",
        "§4 / Příznak 2. stupně",
        test("nausea_reduced_intake"),
    )
    rule(
        "mouth_sores_limit_eating",
        Severity.YELLOW,
        "Afty omezují příjem jídla.",
        "§4 / Příznak 2. stupně",
        test("mouth_sores_limit_eating"),
    )
    rule(
        "severe_hypertension",
        Severity.RED,
        "Tlak dosahuje alespoň 180 systolicky nebo 110 diastolicky.",
        "§3 / Červená / Tlak",
        high_bp(180, 110),
    )
    rule(
        "hypertension_with_warning_signs",
        Severity.RED,
        "Zvýšený tlak je doprovázen varovným příznakem.",
        "§3 / Červená / Tlak",
        all_of(test("high_blood_pressure"), hypertension_warnings),
    )
    rule(
        "antiangiogenic_hypertension",
        Severity.ORANGE,
        "Tlak dosahuje alespoň 160 systolicky nebo 100 diastolicky při antiangiogenní léčbě.",
        "§3 / Oranžová / Tlak",
        all_of(high_bp(160, 100), test("antiangiogenic_treatment")),
    )
    rule(
        "repeated_hypertension",
        Severity.YELLOW,
        "Nejméně tři měření tlaku byla zvýšená alespoň na 140/90.",
        "§4 / Tlak",
        test("elevated_bp_measurements", lambda v: v >= 3),
    )
    rule(
        "orthostatic_hypotension",
        Severity.YELLOW,
        "Hypotenze je doprovázena závratí po vstávání.",
        "§4 / Tlak",
        all_of(
            any_of(test("hypotension"), test("systolic_bp", lambda v: v < 90)),
            test("orthostatic_dizziness"),
        ),
    )
    rule(
        "critical_bleeding",
        Severity.RED,
        "Je doložena krev ve stolici, zvratcích či moči nebo černá stolice.",
        "§3 / Červená / Krvácení",
        any_of(
            *(
                test(field)
                for field in (
                    "blood_in_stool",
                    "blood_in_vomit",
                    "blood_in_urine",
                    "black_stool",
                )
            )
        ),
    )
    rule(
        "prolonged_nosebleed",
        Severity.RED,
        "Krvácení z nosu trvá déle než 20 minut.",
        "§3 / Červená / Krvácení",
        test("nosebleed_minutes", lambda v: v > 20),
    )
    rule(
        "head_injury_on_anticoagulation",
        Severity.RED,
        "Úraz hlavy při antikoagulaci.",
        "§3 / Červená / Krvácení",
        all_of(test("head_injury"), test("anticoagulation")),
    )
    rule(
        "bleeding_on_anticoagulation",
        Severity.ORANGE,
        "Krvácení nebo nové modřiny při antikoagulaci.",
        "§3 / Oranžová / Krvácení",
        all_of(bleeding, test("anticoagulation")),
    )
    rule(
        "anuria",
        Severity.RED,
        "Pacient nemočil déle než 10 hodin.",
        "§3 / Červená / Dehydratace / oběh",
        test("hours_without_urine", lambda v: v > 10),
    )
    rule(
        "fainting",
        Severity.RED,
        "Pacient udává mdlobu.",
        "§3 / Červená / Dehydratace / oběh",
        test("fainting"),
    )
    rule(
        "systolic_hypotension",
        Severity.RED,
        "Systolický tlak je pod 90 mmHg.",
        "§3 / Červená / Dehydratace / oběh",
        test("systolic_bp", lambda v: v < 90),
    )
    rule(
        "fluid_intolerance_with_dehydration",
        Severity.RED,
        "Pacient neudrží tekutiny a má známky dehydratace.",
        "§3 / Červená / Zvracení",
        all_of(test("cannot_keep_fluids"), dehydration),
    )
    rule(
        "cannot_keep_fluids",
        Severity.ORANGE,
        "Pacient neudrží tekutiny.",
        "§3 / Oranžová / Příjem a tekutiny",
        test("cannot_keep_fluids"),
    )
    rule(
        "new_liquid_diet_with_uncontrolled_pain",
        Severity.ORANGE,
        "Pacient nově zvládá jen tekutou stravu a bolest není kontrolovaná.",
        "§3 / Oranžová / Příjem a tekutiny",
        all_of(test("new_only_liquid_food"), test("pain_uncontrolled")),
    )
    rule(
        "reduced_intake_with_circulatory_signs",
        Severity.ORANGE,
        "Snížený příjem doprovází málo moči nebo závrať při vstávání.",
        "§3 / Oranžová / Příjem a tekutiny",
        all_of(
            test("reduced_intake"),
            any_of(test("low_urine"), test("orthostatic_dizziness")),
        ),
    )
    rule(
        "vomiting",
        Severity.RED,
        "Pacient zvracel více než pětkrát za 24 hodin.",
        "§3 / Červená / Zvracení",
        test("vomiting_over_5"),
    )
    rule(
        "vomiting_with_fluid_intolerance",
        Severity.ORANGE,
        "Tři až pět epizod zvracení a pacient neudrží tekutiny.",
        "§3 / Oranžová / Zvracení",
        all_of(vomiting_3_to_5, test("cannot_keep_fluids")),
    )
    rule(
        "vomiting_with_preserved_drinking",
        Severity.YELLOW,
        "Tři až pět epizod zvracení při zachovaném pití.",
        "§4 / Zvracení",
        all_of(vomiting_3_to_5, test("drinking_maintained")),
    )
    rule(
        "bowel_obstruction_signs",
        Severity.RED,
        "Zástava odchodu plynů i stolice se zvracením nebo kolikovitou bolestí.",
        "§3 / Červená / Břicho",
        all_of(
            test("no_gas"),
            test("no_stool"),
            any_of(vomiting, test("colicky_abdominal_pain")),
        ),
    )
    rule(
        "neurological_red_flags",
        Severity.RED,
        "Je doložena zmatenost, porucha vědomí/probuditelnosti, záchvat, nová slabost končetin nebo porucha řeči.",
        "§3 / Červená / Neurologie",
        any_of(
            *(
                test(field)
                for field in (
                    "confusion",
                    "consciousness_disturbance",
                    "difficulty_waking",
                    "seizure",
                    "new_limb_weakness",
                    "speech_disturbance",
                    "unresponsiveness",
                )
            )
        ),
    )
    rule(
        "brain_tumor_morning_headache",
        Severity.ORANGE,
        "Ranní bolest hlavy se zvracením u pacienta s mozkovým nádorem.",
        "§3 / Oranžová / Mozkový nádor",
        all_of(test("brain_tumor"), test("morning_headache"), vomiting),
    )
    rule(
        "metabolic_red_flags",
        Severity.RED,
        "Zvracení, bolest břicha a zrychlené dýchání při diabetu nebo imunoterapii.",
        "§3 / Červená / Metabolismus",
        all_of(
            vomiting,
            test("abdominal_pain"),
            test("rapid_breathing"),
            any_of(test("diabetes"), test("immunotherapy")),
        ),
    )
    rule(
        "immunotherapy_metabolic_symptoms",
        Severity.ORANGE,
        "Velká žízeň, časté močení a hubnutí při imunoterapii.",
        "§3 / Oranžová / Imunoterapie",
        all_of(
            test("immunotherapy"),
            test("polydipsia"),
            test("frequent_urination"),
            test("weight_loss"),
        ),
    )
    rule(
        "hypoglycemia_on_insulin",
        Severity.ORANGE,
        "Glykémie je pod 4 mmol/l při léčbě inzulinem.",
        "§3 / Oranžová / Glykémie",
        all_of(test("glucose_mmol_l", lambda v: v < 4), test("insulin_treatment")),
    )
    rule(
        "symptomatic_hyperglycemia",
        Severity.YELLOW,
        "Glykémie je nad 15 mmol/l se žízní a častým močením.",
        "§4 / Glykémie",
        all_of(
            test("glucose_mmol_l", lambda v: v > 15),
            test("polydipsia"),
            test("frequent_urination"),
        ),
    )
    rule(
        "opioid_red_flags",
        Severity.RED,
        "Nová nápadná spavost, nereagování nebo zpomalené dýchání při opioidech.",
        "§3 / Červená / Opioidy",
        all_of(
            test("opioid_treatment"),
            any_of(
                test("new_marked_drowsiness"),
                test("unresponsiveness"),
                test("slow_breathing"),
            ),
        ),
    )
    rule(
        "chemotherapy_chills",
        Severity.RED,
        "Zimnice během chemoterapie nebo do šesti týdnů po ní.",
        "§3 / Červená / Horečka",
        all_of(test("chills"), test("chemotherapy_within_6_weeks")),
    )
    rule(
        "rest_breathlessness",
        Severity.RED,
        "Dušnost v klidu.",
        "§3 / Červená / Dýchání",
        test("breathlessness_at_rest"),
    )
    rule(
        "sudden_breathlessness_with_cardiac_symptoms",
        Severity.RED,
        "Náhlá dušnost s bolestí na hrudi nebo bušením srdce.",
        "§3 / Červená / Dýchání",
        all_of(
            test("sudden_breathlessness"),
            any_of(test("chest_pain"), test("palpitations")),
        ),
    )
    rule(
        "reported_new_chest_pain",
        Severity.RED,
        "Nově vzniklá bolest na hrudi.",
        "§3 / Červená / Hrudník",
        test("new_chest_pain"),
    )
    rule(
        "diarrhea_severe_or_bloody",
        Severity.RED,
        "Alespoň sedm stolic nad normál nebo průjem s krví.",
        "§3 / Červená / Průjem",
        any_of(
            test("diarrhea_at_least_7"),
            test("diarrhea_with_blood"),
            all_of(test("diarrhea"), test("blood_in_stool")),
        ),
    )
    rule(
        "orthopnea",
        Severity.ORANGE,
        "Nová ortopnoe: dušnost vleže nebo potřeba spát vsedě či na více polštářích.",
        "§3 / Oranžová / Dýchání",
        test("orthopnea"),
    )
    if facts.get("baseline_spo2_pct") and facts.get("spo2_pct"):
        delta = max(v for v, _ in facts["baseline_spo2_pct"]) - min(
            v for v, _ in facts["spo2_pct"]
        )
        put(
            "spo2_drop",
            delta,
            {
                "kind": "derived",
                "field": "spo2_drop",
                "value": delta,
                "source": [
                    e
                    for field in ("baseline_spo2_pct", "spo2_pct")
                    for _, e in facts[field]
                ],
            },
        )
    rule(
        "oxygen_baseline_drop",
        Severity.ORANGE,
        "Saturace poklesla alespoň o tři procentní body proti obvyklé hodnotě.",
        "§3 / Oranžová / Dýchání",
        test("spo2_drop", lambda v: v >= 3),
    )
    rule(
        "high_risk_treatment_diarrhea",
        Severity.ORANGE,
        "Čtyři až šest stolic nad normál při rizikové léčbě.",
        "§3 / Oranžová / Průjem",
        all_of(
            test("diarrhea_4_to_6"),
            any_of(
                test("immunotherapy"),
                test("fluoropyrimidine_treatment"),
                test("irinotecan_treatment"),
            ),
        ),
    )
    rule(
        "loperamide_refractory_diarrhea",
        Severity.ORANGE,
        "Průjem nereaguje na loperamid podle schématu.",
        "§3 / Oranžová / Průjem",
        all_of(
            test("diarrhea"),
            test("loperamide_ineffective"),
            test("loperamide_scheme_followed"),
        ),
    )
    rule(
        "immunotherapy_diarrhea_with_pain",
        Severity.ORANGE,
        "Průjem s bolestí břicha při imunoterapii.",
        "§3 / Oranžová / Průjem na imunoterapii",
        all_of(test("diarrhea"), test("abdominal_pain"), test("immunotherapy")),
    )
    rule(
        "unilateral_calf_swelling_and_pain",
        Severity.ORANGE,
        "Jednostranný otok a bolest lýtka; je nutné poučení o příznacích plicní embolie.",
        "§3 / Oranžová / Žíly",
        all_of(test("unilateral_calf_swelling"), test("calf_pain")),
    )
    rule(
        "hopelessness",
        Severity.ORANGE,
        "Výrok beznaděje vyžaduje kontakt týmu a upřesnění bezpečí.",
        "§3 / Oranžová / Psychika",
        test("hopelessness"),
    )
    rule(
        "worsening_despite_planned_examination",
        Severity.ORANGE,
        "Stav se zhoršuje přes plánované vyšetření; nečekat na termín.",
        "§3 / Oranžová / Opakovaná eskalace",
        test("worsening_despite_planned_examination"),
    )
    rule(
        "constipation_three_days",
        Severity.YELLOW,
        "Zácpa trvá alespoň tři dny.",
        "§4 / Příznak 2. stupně",
        test("constipation_days", lambda v: v >= 3),
    )
    rule(
        "paronychia_limits_activity",
        Severity.YELLOW,
        "Paronychie omezuje běžné činnosti.",
        "§4 / Příznak 2. stupně",
        test("paronychia_limits_activity"),
    )
    rule(
        "hand_foot_limits_activity",
        Severity.YELLOW,
        "Syndrom ruka-noha omezuje běžné činnosti.",
        "§4 / Příznak 2. stupně",
        test("hand_foot_limits_activity"),
    )
    rule(
        "mild_immunotherapy_diarrhea",
        Severity.YELLOW,
        "Mírný průjem při imunoterapii vyžaduje kontakt týmu.",
        "§4 / Průjem",
        all_of(test("diarrhea_up_to_3"), test("immunotherapy")),
    )
    rule(
        "persistent_neuropathy",
        Severity.YELLOW,
        "Neuropatie přetrvává mezi cykly nebo omezuje jemnou motoriku; předat před další aplikací.",
        "§4 / Neuropatie",
        any_of(
            test("neuropathy_persistent_between_cycles"),
            test("neuropathy_limits_fine_motor_skills"),
        ),
    )
    rule(
        "cisplatin_tinnitus",
        Severity.YELLOW,
        "Nový tinnitus při cisplatině; předat před další dávkou.",
        "§4 / Tinnitus",
        all_of(test("new_tinnitus"), test("cisplatin_treatment")),
    )
    rule(
        "cardiotoxic_edema_or_weight_gain",
        Severity.YELLOW,
        "Otoky druhého stupně nebo přírůstek přes dva kg za tři dny při kardiotoxické léčbě.",
        "§4 / Otoky a hmotnost",
        all_of(
            test("cardiotoxic_treatment"),
            any_of(
                test("edema_grade_2"), test("weight_gain_3_days_kg", lambda v: v > 2)
            ),
        ),
    )
    rule(
        "monthly_weight_loss",
        Severity.YELLOW,
        "Úbytek hmotnosti dosahuje alespoň pěti procent za měsíc.",
        "§4 / Úbytek hmotnosti",
        test("weight_loss_month_pct", lambda v: v >= 5),
    )
    rule(
        "functional_status_decline",
        Severity.YELLOW,
        "Soběstačnost poklesla o alespoň dva stupně.",
        "§4 / Soběstačnost",
        test("functional_status_drop", lambda v: v >= 2),
    )
    rule(
        "progressive_intake_decline",
        Severity.YELLOW,
        "Postupně klesá příjem jídla nebo tekutin.",
        "§4 / Příjem",
        test("progressive_intake_decline"),
    )
    rule(
        "moderate_psychological_distress",
        Severity.YELLOW,
        "Středně závažný smutek nebo úzkost.",
        "§4 / Psychická zátěž",
        any_of(test("moderate_sadness"), test("moderate_anxiety")),
    )
    rule(
        "caregiver_exhaustion",
        Severity.YELLOW,
        "Pečující osoba udává vyčerpání.",
        "§4 / Pečující",
        test("caregiver_exhaustion"),
    )
    rule(
        "medication_nonadherence",
        Severity.YELLOW,
        "Pacient vynechává předepsané léky.",
        "§4 / Vynechávání léků",
        test("medication_nonadherence"),
    )
    rule(
        "three_missed_checkins",
        Severity.YELLOW,
        "Tři nebo více nevyplněných check-inů za sebou.",
        "§4 / Výpadek dat",
        test("consecutive_missed_checkins", lambda v: v >= 3),
    )
    rule(
        "unfavorable_trend",
        Severity.YELLOW,
        "Několik záznamů ukazuje zhoršující se trend.",
        "§6.1 / Trend",
        test("unfavorable_trend"),
    )
    rule(
        "immunotherapy_new_symptom",
        Severity.YELLOW,
        "Nový příznak při imunoterapii je nutné hlásit týmu.",
        "§5 / Imunoterapie",
        all_of(
            test("immunotherapy"),
            any_of(
                test("new_diarrhea"),
                test("new_cough"),
                test("new_breathlessness"),
                test("new_thirst"),
                test("new_fatigue"),
            ),
        ),
    )
    rule(
        "irinotecan_diarrhea_not_resolved",
        Severity.YELLOW,
        "Při irinotekanu průjem právě trvá nebo od poslední průjmovité stolice neuplynulo dvanáct hodin.",
        "§5 / Irinotekan",
        all_of(
            test("irinotecan_treatment"),
            any_of(
                test("diarrhea_current"),
                test("hours_without_diarrhea", lambda v: v < 12),
            ),
        ),
    )
    rule(
        "reported_fever",
        Severity.RED,
        "Teplota alespoň 38 °C během chemoterapie nebo do šesti týdnů po ní.",
        "§3 / Červená / Horečka",
        all_of(
            test("temperature_c", lambda v: v >= 38),
            test("chemotherapy_within_6_weeks"),
        ),
    )
    rule(
        "reported_oxygen_red",
        Severity.RED,
        "Saturace je pod 90 %.",
        "§3 / Červená / Dýchání",
        test("spo2_pct", lambda v: v < 90),
    )
    rule(
        "reported_oxygen_orange",
        Severity.ORANGE,
        "Saturace je pod 92 %.",
        "§3 / Oranžová / Dýchání",
        test("spo2_pct", lambda v: v < 92),
    )
    rule(
        "reported_suicidal_thoughts",
        Severity.ORANGE,
        "Pacient sděluje myšlenky na sebevraždu; ověřit bezpečí.",
        "§3 / Oranžová / Psychika",
        test("suicidal_thoughts"),
    )
    rule(
        "suicidal_thoughts_with_plan",
        Severity.RED,
        "Myšlenky na sebevraždu s plánem, úmyslem nebo prostředky.",
        "§3 / Červená / Psychika",
        all_of(test("suicidal_thoughts"), test("suicide_plan_intent_or_means")),
    )
    return {
        "scores": scores,
        "reasons": reasons,
        "skipped_rules": skipped,
        "review_issues": issues,
    }
