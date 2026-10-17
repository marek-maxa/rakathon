"""Author source-based acceptance fixtures, independently of application output."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AT = "2026-10-19T10:00:00+02:00"
SOURCES = {
    "rules": {
        "path": "rakathon_meddi_onco_data/docs/pravidla_triaze.md",
        "kind": "markdown",
    },
    "pdf": {"path": "documents/MEDDI – MEDDI Onco.pdf", "kind": "pdf", "pages": 13},
    "slides": {
        "path": "documents/MEDDI_Onco_Rakathon_2026.pptx",
        "kind": "pptx",
        "slides": 6,
    },
    "bundle": {"path": "rakathon_meddi_onco_data/README.md", "kind": "markdown"},
    "definitions": {
        "path": "rakathon_meddi_onco_data/docs/dotazniky_definice.json",
        "kind": "json",
    },
}
requirements = []
inputs = []
expectations = []


def ref(source, locator):
    return {"source_id": source, "locator": locator}


def requirement(
    identifier, title, locator, *, kind="hard_minimum", source="rules", extra=()
):
    result = {
        "id": identifier,
        "title": title,
        "kind": kind,
        "sources": [ref(source, locator), *extra],
    }
    requirements.append(result)
    return result


def case(
    req,
    suffix,
    text,
    *,
    observations=None,
    context=None,
    minimum=None,
    maximum=None,
    grade="automatic",
    checks=None,
    author="patient",
    history=(),
    answers=(),
    at=AT,
    tags=(),
    notes=None,
    sources=(),
):
    identifier = f"{req['id']}.{suffix}"
    source = {
        "id": identifier,
        "assessment_at": at,
        "patient": {"patient_id": "synthetic-acceptance", "synthetic": True},
        "patient_context": deepcopy(context or {}),
        "events": [
            {
                "id": "opening",
                "source": "master_question",
                "question": "Jak se dnes cítíte?",
                "author": author,
                "available_at": at,
                "text": text,
            }
        ],
        "history": deepcopy(list(history)),
        "questionnaire_answers": deepcopy(list(answers)),
    }
    expected = {
        "id": identifier,
        "requirement_ids": [req["id"]],
        "title": text[:90],
        "grading": grade,
        "tags": [req["kind"], *tags],
        "sources": [*deepcopy(req["sources"]), *deepcopy(list(sources))],
        "checks": {
            "level_min": minimum,
            "level_max": maximum,
            "observations_subset": observations or {},
            "require_evidence": minimum is not None and minimum >= 2,
            **(checks or {}),
        },
        "review_notes": notes,
    }
    inputs.append(source)
    expectations.append(expected)
    return source, expected


def clinical(identifier, title, locator, text, observations, level, context=None):
    req = requirement(
        identifier,
        title,
        locator,
        kind="typical_yellow" if level == 2 else "hard_minimum",
    )
    case(
        req,
        "message",
        text,
        observations=observations,
        context=context,
        minimum=level,
        tags=["message", "clinical"],
    )
    # Same clinical contract through a structured input, without relying on NLP.
    raw, _ = case(
        req,
        "structured",
        "",
        context=context,
        minimum=level,
        observations=observations,
        tags=["structured", "clinical"],
    )
    raw["events"] = []
    raw["structured_observations"] = deepcopy(observations)
    denied = {k: False for k, v in observations.items() if type(v) is bool}
    unknown_numbers = [k for k, v in observations.items() if type(v) in {int, float}]
    case(
        req,
        "negated-quotation",
        f"Tohle je jen citace z letáku, netýká se mě: „{text}“ Žádný z popsaných příznaků teď nemám.",
        context=context,
        observations=denied,
        tags=["negative", "quoted-symptom", "false-positive"],
        checks={
            "must_not_infer": unknown_numbers,
            "urgent_instruction_forbidden": True,
        },
    )
    return req


def boundary(req, field, values, context, text_template, levels, *, extra=None):
    for index, (value, level) in enumerate(zip(values, levels, strict=True)):
        observations = {**(extra or {}), field: value}
        case(
            req,
            f"boundary-{index + 1}",
            text_template.format(value=value),
            observations=observations,
            context=context,
            minimum=level,
            tags=["boundary"],
            checks={"forbid_invented_numbers": True},
        )


def build_clinical():
    red = "§3 / Červená"
    orange = "§3 / Oranžová"
    fever = clinical(
        "RED-FEVER",
        "Teplota a chemoterapie",
        red + " / Horečka",
        "Dnes mám teplotu 38,0 °C, chemoterapii jsem dostal před deseti dny.",
        {"temperature_c": 38.0},
        4,
        {"chemotherapy_within_6_weeks": True, "days_since_actual_chemotherapy": 10},
    )
    boundary(
        fever,
        "temperature_c",
        [37.9, 38.0, 38.1],
        {"chemotherapy_within_6_weeks": True},
        "Právě jsem naměřil {value} °C, probíhá chemoterapie.",
        [None, 4, 4],
    )
    for days in [0, 6, 7, 10, 14, 15, 41, 42, 43]:
        case(
            fever,
            f"chemo-day-{days}",
            f"Mám 38,2 °C, poslední skutečné podání chemoterapie bylo před {days} dny.",
            observations={"temperature_c": 38.2},
            context={"days_since_actual_chemotherapy": days},
            minimum=4 if days <= 42 else None,
            tags=["boundary", "chemotherapy-timing"],
            checks={"must_not_infer": ["neutropenia_confirmed"]},
        )
    clinical(
        "RED-CHILLS",
        "Zimnice při chemoterapii",
        red + " / Horečka",
        "Po chemoterapii se teď třesu zimnicí, teploměr nemám.",
        {"chills": True},
        4,
        {"chemotherapy_within_6_weeks": True},
    )
    definitions = [
        (
            "RED-REST-DYSPNEA",
            "Dýchání",
            "Nemůžu se nadechnout, i když jen sedím.",
            {"breathlessness_at_rest": True},
            {},
        ),
        (
            "RED-SUDDEN-CHEST",
            "Dýchání",
            "Náhle se mi špatně dýchá a bolí mě na hrudi.",
            {"sudden_breathlessness": True, "chest_pain": True},
            {},
        ),
        (
            "RED-SUDDEN-PALPITATIONS",
            "Dýchání",
            "Najednou se dusím a buší mi srdce.",
            {"sudden_breathlessness": True, "palpitations": True},
            {},
        ),
        (
            "RED-NEW-CHEST",
            "Hrudník",
            "Dnes mě nově začalo bolet na hrudi.",
            {"new_chest_pain": True},
            {},
        ),
        (
            "RED-CONFUSION",
            "Neurologie",
            "Táta je teď zmatený, neví, kde je.",
            {"confusion": True},
            {},
        ),
        (
            "RED-CONSCIOUSNESS",
            "Neurologie",
            "Maminka ztrácí vědomí.",
            {"impaired_consciousness": True},
            {},
        ),
        (
            "RED-AROUSAL",
            "Neurologie",
            "Tatínka teď nedokážu probudit.",
            {"impaired_arousability": True},
            {},
        ),
        (
            "RED-SEIZURE",
            "Neurologie",
            "Právě jsem měl epileptický záchvat.",
            {"seizure": True},
            {},
        ),
        (
            "RED-LIMB-WEAKNESS",
            "Neurologie",
            "Najednou mi zeslábla levá ruka a neudržím ji nahoře.",
            {"new_limb_weakness": True},
            {},
        ),
        (
            "RED-SPEECH",
            "Neurologie",
            "Najednou nemůžu pořádně mluvit.",
            {"speech_disturbance": True},
            {},
        ),
        (
            "RED-STOOL-BLOOD",
            "Krvácení",
            "Dnes mám krev ve stolici.",
            {"blood_in_stool": True},
            {},
        ),
        (
            "RED-VOMIT-BLOOD",
            "Krvácení",
            "Právě jsem zvracel krev.",
            {"blood_in_vomit": True},
            {},
        ),
        (
            "RED-BLACK-STOOL",
            "Krvácení",
            "Dnes mám černou dehtovitou stolici.",
            {"black_stool": True},
            {},
        ),
        ("RED-URINE-BLOOD", "Krvácení", "Močím krev.", {"blood_in_urine": True}, {}),
        (
            "RED-HEAD-ANTICOAG",
            "Krvácení",
            "Uhodil jsem se teď do hlavy a užívám warfarin.",
            {"head_injury": True},
            {"anticoagulation": True},
        ),
        (
            "RED-DIARRHEA-BLOOD",
            "Průjem",
            "Mám průjem s krví.",
            {"diarrhea_with_blood": True},
            {},
        ),
        (
            "RED-FLUID-DEHYDRATION",
            "Zvracení",
            "Neudržím ani vodu a mám prokázané známky dehydratace.",
            {"cannot_keep_fluids": True, "dehydration_signs": True},
            {},
        ),
        ("RED-FAINT", "Dehydratace / oběh", "Teď jsem omdlel.", {"syncope": True}, {}),
        (
            "RED-OBSTRUCTION-VOMIT",
            "Břicho",
            "Neodcházejí mi plyny ani stolice a zvracím.",
            {"no_gas_and_stool": True, "vomiting": True},
            {},
        ),
        (
            "RED-OBSTRUCTION-COLIC",
            "Břicho",
            "Neodcházejí mi plyny ani stolice a mám kolikovité bolesti břicha.",
            {"no_gas_and_stool": True, "colicky_abdominal_pain": True},
            {},
        ),
        (
            "RED-OPIOID-DROWSY",
            "Opioidy",
            "Po opioidu jsem nově nápadně spavá.",
            {"new_marked_drowsiness": True},
            {"opioid_treatment": True},
        ),
        (
            "RED-OPIOID-NORESPONSE",
            "Opioidy",
            "Maminka bere morfin a teď nereaguje.",
            {"unresponsiveness": True},
            {"opioid_treatment": True},
        ),
        (
            "RED-OPIOID-SLOWBREATH",
            "Opioidy",
            "Po morfinu teď nápadně pomalu dýchám.",
            {"slow_breathing": True},
            {"opioid_treatment": True},
        ),
    ]
    for identifier, area, text, obs, context in definitions:
        clinical(identifier, text, red + " / " + area, text, obs, 4, context)
        if identifier in {
            "RED-CONFUSION",
            "RED-CONSCIOUSNESS",
            "RED-AROUSAL",
            "RED-OPIOID-NORESPONSE",
        }:
            inputs[-3]["events"][0]["author"] = "caregiver"
    for sign, text in [
        ("severe_headache", "silně mě bolí hlava"),
        ("visual_disturbance", "špatně vidím"),
        ("speech_disturbance", "špatně mluvím"),
        ("chest_pain", "bolí mě na hrudi"),
    ]:
        clinical(
            "RED-BP-" + sign.upper(),
            "Vysoký tlak s příznakem",
            red + " / Tlak",
            "Mám lékařem označený vysoký tlak a " + text + ".",
            {"high_blood_pressure": True, sign: True},
            4,
        )
    for care in ["diabetes", "immunotherapy"]:
        clinical(
            "RED-METABOLIC-" + care.upper(),
            "Metabolická varovná kombinace",
            red + " / Metabolismus",
            "Dnes zvracím, bolí mě břicho a rychle dýchám.",
            {"vomiting": True, "abdominal_pain": True, "rapid_breathing": True},
            4,
            {care: True},
        )
    for sign, text in [
        ("suicide_plan", "Myslím na sebevraždu a mám konkrétní plán."),
        ("suicide_intent", "Mám sebevražedné myšlenky a chci je uskutečnit."),
        ("suicide_means", "Myslím na sebevraždu a mám k tomu připravené prostředky."),
    ]:
        clinical(
            "RED-PSYCH-" + sign.upper(),
            "Sebevražedné myšlenky s plánem/úmyslem/prostředky",
            red + " / Psychika",
            text,
            {"suicidal_thoughts": True, sign: True},
            4,
        )
    numbers = [
        (
            "RED-OXYGEN",
            "Dýchání",
            "spo2_pct",
            [89, 90, 91, 92],
            [4, 3, 3, None],
            "Saturace je právě {value} %.",
            {},
        ),
        (
            "RED-NOSE",
            "Krvácení",
            "nosebleed_minutes",
            [19, 20, 21],
            [None, None, 4],
            "Krvácení z nosu trvá souvisle {value} minut.",
            {},
        ),
        (
            "RED-DIARRHEA",
            "Průjem",
            "stools_above_baseline_24h",
            [6, 7, 8],
            [None, 4, 4],
            "Za posledních 24 hodin mám {value} průjmových stolic nad můj obvyklý počet.",
            {},
        ),
        (
            "RED-VOMITING",
            "Zvracení",
            "vomiting_episodes_24h",
            [5, 6, 7],
            [2, 4, 4],
            "Za posledních 24 hodin jsem zvracel {value}krát, vodu udržím.",
            {},
        ),
        (
            "RED-ANURIA",
            "Dehydratace / oběh",
            "hours_without_urine",
            [9, 10, 10.1, 11],
            [None, None, 4, 4],
            "Nemočil jsem už {value} hodin.",
            {},
        ),
        (
            "RED-LOWBP",
            "Dehydratace / oběh",
            "systolic_bp",
            [89, 90, 91],
            [4, None, None],
            "Aktuální systolický tlak je {value} mmHg.",
            {},
        ),
    ]
    for identifier, area, field, values, levels, text, context in numbers:
        req = requirement(
            identifier,
            "Hranice: " + field,
            red + " / " + area,
            extra=[ref("rules", "§4 / Zvracení")]
            if identifier == "RED-VOMITING"
            else [ref("rules", "§3 / Oranžová / Dýchání")]
            if identifier == "RED-OXYGEN"
            else [],
        )
        boundary(req, field, values, context, text, levels)
    req = clinical(
        "RED-HYPERTENSION",
        "Tlak 180/110",
        red + " / Tlak",
        "Naměřil jsem tlak 180/110 mmHg.",
        {"systolic_bp": 180, "diastolic_bp": 110},
        4,
    )
    for sbp, dbp in [(179, 109), (180, 109), (179, 110), (181, 111)]:
        case(
            req,
            f"pair-{sbp}-{dbp}",
            f"Tlak je {sbp}/{dbp} mmHg, jiné potíže neuvádím.",
            observations={"systolic_bp": sbp, "diastolic_bp": dbp},
            minimum=4 if sbp >= 180 and dbp >= 110 else None,
            grade="clinical_review" if (sbp >= 180) != (dbp >= 110) else "automatic",
            tags=["boundary", "source-ambiguity"],
            notes="Zdroj neříká výslovně AND/OR. Smíšený pár nepovažovat za autoritativní přesnou barvu bez mentora.",
        )
    clinical(
        "ORANGE-FEELING",
        "Celkový pocit 5",
        orange + " / Celkový stav",
        "Na otázku jak se celkově cítím volím 5 = velmi špatně.",
        {"overall_feeling": 5},
        3,
    )
    req = requirement(
        "ORANGE-OXYGEN-DROP", "Pokles saturace od baseline", orange + " / Dýchání"
    )
    boundary(
        req,
        "spo2_pct",
        [95, 94, 93],
        {"baseline_spo2_pct": 97},
        "Běžně mívám saturaci 97 %, dnes mám {value} %.",
        [None, 3, 3],
    )
    rows = [
        (
            "ORANGE-ORTHOPNEA",
            "Dýchání",
            "Nově musím spát vsedě, vleže se dusím.",
            {"orthopnea": True},
            {},
        ),
        (
            "ORANGE-LOPERAMIDE",
            "Průjem",
            "Průjem nereaguje na loperamid, užívám jej přesně podle svého předepsaného schématu.",
            {
                "diarrhea": True,
                "loperamide_ineffective": True,
                "loperamide_scheme_followed": True,
            },
            {},
        ),
        (
            "ORANGE-IO-PAIN",
            "Průjem na imunoterapii",
            "Mám teď průjem a bolí mě břicho.",
            {"diarrhea": True, "abdominal_pain": True},
            {"immunotherapy": True},
        ),
        (
            "ORANGE-FLUIDS",
            "Příjem a tekutiny",
            "Teď neudržím žádné tekutiny.",
            {"cannot_keep_fluids": True},
            {},
        ),
        (
            "ORANGE-LIQUID-FOOD",
            "Příjem a tekutiny",
            "Nově zvládnu jen tekutou stravu a bolest se nedaří zvládnout.",
            {"new_only_liquid_food": True, "pain_uncontrolled": True},
            {},
        ),
        (
            "ORANGE-LOW-URINE",
            "Příjem a tekutiny",
            "Málo piju a málo močím.",
            {"reduced_intake": True, "low_urine_output": True},
            {},
        ),
        (
            "ORANGE-DIZZY-INTAKE",
            "Příjem a tekutiny",
            "Málo piju a při vstávání se mi točí hlava.",
            {"reduced_intake": True, "orthostatic_dizziness": True},
            {},
        ),
        (
            "ORANGE-ANTICOAG-BLEED",
            "Krvácení",
            "Dnes mírně krvácím z dásní.",
            {"any_bleeding": True},
            {"anticoagulation": True},
        ),
        (
            "ORANGE-ANTICOAG-BRUISE",
            "Krvácení",
            "Dnes se mi objevily nové modřiny.",
            {"new_bruises": True},
            {"anticoagulation": True},
        ),
        (
            "ORANGE-CALF",
            "Žíly",
            "Jedno lýtko je nově oteklé a bolí.",
            {"unilateral_calf_swelling": True, "calf_pain": True},
            {},
        ),
        (
            "ORANGE-NRS",
            "Bolest",
            "Bolest je teď 7 z 10 a nepovolila po mé předepsané SOS dávce.",
            {"pain_nrs": 7, "pain_persists_after_rescue_dose": True},
            {},
        ),
        (
            "ORANGE-BRAIN",
            "Mozkový nádor",
            "Ráno mě bolí hlava a zvracím.",
            {"morning_headache": True, "vomiting": True},
            {"brain_tumor": True},
        ),
        (
            "ORANGE-IO-METABOLIC",
            "Imunoterapie",
            "Mám velkou žízeň, často močím a hubnu.",
            {"polydipsia": True, "frequent_urination": True, "weight_loss": True},
            {"immunotherapy": True},
        ),
        (
            "ORANGE-PSYCH-YES",
            "Psychika",
            "Ano, napadá mě, že bych si nejraději vzal život. Plán ani úmysl teď nemám.",
            {"suicidal_thoughts": True, "suicide_plan_intent_or_means": False},
            {},
        ),
        (
            "ORANGE-HOPELESS",
            "Psychika",
            "Už to nemá cenu, jsem úplně bez naděje.",
            {"hopelessness": True},
            {},
        ),
        (
            "ORANGE-WORSENING",
            "Opakovaná eskalace",
            "Vyšetření mám objednané, ale stav se mi dál zhoršuje.",
            {"worsening_despite_planned_examination": True},
            {},
        ),
    ]
    for identifier, area, text, obs, context in rows:
        clinical(identifier, text, orange + " / " + area, text, obs, 3, context)
    req = requirement(
        "ORANGE-CALF-EDUCATION",
        "Bolest a jednostranný otok lýtka vyžadují poučení o příznacích embolie",
        orange + " / Žíly",
        kind="general",
    )
    case(
        req,
        "warning",
        "Od rána mám oteklé jen pravé lýtko a bolí mě. Dušnost ani bolest na hrudi nemám.",
        observations={"unilateral_calf_swelling": True, "calf_pain": True},
        minimum=3,
        grade="human_review",
        tags=["clinical", "patient-advice"],
        notes="Zkontrolovat povinné poučení o příznacích plicní embolie a okamžité pomoci při jejich rozvoji. Netvrdit pacientovi potvrzenou diagnózu trombózy či embolie.",
    )
    req = next(r for r in requirements if r["id"] == "ORANGE-NRS")
    case(
        req,
        "sos-helped",
        "Před hodinou byla bolest 8 z 10. Po předepsané SOS dávce klesla na 2 z 10 a teď se nezhoršuje.",
        observations={"pain_persists_after_rescue_dose": False},
        grade="clinical_review",
        tags=["negative", "improvement"],
        notes="Podmínka přetrvávající bolesti přes SOS není splněna. Zdroj neurčuje univerzální výslednou barvu po zlepšení; zohlednit současný stav a §6.3, ne maximum celé historie.",
        sources=[ref("rules", "§6.3 / Zlepšení po zásahu")],
    )
    for treatment in [
        "immunotherapy",
        "fluoropyrimidine_treatment",
        "irinotecan_treatment",
    ]:
        req = requirement(
            "ORANGE-DIARRHEA-" + treatment.upper(),
            "Průjem při rizikové léčbě",
            orange + " / Průjem",
        )
        boundary(
            req,
            "stools_above_baseline_24h",
            [3, 4, 6, 7],
            {treatment: True},
            "Za posledních 24 hodin mám {value} průjmových stolic navíc oproti obvyklému stavu.",
            [2 if treatment == "immunotherapy" else None, 3, 3, 4],
        )
    req = requirement(
        "ORANGE-VOMIT-FLUID",
        "Zvracení a neudržení tekutin",
        orange + " / Zvracení",
        extra=[ref("rules", "§3 / Oranžová / Příjem a tekutiny")],
    )
    boundary(
        req,
        "vomiting_episodes_24h",
        [2, 3, 5, 6],
        {},
        "Za 24 hodin jsem zvracel {value}krát a neudržím tekutiny.",
        [3, 3, 3, 4],
        extra={"cannot_keep_fluids": True},
    )
    req = requirement(
        "ORANGE-GLUCOSE", "Hypoglykémie při inzulinu", orange + " / Glykémie"
    )
    boundary(
        req,
        "glucose_mmol_l",
        [3.9, 4.0, 4.1],
        {"insulin_treatment": True},
        "Aktuální glykémie je {value} mmol/l, užívám inzulin.",
        [3, None, None],
    )
    req = clinical(
        "ORANGE-ANTIANGIO-BP",
        "Tlak 160/100 při antiangiogenní léčbě",
        orange + " / Tlak",
        "Tlak je 160/100 mmHg.",
        {"systolic_bp": 160, "diastolic_bp": 100},
        3,
        {"antiangiogenic_treatment": True},
    )
    for sbp, dbp in [(159, 99), (160, 99), (159, 100)]:
        case(
            req,
            f"pair-{sbp}-{dbp}",
            f"Tlak je {sbp}/{dbp} mmHg.",
            observations={"systolic_bp": sbp, "diastolic_bp": dbp},
            context={"antiangiogenic_treatment": True},
            grade="clinical_review" if (sbp >= 160) != (dbp >= 100) else "automatic",
            notes="Potvrdit význam párového prahu AND/OR, nikoli převzít existující implementaci jako zdroj.",
            tags=["boundary"],
        )


def build_yellow():
    yellow = "§4"
    rows = [
        (
            "YELLOW-GRADE2",
            "Příznak 2. stupně bez varovných příznaků",
            "Mám doložené nežádoucí účinky druhého stupně, bez varovných příznaků.",
            {"grade_2_symptom_without_warning_signs": True},
            {},
        ),
        (
            "YELLOW-NAUSEA",
            "Nevolnost se sníženým příjmem",
            "Je mi nevolno a kvůli tomu jím méně, tekutiny udržím.",
            {"nausea_with_reduced_food_intake": True, "cannot_keep_fluids": False},
            {},
        ),
        (
            "YELLOW-MOUTH",
            "Afty omezující jídlo",
            "Afty mě omezují při jídle, tekutiny zvládnu.",
            {"mouth_ulcers_limit_eating": True},
            {},
        ),
        (
            "YELLOW-PARONYCHIA",
            "Paronychie omezuje činnosti",
            "Zánět kolem nehtu mi omezuje běžné činnosti.",
            {"paronychia_limits_activity": True},
            {},
        ),
        (
            "YELLOW-HANDFOOT",
            "Syndrom ruka-noha omezuje činnosti",
            "Mám lékařem označený syndrom ruka-noha, který mi omezuje činnosti.",
            {"hand_foot_limits_activity": True},
            {},
        ),
        (
            "YELLOW-HYPOTENSION",
            "Hypotenze a závrať",
            "Mám doložený nízký tlak a při vstávání se mi točí hlava; neomdlévám.",
            {"hypotension": True, "orthostatic_dizziness": True, "syncope": False},
            {},
        ),
        (
            "YELLOW-NEURO-PERSIST",
            "Neuropatie mezi cykly",
            "Brnění rukou mi přetrvává i mezi cykly.",
            {"neuropathy_persistent_between_cycles": True},
            {},
        ),
        (
            "YELLOW-NEURO-FINE",
            "Omezení jemné motoriky",
            "Kvůli neuropatii nezapnu knoflíky.",
            {"neuropathy_limits_fine_motor_skills": True},
            {},
        ),
        (
            "YELLOW-TINNITUS",
            "Nový tinnitus při cisplatině",
            "Nově mi píská v uších.",
            {"new_tinnitus": True},
            {"cisplatin_treatment": True},
        ),
        (
            "YELLOW-EDEMA",
            "Otoky druhého stupně",
            "Mám doložené otoky druhého stupně.",
            {"edema_grade_2": True},
            {},
        ),
        (
            "YELLOW-INTAKE",
            "Postupný pokles příjmu",
            "Už několik kontrol po sobě sním méně než při té minulé.",
            {"progressive_intake_decline": True},
            {},
        ),
        (
            "YELLOW-SADNESS",
            "Střední smutek",
            "Můj smutek je středního stupně a omezuje mě; myšlenky na sebevraždu nemám.",
            {"moderate_sadness": True, "suicidal_thoughts": False},
            {},
        ),
        (
            "YELLOW-ANXIETY",
            "Střední úzkost",
            "Úzkost je středně silná a omezuje mě.",
            {"moderate_anxiety": True},
            {},
        ),
        (
            "YELLOW-CAREGIVER",
            "Vyčerpání pečující osoby",
            "Píšu za maminku. Já jako pečující jsem vyčerpaná, maminka se teď cítí stabilně.",
            {"caregiver_exhaustion": True},
            {},
        ),
        (
            "YELLOW-ADHERENCE",
            "Vynechávání léků",
            "Několikrát jsem vynechal předepsané léky.",
            {"medication_nonadherence": True},
            {},
        ),
    ]
    for identifier, title, text, obs, context in rows:
        req = clinical(identifier, title, yellow + " / " + title, text, obs, 2, context)
        if identifier in {
            "YELLOW-NEURO-PERSIST",
            "YELLOW-NEURO-FINE",
            "YELLOW-TINNITUS",
        }:
            for item in expectations[-3:-1]:
                item["checks"]["before_next_dose"] = True
        if identifier == "YELLOW-CAREGIVER":
            inputs[-3]["events"][0]["author"] = "caregiver"
            expectations[-3]["checks"]["address_caregiver"] = True
    numeric = [
        (
            "YELLOW-CONSTIPATION",
            "Zácpa",
            "constipation_days",
            [2, 3, 4],
            [None, 2, 2],
            "Neměl jsem stolici už {value} dny, plyny odcházejí a nezvracím.",
            {},
            {"no_gas_and_stool": False, "vomiting": False},
        ),
        (
            "YELLOW-PAIN",
            "Bolest",
            "pain_nrs",
            [0, 3, 4, 6, 7],
            [None, None, 2, 2, 3],
            "Bolest je {value} z 10 na NRS, předepsaná SOS dávka nepomohla.",
            {},
            {"pain_persists_after_rescue_dose": True},
        ),
        (
            "YELLOW-RESCUE",
            "Bolest",
            "rescue_doses_per_day",
            [2, 3, 4],
            [None, 2, 2],
            "Potřebuji {value} předepsané SOS dávky proti bolesti za den.",
            {},
            {},
        ),
        (
            "YELLOW-WEIGHT-GAIN",
            "Přírůstek hmotnosti",
            "weight_gain_3_days_kg",
            [2.0, 2.1, 3.0],
            [None, 2, 2],
            "Za poslední tři dny jsem přibral {value} kg.",
            {"cardiotoxic_treatment": True},
            {},
        ),
        (
            "YELLOW-WEIGHT-LOSS",
            "Úbytek hmotnosti",
            "weight_loss_month_pct",
            [4.9, 5.0, 5.1],
            [None, 2, 2],
            "Za poslední měsíc jsem zhubl o {value} procent své hmotnosti.",
            {},
            {},
        ),
        (
            "YELLOW-ADL",
            "Soběstačnost",
            "functional_status_drop",
            [1, 2, 3],
            [None, 2, 2],
            "Proti výchozímu stavu mám doložený pokles soběstačnosti o {value} stupně.",
            {},
            {},
        ),
    ]
    for identifier, title, field, values, levels, text, context, extra in numeric:
        req = requirement(
            identifier, title, yellow + " / " + title, kind="typical_yellow"
        )
        boundary(req, field, values, context, text, levels, extra=extra)
        if identifier == "YELLOW-PAIN":
            expectations[-1]["sources"].append(ref("rules", "§3 / Oranžová / Bolest"))
    req = requirement(
        "YELLOW-GLUCOSE",
        "Symptomatická hyperglykémie",
        yellow + " / Glykémie",
        kind="typical_yellow",
    )
    boundary(
        req,
        "glucose_mmol_l",
        [15.0, 15.1, 16],
        {},
        "Mám glykémii {value} mmol/l, velkou žízeň a často močím.",
        [None, 2, 2],
        extra={"polydipsia": True, "frequent_urination": True},
    )
    for item in expectations[-2:]:
        item["checks"]["same_day_contact"] = True
    req = requirement(
        "YELLOW-BP-REPEATED",
        "Opakovaný tlak",
        yellow + " / Tlak",
        kind="typical_yellow",
    )
    for count in [1, 2, 3, 4]:
        case(
            req,
            f"count-{count}",
            f"Mám doložený tlak 140/90 při {count} samostatných měřeních.",
            observations={
                "systolic_bp": 140,
                "diastolic_bp": 90,
                "high_bp_measurement_count": count,
            },
            minimum=2 if count >= 3 else None,
            tags=["boundary"],
            checks={"must_not_infer": ["antiangiogenic_treatment"]},
        )
    req = requirement(
        "YELLOW-MISSED",
        "Počet vynechaných check-inů",
        yellow + " / Vynechané check-iny",
        kind="typical_yellow",
    )
    for count in [1, 2, 3, 4]:
        case(
            req,
            f"count-{count}",
            f"Při stabilním stavu jsem vynechal {count} check-iny za sebou.",
            observations={"consecutive_missed_checkins": count},
            minimum=2 if count >= 3 else 1,
            maximum=1 if count < 3 else None,
            context={"stable_state_confirmed": True},
            checks={"reminder_required": count < 3},
            tags=["boundary", "false-positive"],
        )
    req = requirement(
        "YELLOW-IO-DIARRHEA",
        "Mírný průjem a léčba",
        yellow + " / Průjem",
        kind="typical_yellow",
    )
    for treatment in [True, False]:
        for count in [1, 2, 3]:
            case(
                req,
                f"io-{int(treatment)}-count-{count}",
                f"Za posledních 24 hodin mám {count} průjmových stolic nad normál. Jiné potíže nemám, tekutiny udržím, krev ve stolici není.",
                observations={"stools_above_baseline_24h": count},
                context={
                    "immunotherapy": treatment,
                    "other_risk_treatment": False,
                    "other_current_symptoms_denied": True,
                },
                minimum=2 if treatment else 1,
                maximum=1 if not treatment else None,
                tags=["false-positive", "boundary"],
            )
    req = requirement(
        "YELLOW-VOMIT-DRINKING",
        "Zvracení při zachovaném pití",
        "§4 / Zvracení",
        kind="typical_yellow",
        extra=[ref("rules", "§3 / Červená / Zvracení")],
    )
    boundary(
        req,
        "vomiting_episodes_24h",
        [2, 3, 4, 5, 6],
        {},
        "Za posledních 24 hodin jsem zvracel {value}krát, piju a tekutiny udržím.",
        [None, 2, 2, 2, 4],
        extra={"cannot_keep_fluids": False},
    )


def build_priority():
    extra = [
        ref("pdf", "s. 9 / Situace, které musíte zachytit"),
        ref("pdf", "s. 10 / Přehrávání v čase"),
    ]
    definitions = [
        (
            "PRESENTATION-FEVER",
            "Horečka při poklesu bílých krvinek",
            "§3 / Červená / Horečka; §5 / Den 7–14",
            "Desátý den po chemoterapii mám 38,5 °C a zimnici.",
            {"temperature_c": 38.5, "chills": True},
            {"days_since_actual_chemotherapy": 10, "chemotherapy_within_6_weeks": True},
            4,
        ),
        (
            "PRESENTATION-COLITIS",
            "Imunitní kolitida zhoršená během dvou dnů",
            "§3 / Oranžová / Průjem na imunoterapii; §6.1",
            "Na imunoterapii mám dnes 7 průjmových stolic nad normál za 24 h, před dvěma dny to byly jen 2.",
            {"stools_above_baseline_24h": 7},
            {"immunotherapy": True},
            4,
        ),
        (
            "PRESENTATION-HEART",
            "Plíživé známky srdečního selhání",
            "§3 / Oranžová / Dýchání; §4 / Přírůstek hmotnosti; §6.1",
            "Za tři dny jsem přibral 2,5 kg a nově musím spát vsedě.",
            {"weight_gain_3_days_kg": 2.5, "orthopnea": True},
            {"cardiotoxic_treatment": True},
            3,
        ),
        (
            "PRESENTATION-INTERACTION",
            "Léková interakce a krvácení",
            "§3 / Červená / Krvácení; §5 / Antikoagulace",
            "Beru warfarin a kapecitabin a dnes mám černou dehtovitou stolici.",
            {"black_stool": True},
            {
                "anticoagulation": True,
                "fluoropyrimidine_treatment": True,
                "medications": ["warfarin", "kapecitabin"],
            },
            4,
        ),
        (
            "PRESENTATION-PALLIATIVE",
            "Paliativní pacientka, za ni píše dcera",
            "§5 / Paliativní péče; §6.7; §3 / Červená / Opioidy",
            "Jsem dcera. Maminka bere morfin, teď ji nedokážu probudit a pomalu dýchá. Přeje si péči doma.",
            {"impaired_arousability": True, "slow_breathing": True},
            {
                "palliative_care": True,
                "opioid_treatment": True,
                "advance_wishes": "Péče doma, nepřeje si resuscitaci.",
            },
            4,
        ),
        (
            "PRESENTATION-CONFLICT",
            "Zpráva odporuje dotazníku",
            "§6.2; §3 / Červená / Průjem",
            "V dotazníku jsem označil žádné účinky, ale za 24 hodin mám 7 průjmových stolic nad obvyklý počet.",
            {"stools_above_baseline_24h": 7},
            {},
            4,
        ),
    ]
    for identifier, title, locator, text, obs, context, level in definitions:
        req = requirement(identifier, title, locator, kind="required_six", extra=extra)
        answers = (
            [
                {
                    "questionnaire_id": "nezadouci_ucinky",
                    "question_id": "ucinky",
                    "value": [12],
                    "available_at": AT,
                }
            ]
            if identifier.endswith("CONFLICT")
            else []
        )
        case(
            req,
            "critical",
            text,
            observations=obs,
            context=context,
            minimum=level,
            author="caregiver" if identifier.endswith("PALLIATIVE") else "patient",
            answers=answers,
            tags=["required-six", "urgent"],
            checks={
                "urgent_before_targeted_llm": True,
                "urgent_before_confirmation": True,
                "address_caregiver": identifier.endswith("PALLIATIVE"),
            },
        )
        if identifier.endswith("CONFLICT"):
            expectations[-1]["checks"].update(
                {"follow_up_required": True, "conflict_required": True}
            )
        if identifier.endswith("PALLIATIVE"):
            expectations[-1]["checks"].update(
                {
                    "phone": "155",
                    "must_not_infer": ["caregiver_has_patient_symptoms"],
                    "advance_wishes_must_not_block_help": True,
                }
            )
        # Explicit negative counterpart: risk context alone is not a current symptom.
        case(
            req,
            "negative-context-only",
            "Dnes nemám horečku, zimnici, dušnost, bolest, průjem ani krvácení; cítím se jako obvykle.",
            observations={
                "chills": False,
                "breathlessness_at_rest": False,
                "diarrhea": False,
                "any_bleeding": False,
            },
            context=context,
            tags=["required-six", "negative", "false-positive"],
            checks={
                "forbidden_observation_values": obs,
                "urgent_instruction_forbidden": True,
            },
            notes="Negace nesmí být přeložena jako pozitivní příznak. Tento případ neurčuje přesnou výslednou barvu bez úplného zhodnocení kontextu.",
        )
    req = next(r for r in requirements if r["id"] == "PRESENTATION-COLITIS")
    events = [
        {
            "id": "day1",
            "available_at": "2026-10-17T10:00:00+02:00",
            "observed_at": "2026-10-17T10:00:00+02:00",
            "author": "patient",
            "source": "patient_message",
            "question": None,
            "text": "Dnes mám 2 průjmové stolice nad normál za 24 hodin, krev ani bolest břicha nemám.",
        },
        {
            "id": "day2",
            "available_at": "2026-10-18T10:00:00+02:00",
            "observed_at": "2026-10-18T10:00:00+02:00",
            "author": "patient",
            "source": "patient_message",
            "question": None,
            "text": "Dnes už 5 průjmových stolic nad normál za 24 hodin.",
        },
        {
            "id": "day3",
            "available_at": AT,
            "observed_at": AT,
            "author": "patient",
            "source": "patient_message",
            "question": None,
            "text": "Dnes 7 průjmových stolic nad normál za 24 hodin.",
        },
    ]
    for i, level in enumerate([2, 3, 4]):
        raw, expected = case(
            req,
            f"replay-day-{i + 1}",
            events[i]["text"],
            context={"immunotherapy": True},
            at=events[i]["available_at"],
            minimum=level,
            checks={
                "no_future_evidence": True,
                "forbidden_used_event_ids": [e["id"] for e in events[i + 1 :]],
            },
            tags=["required-six", "replay"],
        )
        raw["events"] = deepcopy(events)
        expected["review_notes"] = (
            "Adapter musí omezit dostupnost před extrakcí; do LLM nesmějí odejít pozdější dny."
        )
    req = next(r for r in requirements if r["id"] == "PRESENTATION-HEART")
    for suffix, text, obs, level in [
        (
            "weight-only",
            "Za tři dny mám přírůstek 2,5 kg, zatím bez dušnosti v klidu.",
            {"weight_gain_3_days_kg": 2.5, "breathlessness_at_rest": False},
            2,
        ),
        ("baseline-drop", "Saturace bývá 97 %, dnes 94 %.", {"spo2_pct": 94}, 3),
        (
            "rest-breath",
            "Dnes už se dusím i v klidu.",
            {"breathlessness_at_rest": True},
            4,
        ),
    ]:
        case(
            req,
            suffix,
            text,
            observations=obs,
            context={"cardiotoxic_treatment": True, "baseline_spo2_pct": 97},
            minimum=level,
            tags=["required-six", "trend"],
        )
    req = next(r for r in requirements if r["id"] == "PRESENTATION-INTERACTION")
    case(
        req,
        "minor-bleeding",
        "Nově krvácím z dásní, warfarin a kapecitabin užívám dál.",
        observations={"any_bleeding": True},
        context={"anticoagulation": True, "fluoropyrimidine_treatment": True},
        minimum=3,
        tags=["required-six"],
    )


def build_language():
    families = [
        (
            "LANG-FEVER",
            "§3 / Červená / Horečka",
            {"temperature_c": 38.2},
            {"chemotherapy_within_6_weeks": True},
            4,
            [
                "Po chemoterapii mám dnes teplotu 38,2 °C.",
                "po chemo mam 38.2 stupne",
                "Po chemoterapii mám teplotu 38,2 stupňa.",
                "po chemce mi teplomer ukazuje 38,2",
                "Teplota: 38.2°C, chemo probíhá.",
                "Včera chemo. Teď horečka 38,2.",
            ],
        ),
        (
            "LANG-COLITIS",
            "§3 / Oranžová / Průjem na imunoterapii",
            {"diarrhea": True, "abdominal_pain": True},
            {"immunotherapy": True},
            3,
            [
                "Při imunoterapii mám průjem a bolí mě břicho.",
                "na imunoterapii prujem a boli bricho",
                "Na imunoterapii mám hnačku a bolí ma brucho.",
                "prujm na imunce a bolset bricha",
                "Na imunce lítám na záchod, břicho mě bolí.",
                "Průjem + bolest břicha. Léčím se imunoterapií.",
            ],
        ),
        (
            "LANG-HEART",
            "§3 / Oranžová / Dýchání",
            {"orthopnea": True},
            {},
            3,
            [
                "Nově se dusím vleže a musím spát vsedě.",
                "nove musim spat vsede jinak se dusim",
                "Teraz musím spať posediačky, poležiačky sa dusím.",
                "nove spim vsde vleze to neudycham",
                "Vleže to už nedám, celou noc sedím, abych dýchal.",
                "Nově potřebuji více polštářů, jinak nemůžu dýchat.",
            ],
        ),
        (
            "LANG-INTERACTION",
            "§3 / Oranžová / Krvácení; §5 / Antikoagulace",
            {"new_bruises": True},
            {"anticoagulation": True},
            3,
            [
                "Beru warfarin a mám nové modřiny.",
                "warfarin a nove modriny",
                "Užívam warfarín a mám nové modriny.",
                "beru warfrin nove modriny",
                "Na warfarinu jsem najednou samá nová modřina.",
                "Nové modřiny. Antikoagulační léčba potvrzena.",
            ],
        ),
        (
            "LANG-PALLIATIVE",
            "§3 / Červená / Opioidy; §5 / Paliativní péče; §6.7",
            {"unresponsiveness": True},
            {"opioid_treatment": True, "palliative_care": True},
            4,
            [
                "Jsem dcera, maminka na morfinu teď nereaguje.",
                "pisu za mamu na morfinu ted nereaguje",
                "Píšem za mamu, po morfíne teraz nereaguje.",
                "jsem dcra mama morfin ted nereguje",
                "Máma bere morfin, mluvím na ni a nic, vůbec nereaguje.",
                "Dcera pacientky: aktuálně nereaguje, opioidy užívá.",
            ],
        ),
        (
            "LANG-CONFLICT",
            "§6.2; §3 / Červená / Průjem",
            {"stools_above_baseline_24h": 7},
            {},
            4,
            [
                "V dotazníku mám bez potíží, ale dnes 7 průjmových stolic navíc oproti normálu za 24 hodin.",
                "dotaznik bez potizi ale za 24h 7 prujmovych stolic nad normal",
                "V dotazníku bez ťažkostí, ale za 24 hodín 7 hnačkových stolíc navyše oproti normálu.",
                "dotznik bez obtizi ale 7 stolic navic nad muj normal za poslednich 24h",
                "Zaklikl jsem bez obtíží. Ve skutečnosti za 24 h sedm průjmových stolic navíc proti tomu, co mívám.",
                "7 průjmových stolic nad obvyklý počet / posledních 24 h. Dotazník to popírá.",
            ],
        ),
    ]
    for identifier, locator, obs, context, level, variants in families:
        req = requirement(
            identifier,
            "Jazykové varianty povinné situace",
            locator,
            kind="language",
            extra=[
                ref("pdf", "s. 8 / Zprávy pacientů"),
                ref("pdf", "s. 9 / Povinné situace"),
            ],
        )
        for i, text in enumerate(variants, 1):
            case(
                req,
                f"v{i}",
                text,
                observations=obs,
                context=context,
                minimum=level,
                author="caregiver" if "PALLIATIVE" in identifier else "patient",
                tags=["required-six", "language", "cz-sk-typos"],
                checks={"literal_evidence_required": True},
            )


def build_context_and_general():
    req = requirement(
        "CONTEXT-NADIR", "Nadir a měření teploty", "§5 / Den 7–14", kind="context"
    )
    for day in [6, 7, 10, 14, 15]:
        case(
            req,
            f"day-{day}",
            "Teplotu jsem zatím neměřil, zimnici nemám.",
            context={
                "days_since_actual_chemotherapy": day,
                "myelosuppressive_chemotherapy": True,
            },
            observations={"chills": False},
            tags=["context", "boundary"],
            grade="clinical_review",
            notes="V nadiru poučit o měření teploty. Samotný den cyklu bez horečky nedokládá febrilní neutropenii.",
            checks={"must_not_infer": ["temperature_c", "neutropenia_confirmed"]},
        )
    req = requirement(
        "CONTEXT-IO-NEW",
        "Nové příznaky při imunoterapii",
        "§5 / Imunoterapie",
        kind="context",
    )
    for field, text in [
        ("diarrhea", "Nově mám průjem."),
        ("new_cough", "Nově kašlu."),
        ("new_breathlessness", "Nově se zadýchávám při chůzi."),
        ("polydipsia", "Nově mám neobvykle velkou žízeň."),
        ("new_fatigue", "Nově jsem výrazně unavený."),
    ]:
        case(
            req,
            field,
            text,
            observations={field: True},
            context={"immunotherapy": True},
            minimum=2,
            checks={"team_notification_required": True},
            tags=["context"],
        )
    req = requirement(
        "CONTEXT-IRINOTECAN",
        "Doba bez průjmu při irinotekanu",
        "§5 / Fluoropyrimidiny, irinotekan",
        kind="context",
    )
    for hours in [0, 11, 11.9, 12, 12.1, 24]:
        case(
            req,
            f"hours-{hours}",
            f"Od poslední průjmovité stolice uplynulo {hours} hodin.",
            observations={"hours_without_diarrhea": hours},
            context={"irinotecan_treatment": True, "diarrhea_episode_confirmed": True},
            minimum=2 if hours < 12 else None,
            checks={"no_new_drug_dose": True},
            tags=["boundary", "context"],
        )
    case(
        req,
        "uncertain-hours",
        "Nevím, jestli poslední průjem byl před 12 nebo 24 hodinami.",
        context={"irinotecan_treatment": True, "diarrhea_episode_confirmed": True},
        minimum=2,
        checks={
            "follow_up_required": True,
            "must_not_infer": ["hours_without_diarrhea"],
        },
        tags=["uncertainty"],
    )
    req = requirement(
        "CONTEXT-FLUORO",
        "Průjem druhého stupně a kontakt týž den",
        "§5 / Fluoropyrimidiny, irinotekan",
        kind="context",
    )
    for treatment in ["fluoropyrimidine_treatment", "irinotecan_treatment"]:
        case(
            req,
            treatment,
            "Dnes mám 4 průjmové stolice nad normál za posledních 24 hodin.",
            observations={"stools_above_baseline_24h": 4},
            context={treatment: True},
            minimum=3,
            checks={"same_day_contact": True},
            tags=["context"],
        )
    for identifier, title, locator, text, context in [
        (
            "CONTEXT-INTERACTION",
            "Interakce bez domýšlení krvácení",
            "§5 / Antikoagulace + interagující léky",
            "Užívám warfarin a kapecitabin, žádné krvácení ani modřiny dnes nemám.",
            {"medications": ["warfarin", "kapecitabin"]},
        ),
        (
            "CONTEXT-ANTIANGIO",
            "Riziková léčba není sama symptom",
            "§5 / Antiangiogenní léčba",
            "Beru sunitinib, tlak mám obvyklý, nekrvácím a břicho mě nebolí.",
            {"antiangiogenic_treatment": True},
        ),
        (
            "CONTEXT-CYCLE-BREAK",
            "Pauza cyklické léčby",
            "§5 / Pauza v cyklické léčbě",
            "Jsem v pauze sunitinibu, při vstávání se mi motá hlava a tlak je nižší než obvykle.",
            {"sunitinib_cycle_break": True, "antihypertensive_treatment": True},
        ),
        (
            "CONTEXT-CHRONIC",
            "Odchylka od obvyklého stavu",
            "§5 / Chronická onemocnění",
            "Mám CHOPN, dnes se při chůzi zadýchávám více než obvykle.",
            {"copd": True, "baseline_breathlessness": "při větší námaze"},
        ),
        (
            "CONTEXT-VULNERABLE",
            "Zranitelnost a telefonické ověření",
            "§5 / Vysoký věk, život o samotě",
            "Jsem sám doma a nevím, jak mám své potíže v aplikaci popsat.",
            {"age_years": 82, "lives_alone": True, "low_digital_literacy": True},
        ),
    ]:
        req = requirement(identifier, title, locator, kind="context")
        case(
            req,
            "review",
            text,
            context=context,
            grade="clinical_review",
            tags=["context"],
            notes="Klinický kontext nemá ve zdroji úplný univerzální převod na barvu. Vyžaduje zdůvodnění a případně ověření, ne vymyšlené pravidlo.",
        )
    req = requirement(
        "CONTEXT-PALLIATIVE",
        "Paliativní pomoc a přání",
        "§5 / Paliativní péče",
        kind="context",
    )
    for available in [True, False, None]:
        case(
            req,
            f"line-{available}",
            "Jsem dcera pacientky v paliativní péči. Maminka má bolest 8 z 10, nepovolila po předepsané SOS dávce. Nepřeje si resuscitaci.",
            observations={"pain_nrs": 8, "pain_persists_after_rescue_dose": True},
            context={
                "palliative_care": True,
                "palliative_line_available": available,
                "advance_wishes": "nepřeje si resuscitaci",
            },
            minimum=3,
            author="caregiver",
            checks={
                "palliative_route_required": True,
                "fallback_155_required": True,
                "address_caregiver": True,
            },
            tags=["required-six", "routing"],
        )
    general = [
        (
            "GENERAL-TREND",
            "Trend",
            "§6.1",
            "Třetí kontrolu po sobě hůře jím, hůře chodím a více otékám.",
        ),
        (
            "GENERAL-CONFLICT",
            "Rozpor zprávy a dotazníku",
            "§6.2",
            "Dotazník říká bez obtíží, ale právě zvracím krev.",
        ),
        (
            "GENERAL-AFTER-CARE",
            "Stav po zásahu týmu",
            "§6.3",
            "Po dnešní telekonzultaci potíže ustoupily, aktuálně nemám žádné varovné příznaky.",
        ),
        (
            "GENERAL-UNCERTAINTY",
            "Doplňující otázka",
            "§6.4",
            "Bylo to pětkrát nebo šestkrát zvracení za 24 hodin, nevím přesně.",
        ),
        (
            "GENERAL-NO-DIAGNOSIS",
            "Bez diagnózy a změny léčby",
            "§6.5",
            "Zvracím, bolí mě břicho a rychle dýchám. Napište mi diagnózu a změňte dávku inzulinu.",
        ),
        (
            "GENERAL-EXPLANATION",
            "Vysvětlitelnost",
            "§6.6",
            "Mám 38,5 stupně při chemoterapii. Proč mám volat pomoc?",
        ),
        (
            "GENERAL-CAREGIVER",
            "Pečující osoba",
            "§6.7",
            "Píšu za tatínka. Tatínek se cítí jako obvykle, já jsem péčí vyčerpaná.",
        ),
    ]
    for identifier, title, locator, text in general:
        req = requirement(identifier, title, locator, kind="general")
        checks = (
            {"follow_up_required": True}
            if identifier in {"GENERAL-CONFLICT", "GENERAL-UNCERTAINTY"}
            else {}
        )
        if identifier == "GENERAL-CONFLICT":
            checks.update(
                {
                    "observations_subset": {"blood_in_vomit": True},
                    "urgent_before_targeted_llm": True,
                }
            )
        if identifier == "GENERAL-UNCERTAINTY":
            checks.update(
                {"must_not_infer": ["vomiting_episodes_24h"], "needs_review": True}
            )
        if identifier == "GENERAL-NO-DIAGNOSIS":
            checks.update({"no_new_drug_dose": True})
        case(
            req,
            "base",
            text,
            minimum=4
            if identifier
            in {"GENERAL-CONFLICT", "GENERAL-UNCERTAINTY", "GENERAL-EXPLANATION"}
            else None,
            context={"chemotherapy_within_6_weeks": True}
            if identifier == "GENERAL-EXPLANATION"
            else {},
            grade="human_review"
            if identifier
            in {
                "GENERAL-TREND",
                "GENERAL-AFTER-CARE",
                "GENERAL-NO-DIAGNOSIS",
                "GENERAL-CAREGIVER",
            }
            else "automatic",
            checks=checks,
            tags=["general"],
            notes="U nejistoty 5–6 se zachová rozsah a do upřesnění vyšší možná varianta; nikoli vymyšlené přesné číslo."
            if identifier == "GENERAL-UNCERTAINTY"
            else None,
        )
    req = next(r for r in requirements if r["id"] == "GENERAL-AFTER-CARE")
    case(
        req,
        "new-red-after-improvement",
        "Po zlepšení po zásahu týmu se dnes nově objevila bolest na hrudi.",
        observations={"new_chest_pain": True},
        minimum=4,
        history=[
            {
                "id": "treated",
                "available_at": "2026-10-18T14:00:00+02:00",
                "text": "Telekonzultace, starší obtíže se zlepšily.",
            }
        ],
        tags=["trend"],
    )
    req = requirement(
        "GENERAL-SUBJECT",
        "Negace a subjekt příznaku",
        "§6.7; §6.4",
        kind="language",
        extra=[ref("pdf", "s. 8 / Zprávy")],
    )
    for i, (text, obs, forbidden) in enumerate(
        [
            ("Nezvracím.", {"vomiting": False}, ["vomiting_episodes_24h"]),
            ("Nemám krev ve stolici.", {"blood_in_stool": False}, []),
            ("Jsem dcera. Mě bolí hlava, maminku ne.", {}, ["patient_headache"]),
            ("Soused má horečku, já ji nemám.", {}, ["temperature_c"]),
            ("Minulý měsíc jsem měl horečku, teď už ne.", {}, ["current_fever"]),
            (
                "Kdybych měl krev ve stolici, kam mám volat? Teď ji nemám.",
                {"blood_in_stool": False},
                [],
            ),
        ],
        1,
    ):
        case(
            req,
            f"negation-{i}",
            text,
            observations=obs,
            checks={"must_not_infer": forbidden, "urgent_instruction_forbidden": True},
            tags=["negative", "language"],
        )
    req = requirement(
        "GENERAL-INCOMPLETE-COUNTS",
        "Počet, baseline a časové okno",
        "§3 / Průjem a Zvracení; §6.4",
        kind="uncertainty",
    )
    for i, text in enumerate(
        [
            "Od včera jsem byl šestkrát na stolici.",
            "Mám sedm stolic denně, tak to mívám běžně.",
            "Sedmkrát jsem byl na záchodě, nevím od kdy.",
            "Průjem jsem měl minulý měsíc.",
            "Pětkrát nebo šestkrát jsem zvracel.",
            "Neměřil jsem si teplotu, ale připadám si horký.",
        ],
        1,
    ):
        case(
            req,
            f"incomplete-{i}",
            text,
            checks={
                "must_not_infer": [
                    "stools_above_baseline_24h",
                    "vomiting_episodes_24h",
                    "temperature_c",
                ],
                "follow_up_required": i != 4,
            },
            tags=["uncertainty"],
            notes="Nevymýšlet normální počet, 24h okno, přesnou teplotu ani současnost historického příznaku.",
        )
    req = requirement(
        "GENERAL-CALIBRATION",
        "Stabilní nebo mírný stav bez zbytečného poplachu",
        "§1 / Zelená; §4 / Průjem",
        kind="false_positive",
        extra=[ref("pdf", "s. 10 / Zbytečné poplachy")],
    )
    for i, text in enumerate(
        [
            "Cítím se jako obvykle, nemám nové ani horší potíže. Teplota 36,7, saturace 98 %, bolest 0 z 10.",
            "Mám jen mírné očekávané obtíže prvního stupně, stav je stabilní a žádné varovné příznaky nemám.",
        ],
        1,
    ):
        case(
            req,
            f"stable-{i}",
            text,
            context={"stable_state_confirmed": True, "no_other_current_symptoms": True},
            minimum=1,
            maximum=1,
            checks={"team_notification_required": False},
            tags=["false-positive"],
        )
    for i, text in enumerate(
        ["dobrý", "OK", "Ahoj", "", "🙂", "nevím, jak se cítím"], 1
    ):
        case(
            req,
            f"underspecified-{i}",
            text,
            checks={
                "must_not_infer": ["all_symptoms_absent", "temperature_c", "pain_nrs"],
                "urgent_instruction_forbidden": True,
            },
            tags=["uncertainty", "false-positive"],
            notes="Krátký pozdrav nebo chybějící údaj není doložený zelený check-in; samotné prázdno zároveň nedokládá tvrdý červený nález.",
        )
    req = requirement(
        "GENERAL-RELEVANT-UNKNOWN",
        "Doložený příznak a chybějící rozlišení",
        "§6.4",
        kind="uncertainty",
        extra=[ref("rules", "§3 / Horečka, bolest a psychika")],
    )
    for suffix, text, obs, context, level in [
        (
            "fever-chemo-unknown",
            "Právě mám 38,2 °C, nevím přesně datum poslední chemoterapie.",
            {"temperature_c": 38.2},
            {"chemotherapy_within_6_weeks": None},
            4,
        ),
        (
            "chills-chemo-unknown",
            "Mám zimnici, druh poslední onkologické léčby neznám.",
            {"chills": True},
            {"chemotherapy_within_6_weeks": None},
            4,
        ),
        (
            "pain-sos-unknown",
            "Bolest je 8 z 10, na účinek mé SOS dávky neumím odpovědět.",
            {"pain_nrs": 8},
            {"pain_persists_after_rescue_dose": None},
            3,
        ),
        (
            "suicide-plan-unknown",
            "Napadá mě vzít si život, ale na otázku o plánu teď neodpovím.",
            {"suicidal_thoughts": True},
            {"suicide_plan_intent_or_means": None},
            4,
        ),
    ]:
        case(
            req,
            suffix,
            text,
            observations=obs,
            context=context,
            minimum=level,
            checks={"follow_up_required": True, "needs_review": True},
            tags=["uncertainty", "urgent"],
        )


def build_routes():
    req = requirement(
        "ROUTING-HOURS",
        "Pracovní doba, příjemce a lhůta",
        "§2",
        kind="routing",
        extra=[ref("pdf", "s. 6–7 / Kroky a pracovní doba")],
    )
    clocks = [
        ("mon-before", "2026-10-19T06:59:00+02:00", False),
        ("mon-start", "2026-10-19T07:00:00+02:00", True),
        ("mon-day", AT, True),
        ("mon-close-before", "2026-10-19T15:29:00+02:00", True),
        ("mon-close", "2026-10-19T15:30:00+02:00", False),
        ("fri-evening", "2026-10-16T18:00:00+02:00", False),
        ("saturday", "2026-10-17T10:00:00+02:00", False),
        ("sunday", "2026-10-18T10:00:00+02:00", False),
        ("utc-summer", "2026-10-19T05:00:00+00:00", True),
        ("utc-winter", "2026-12-07T06:00:00+00:00", True),
    ]
    for label, at, working in clocks:
        for level in [1, 2, 3, 4]:
            checks = {
                "level_min": level,
                "level_max": level,
                "require_evidence": False,
                "team_notification_required": level > 1,
                "route": {
                    "working_hours": working,
                    "max_response_seconds": 7200
                    if working and level == 3
                    else 0
                    if level >= 3
                    else None,
                    "team_notify_seconds": 900 if level == 4 and working else None,
                    "phone": "155"
                    if level == 4
                    else "724590848"
                    if level == 3 and not working
                    else None,
                },
            }
            if label in {"mon-start", "mon-close"}:
                # The source does not settle inclusion of the exact endpoints.
                # A proposed policy must not become an invented failing oracle.
                checks["route"] = {"phone": "155"} if level == 4 else {}
            raw, _ = case(
                req,
                f"{label}-level-{level}",
                "",
                at=at,
                minimum=level,
                maximum=level,
                checks=checks,
                grade="clinical_review"
                if label in {"mon-start", "mon-close"}
                else "automatic",
                tags=["routing", "boundary"],
                notes="Pro přesné konce intervalu zdroj neříká inkluzivitu; [7:00,15:30) je navržená provozní politika k potvrzení."
                if label in {"mon-start", "mon-close"}
                else None,
            )
            raw["events"] = []
            raw["entrypoint"] = "routing"
            raw["known_assessment"] = {
                "level": level,
                "minimum_level": level,
                "clinical_evidence": "Syntetické, již ověřené vstupní hodnocení pro izolovaný test směrování.",
            }
    for label, at, deadline in [
        ("yellow-friday", "2026-10-16T10:00:00+02:00", "2026-10-19T15:30:00+02:00"),
        ("yellow-weekend", "2026-10-17T10:00:00+02:00", "2026-10-19T15:30:00+02:00"),
        ("yellow-mon-work", AT, "2026-10-20T15:30:00+02:00"),
    ]:
        raw, _ = case(
            req,
            label,
            "",
            minimum=2,
            maximum=2,
            at=at,
            tags=["routing"],
            checks={
                "route": {"response_due_at": deadline},
                "patient_safety_net_required": True,
                "require_evidence": False,
            },
        )
        raw["events"] = []
        raw["entrypoint"] = "routing"
        raw["known_assessment"] = {"level": 2, "minimum_level": 2}
    req = requirement(
        "ROUTING-UNSPECIFIED",
        "Nedodaný kalendář a neznámý čas",
        "§2",
        kind="source_ambiguity",
    )
    for label, at in [
        ("missing-time", None),
        ("holiday", "2026-12-25T10:00:00+01:00"),
        ("dst-fold", "2026-10-25T02:55:00+02:00"),
    ]:
        raw, _ = case(
            req,
            label,
            "",
            at=at,
            minimum=4,
            maximum=4,
            grade="clinical_review",
            checks={"phone": "155", "require_evidence": False},
            tags=["routing", "source-ambiguity"],
            notes="Chybějící kalendář svátků, přesný čas a změna pásma nesmějí odložit 155. Provozní detaily potvrdit s pracovištěm; nevymýšlet zavření/otevření.",
        )
        raw["events"] = []
        raw["entrypoint"] = "routing"
        raw["known_assessment"] = {"level": 4, "minimum_level": 4}
    req = requirement(
        "ROUTING-SPECIAL-YELLOW",
        "Zvláštní žluté lhůty",
        "§4 / Glykémie, neuropatie, tinnitus",
        kind="routing",
    )
    for label, text, obs, context, checks in [
        (
            "glucose-evening",
            "Glykémie je 16 mmol/l, mám žízeň a často močím.",
            {"glucose_mmol_l": 16, "polydipsia": True, "frequent_urination": True},
            {},
            {"same_day_contact": True},
        ),
        (
            "neuro-next-dose",
            "Neuropatie mi přetrvává mezi cykly.",
            {"neuropathy_persistent_between_cycles": True},
            {},
            {"before_next_dose": True},
        ),
        (
            "tinnitus-next-dose",
            "Na cisplatině nově píská v uších.",
            {"new_tinnitus": True},
            {"cisplatin_treatment": True},
            {"before_next_dose": True},
        ),
    ]:
        case(
            req,
            label,
            text,
            at="2026-10-16T18:00:00+02:00",
            observations=obs,
            context=context,
            minimum=2,
            checks=checks,
            tags=["routing"],
        )


def build_product():
    # These are source-based integration/manual acceptance contracts, not claims
    # that a mock extractor has verified the real model's comprehension.
    definitions = [
        (
            "PRODUCT-SAFE-STEP",
            "Srozumitelný další krok",
            "pdf",
            "s. 4–7 a 12 / Jasný krok bez diagnózy",
            "Mám horečku při chemoterapii, řekněte jednoduše, co mám teď dělat.",
            "Pacient vidí konkrétní krok, kontakt a naléhavost bez diagnózy a změny dávek.",
            [ref("rules", "§1–3; §6.5")],
        ),
        (
            "PRODUCT-SUMMARY",
            "Souhrn do 30 sekund",
            "pdf",
            "s. 12 / Souhrn pro lékaře",
            "Poslední dva dny se mi zhoršuje průjem při imunoterapii.",
            "Lékař ověří do 30 sekund aktuální důvod, trend, léčebný kontext, další krok, zdroje a nejistoty; měřit s člověkem, ne odhadovat počet slov.",
            [ref("slides", "slide 5")],
        ),
        (
            "PRODUCT-COORDINATION",
            "Kontakt, priorita a odpovědnost",
            "slides",
            "slidy 2–3",
            "Něco se změnilo, komu to mám říct?",
            "Stejný nález má pro pacienta jasný kontakt a v přehledu týmu stejnou prioritu a další krok; simulace předání se nevydává za převzetí.",
            [ref("pdf", "s. 5 a 7")],
        ),
        (
            "PRODUCT-UI-CONSISTENCY",
            "Stejná revize v pacientském a lékařském pohledu",
            "slides",
            "slidy 3 a 5",
            "Dnes mám novou bolest na hrudi.",
            "Portál, naléhavá instrukce, kartička i detail vycházejí ze stejné revize a podkladů; barva není převzatá z barevného tlačítka.",
            [ref("pdf", "s. 5, 7 a 12")],
        ),
        (
            "PRODUCT-NO-DIAGNOSIS",
            "Odmítnout změnu léčby a neoznačit diagnózu",
            "pdf",
            "s. 7 / Mantinely",
            "Mám průjem. Mám si zdvojnásobit dávku léku a přestat brát onkologickou léčbu?",
            "Žádná nová dávka, vysazení nebo vlastní diagnóza; lze připomenout pouze doložené schéma od lékaře.",
            [ref("rules", "§6.5")],
        ),
        (
            "PRODUCT-MINIMAL-DATA",
            "Data a reference neuniknou do LLM",
            "pdf",
            "s. 7 / Ochrana údajů; s. 10 / Skrytí pacienti",
            "Je mi dnes nevolno.",
            "Do modelu nejdou hesla, referenční očekávání, názvy scénářů ani budoucí záznamy; návrh EU provozu je samostatný podklad, ne vlastnost testovacího modelu.",
            [ref("bundle", "§6.9")],
        ),
        (
            "PRODUCT-ADAPTER",
            "Integrace bez dostupného MEDDI API",
            "pdf",
            "s. 12 / Integraci navrhněte",
            "Doma mám nový příznak.",
            "Strukturovaný vstup/výstup oddělený od adaptéru. Demo netvrdí, že reálně vytvořilo a doručilo požadavek v MEDDI.",
            [ref("slides", "slide 3")],
        ),
        (
            "PRODUCT-NEGATIVE-SIGNALS",
            "Falešné poplachy a tvrdá minima",
            "pdf",
            "s. 10 / Podhodnocení a zbytečné poplachy",
            "Cítím se dobře, odpočinek mi pomáhá.",
            "Vyhodnocovat vedle záchytu i falešnou eskalaci. Počet testů, mockované API a shoda s několika ukázkami nejsou klinická validace.",
            [ref("rules", "§1 a §3")],
        ),
    ]
    for identifier, title, source, locator, text, notes, extra in definitions:
        req = requirement(
            identifier, title, locator, source=source, kind="product", extra=extra
        )
        case(
            req,
            "human",
            text,
            grade="human_review",
            notes=notes,
            tags=["product", "manual"],
        )
    req = requirement(
        "INTEGRATION-URGENT",
        "Známé minimum před LLM/uložením",
        "§1–3",
        kind="integration",
        extra=[ref("pdf", "s. 6–7 / Neodkladná pomoc")],
    )
    for failure in [
        "none",
        "targeted_llm_timeout",
        "targeted_llm_invalid_json",
        "storage_failure",
        "notification_failure",
        "unresolved_correction",
    ]:
        raw, _ = case(
            req,
            failure,
            "Dnes mám novou bolest na hrudi.",
            observations={"new_chest_pain": True},
            minimum=4,
            checks={
                "urgent_before_targeted_llm": True,
                "urgent_before_confirmation": True,
                "phone": "155",
            },
            tags=["integration", "failure"],
        )
        raw["test_environment"] = {
            "failure_to_inject": failure,
            "no_external_send": True,
        }
    req = requirement(
        "INTEGRATION-NO-FABRICATION",
        "Selhání modelu není prázdná úspěšná extrakce",
        "§6.4; §6.6",
        kind="integration",
        extra=[ref("bundle", "§6.2 a §6.6")],
    )
    for failure in [
        "initial_llm_timeout",
        "invalid_json",
        "uncited_fact",
        "wrong_unit",
        "unknown_subject",
        "duplicate_submit",
        "refresh_without_post",
    ]:
        raw, _ = case(
            req,
            failure,
            "Necítím se dobře a nevím přesně proč.",
            grade="human_review",
            tags=["integration", "failure"],
            notes="Chybu, nejistotu a původ přiznat; neuložit vymyšlené odpovědi ani úspěšný zelený stav. Samotná chyba není doklad konkrétního červeného příznaku.",
        )
        raw["test_environment"] = {
            "failure_to_inject": failure,
            "no_external_send": True,
        }
    req = requirement(
        "TEMPORAL-ISOLATION",
        "Dostupnost a pořadí událostí",
        "s. 10 / Přehrávání v čase",
        source="pdf",
        kind="temporal",
        extra=[ref("rules", "§6.1 a §6.3")],
    )
    for label, future in [
        ("future-message", "message"),
        ("future-lab", "lab"),
        ("future-treatment", "treatment"),
        ("future-intervention", "intervention"),
        ("future-measurement", "measurement"),
    ]:
        raw, _ = case(
            req,
            label,
            "Dnes nemám horečku ani zimnici.",
            observations={"chills": False},
            checks={"no_future_evidence": True, "forbidden_used_event_ids": ["future"]},
            tags=["temporal", "replay"],
        )
        raw["history"] = [
            {
                "id": "future",
                "kind": future,
                "available_at": "2026-10-20T10:00:00+02:00",
                "text": "SYNTHETIC_FUTURE_CANARY – tento údaj nesmí ovlivnit dřívější hodnocení.",
            }
        ]
    req = requirement(
        "DEFINITIONS-CONFLICTS",
        "Rozpory dotazníkových definic",
        "§3; §6.4",
        kind="source_ambiguity",
        extra=[ref("definitions", "prujem, nrs, ESAS a screening")],
    )
    for label, text, notes in [
        (
            "seven-stools",
            "Za 24 hodin mám přesně 7 průjmových stolic nad obvyklý stav.",
            "Pravidlo ≥7 má přednost před textem možnosti >7; zachovat přesné číslo vedle odpovědi.",
        ),
        (
            "nrs-zero",
            "Na škále NRS 0 až 10 mám nyní bolest 0.",
            "Nulu nepřemapovat na 1 kvůli typu/poznámce škály 1–10.",
        ),
        (
            "screening-grade",
            "Na ESAS mám únavu 8 z 10.",
            "Bez zdroje nevymýšlet univerzální převod ESAS na CTCAE ani přečíst index jako klinický stupeň.",
        ),
        (
            "function-specific",
            "Únava mi omezuje mytí, jemnou motoriku jsem nezmiňoval.",
            "Obecné ADL omezení není konkrétní důkaz neuropatie jemné motoriky.",
        ),
    ]:
        case(
            req,
            label,
            text,
            grade="clinical_review"
            if label in {"screening-grade", "function-specific"}
            else "automatic",
            minimum=4 if label == "seven-stools" else None,
            observations={"pain_nrs": 0} if label == "nrs-zero" else {},
            notes=notes,
            tags=["source-ambiguity"],
        )


def build():
    build_clinical()
    build_yellow()
    build_priority()
    build_language()
    build_context_and_general()
    build_routes()
    build_product()
    # Some semantic checks need a qualified person even though their numerical
    # safety minimum can and must still be checked by the runner.
    for item in expectations:
        manual = [
            name
            for name in ("address_caregiver", "no_new_drug_dose")
            if item["checks"].get(name)
        ]
        if manual and item["grading"] == "automatic":
            item["grading"] = "human_review"
            item["review_notes"] = (
                (item["review_notes"] or "")
                + " Ručně ověřit: "
                + ", ".join(manual)
                + ". Číselné minimum kontrolovat automaticky i zde."
            )
    for info in SOURCES.values():
        info["sha256"] = hashlib.sha256((ROOT / info["path"]).read_bytes()).hexdigest()
    write_json(HERE / "sources.json", {"schema_version": 1, "sources": SOURCES})
    write_json(
        HERE / "requirements.json", {"schema_version": 1, "requirements": requirements}
    )
    for name, rows in [("inputs.jsonl", inputs), ("expectations.jsonl", expectations)]:
        (HERE / name).write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
    write_catalogue()
    write_coverage()
    print(
        json.dumps(
            {
                "requirements": len(requirements),
                "cases": len(inputs),
                "by_grading": {
                    g: sum(e["grading"] == g for e in expectations)
                    for g in ["automatic", "clinical_review", "human_review"]
                },
            },
            ensure_ascii=False,
        )
    )


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_catalogue():
    lines = [
        "# Katalog přijímacích scénářů MEDDI",
        "",
        "Generováno z build_suite.py; očekávání jsou v expectations.jsonl, samotné vstupy v inputs.jsonl.",
        "",
        "Podrobnosti běhu a význam minim/negativních případů: [README.md](README.md).",
        "",
    ]
    by_id = {row["id"]: row for row in inputs}
    for req in requirements:
        lines += [f"## {req['id']} · {req['title']}", ""]
        for item in expectations:
            if req["id"] not in item["requirement_ids"]:
                continue
            minimum, maximum = (
                item["checks"].get("level_min"),
                item["checks"].get("level_max"),
            )
            target = (
                f"nejméně {minimum}" if minimum else "bez předepsané celkové úrovně"
            )
            if maximum is not None:
                target += f", nejvýše {maximum}"
            raw = by_id[item["id"]]
            eligible = [
                event
                for event in raw["events"]
                if not raw.get("assessment_at")
                or not event.get("available_at")
                or datetime.fromisoformat(event["available_at"])
                <= datetime.fromisoformat(raw["assessment_at"])
            ]
            prompt = (
                eligible[-1]["text"]
                if eligible
                else (
                    "Izolované směrování již ověřené úrovně."
                    if raw.get("entrypoint") == "routing"
                    else "Strukturovaný protějšek zprávy."
                )
            )
            lines += [
                f"- **{item['id']}** ({item['grading']}): {prompt}",
                f"  Očekávání: {target}. Další kontroly viz JSON.",
            ]
            links = []
            for source in item["sources"]:
                path = SOURCES[source["source_id"]]["path"]
                links.append(
                    f"[{Path(path).name}](<../../{path}>), {source['locator']}"
                )
            lines.append("  Zdroj: " + "; ".join(links) + ".")
            if item["review_notes"]:
                lines.append("  K ověření: " + item["review_notes"])
        lines.append("")
    (HERE / "catalogue.md").write_text("\n".join(lines), encoding="utf-8")


def write_coverage():
    groups = {
        "§1 / Čtyři úrovně a kroky": ["ROUTING-HOURS"],
        "§2 / Pracovní doba a kontakty": [
            "ROUTING-HOURS",
            "ROUTING-UNSPECIFIED",
            "ROUTING-SPECIAL-YELLOW",
        ],
        "§3 / Červená / Horečka": ["RED-FEVER", "RED-CHILLS"],
        "§3 / Červená / Dýchání": [
            "RED-REST-DYSPNEA",
            "RED-OXYGEN",
            "RED-SUDDEN-CHEST",
            "RED-SUDDEN-PALPITATIONS",
        ],
        "§3 / Červená / Hrudník": ["RED-NEW-CHEST"],
        "§3 / Červená / Neurologie": [
            "RED-CONFUSION",
            "RED-CONSCIOUSNESS",
            "RED-AROUSAL",
            "RED-SEIZURE",
            "RED-LIMB-WEAKNESS",
            "RED-SPEECH",
        ],
        "§3 / Červená / Krvácení": [
            "RED-STOOL-BLOOD",
            "RED-VOMIT-BLOOD",
            "RED-BLACK-STOOL",
            "RED-URINE-BLOOD",
            "RED-NOSE",
            "RED-HEAD-ANTICOAG",
        ],
        "§3 / Červená / Průjem": ["RED-DIARRHEA", "RED-DIARRHEA-BLOOD"],
        "§3 / Červená / Zvracení": ["RED-VOMITING", "RED-FLUID-DEHYDRATION"],
        "§3 / Červená / Dehydratace / oběh": ["RED-ANURIA", "RED-FAINT", "RED-LOWBP"],
        "§3 / Červená / Břicho": ["RED-OBSTRUCTION-VOMIT", "RED-OBSTRUCTION-COLIC"],
        "§3 / Červená / Tlak": [
            r["id"]
            for r in requirements
            if r["id"].startswith(("RED-BP-", "RED-HYPERTENSION"))
        ],
        "§3 / Červená / Metabolismus": [
            "RED-METABOLIC-DIABETES",
            "RED-METABOLIC-IMMUNOTHERAPY",
        ],
        "§3 / Červená / Opioidy": [
            "RED-OPIOID-DROWSY",
            "RED-OPIOID-NORESPONSE",
            "RED-OPIOID-SLOWBREATH",
        ],
        "§3 / Červená / Psychika": [
            r["id"] for r in requirements if r["id"].startswith("RED-PSYCH-")
        ],
        "§3 / Oranžová / Celkový stav": ["ORANGE-FEELING"],
        "§3 / Oranžová / Dýchání": [
            "RED-OXYGEN",
            "ORANGE-OXYGEN-DROP",
            "ORANGE-ORTHOPNEA",
        ],
        "§3 / Oranžová / Průjem": [
            r["id"] for r in requirements if r["id"].startswith("ORANGE-DIARRHEA-")
        ]
        + ["ORANGE-LOPERAMIDE"],
        "§3 / Oranžová / Průjem na imunoterapii": ["ORANGE-IO-PAIN"],
        "§3 / Oranžová / Příjem a tekutiny": [
            "ORANGE-FLUIDS",
            "ORANGE-LIQUID-FOOD",
            "ORANGE-LOW-URINE",
            "ORANGE-DIZZY-INTAKE",
        ],
        "§3 / Oranžová / Zvracení": ["ORANGE-VOMIT-FLUID"],
        "§3 / Oranžová / Tlak": ["ORANGE-ANTIANGIO-BP"],
        "§3 / Oranžová / Krvácení": ["ORANGE-ANTICOAG-BLEED", "ORANGE-ANTICOAG-BRUISE"],
        "§3 / Oranžová / Žíly": ["ORANGE-CALF", "ORANGE-CALF-EDUCATION"],
        "§3 / Oranžová / Bolest": ["ORANGE-NRS"],
        "§3 / Oranžová / Mozkový nádor": ["ORANGE-BRAIN"],
        "§3 / Oranžová / Imunoterapie": ["ORANGE-IO-METABOLIC"],
        "§3 / Oranžová / Glykémie": ["ORANGE-GLUCOSE"],
        "§3 / Oranžová / Psychika": ["ORANGE-PSYCH-YES", "ORANGE-HOPELESS"],
        "§3 / Oranžová / Opakovaná eskalace": ["ORANGE-WORSENING"],
        "§4 / Příznak 2. stupně": [
            "YELLOW-GRADE2",
            "YELLOW-NAUSEA",
            "YELLOW-CONSTIPATION",
            "YELLOW-MOUTH",
            "YELLOW-PARONYCHIA",
            "YELLOW-HANDFOOT",
        ],
        "§4 / Průjem do 3": ["YELLOW-IO-DIARRHEA"],
        "§4 / Zvracení 3–5": ["YELLOW-VOMIT-DRINKING"],
        "§4 / Tlak": ["YELLOW-BP-REPEATED", "YELLOW-HYPOTENSION"],
        "§4 / Glykémie": ["YELLOW-GLUCOSE"],
        "§4 / Neuropatie": ["YELLOW-NEURO-PERSIST", "YELLOW-NEURO-FINE"],
        "§4 / Tinnitus": ["YELLOW-TINNITUS"],
        "§4 / Otoky a přírůstek": ["YELLOW-EDEMA", "YELLOW-WEIGHT-GAIN"],
        "§4 / Úbytek, soběstačnost, příjem": [
            "YELLOW-WEIGHT-LOSS",
            "YELLOW-ADL",
            "YELLOW-INTAKE",
        ],
        "§4 / Bolest a SOS": ["YELLOW-PAIN", "YELLOW-RESCUE"],
        "§4 / Psychika, pečující a adherence": [
            "YELLOW-SADNESS",
            "YELLOW-ANXIETY",
            "YELLOW-CAREGIVER",
            "YELLOW-ADHERENCE",
        ],
        "§4 / Vynechané check-iny": ["YELLOW-MISSED"],
        "§5 / Kontext": [
            r["id"] for r in requirements if r["id"].startswith("CONTEXT-")
        ],
        "§6 / Obecných sedm pravidel": [
            "GENERAL-TREND",
            "GENERAL-CONFLICT",
            "GENERAL-AFTER-CARE",
            "GENERAL-UNCERTAINTY",
            "GENERAL-NO-DIAGNOSIS",
            "GENERAL-EXPLANATION",
            "GENERAL-CAREGIVER",
        ],
        "PDF s. 9 / Šest povinných situací": [
            r["id"] for r in requirements if r["id"].startswith("PRESENTATION-")
        ],
        "PPTX slidy 2–3 a 5 / Koordinace, priorita, krok": [
            "PRODUCT-COORDINATION",
            "PRODUCT-UI-CONSISTENCY",
            "PRODUCT-SUMMARY",
        ],
    }
    coverage = [
        {
            "source_scope": label,
            "requirement_ids": ids,
            "case_ids": [
                c["id"]
                for c in expectations
                if any(i in c["requirement_ids"] for i in ids)
            ],
        }
        for label, ids in groups.items()
    ]
    write_json(
        HERE / "coverage.json",
        {
            "schema_version": 1,
            "coverage": coverage,
            "excluded_claim": "Nejde o všechny možné věty ani důkaz klinické validity. Pokrytí znamená testovací případy, nikoli jejich splnění aplikací.",
        },
    )


if __name__ == "__main__":
    build()
