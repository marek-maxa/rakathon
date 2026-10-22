"""Actionable four-level disposition, separate from assessment completeness.

Sources: resources/triage_rules.md §1–2, §6.4 and §8.
Yellow review for unresolved current inputs is a conservative application policy,
not a diagnosis or a claim that the missing clinical mapping is implemented.
"""

from copy import deepcopy

from .routing import timed_route

RULES_SOURCE = "resources/triage_rules.md"
COLORS = ("green", "yellow", "orange", "red")
ACTIONS = {
    "green": (
        "dalsi_sledovani",
        "Další sledování; při nových nebo zhoršených potížích zdravotnický tým.",
        "Pokračujte ve sledování. Při nových nebo zhoršujících se potížích kontaktujte zdravotnický tým.",
    ),
    "yellow": (
        "kontaktovat_tym",
        "Monitorovací centrum MEDDI Onco v pracovní době Po–Pá 7:00–15:30; mimo ni následující pracovní den.",
        (
            "Kontaktujte monitorovací centrum MEDDI Onco a požádejte o posouzení. "
            "Vyřízení má proběhnout nejpozději do konce následujícího pracovního dne. "
            "Při rychlém zhoršení nečekejte: volejte sloužícího lékaře MOÚ 724 590 848, při akutním ohrožení 155."
        ),
    ),
    "orange": (
        "telekonzultace",
        "V pracovní době lékař MOÚ do 2 hodin; mimo pracovní dobu sloužící lékař MOÚ 724 590 848 ihned.",
        (
            "V pracovní době Po–Pá 7:00–15:30 kontaktujte monitorovací centrum kvůli telekonzultaci s lékařem do 2 hodin. "
            "Mimo pracovní dobu volejte ihned sloužícího lékaře MOÚ 724 590 848. Při akutním ohrožení volejte 155."
        ),
    ),
    "red": (
        "neodkladna_pomoc",
        "155 / urgentní příjem ihned.",
        "Volejte ihned 155 nebo vyhledejte urgentní příjem. Nečekejte na odpověď v aplikaci.",
    ),
}


def resolve_disposition(
    assessment: dict, *, needs_clinical_review: bool, at=None, palliative_care=None
) -> dict:
    """Keep the clinical minimum; unresolved current inputs get human review.

    Callers decide whether uncertainty concerns actual supplied inputs. A skipped
    hypothetical rule alone is not evidence of a problem. No notification is
    sent by this pure function; upozornit_tym specifies the required action.
    """
    result = deepcopy(assessment)
    result["reasons"] = [
        reason
        for reason in result.get("reasons", [])
        if reason["rule_id"] != "clinical_review_required"
    ]
    minimum = result.get("minimum_color", result.get("color"))
    needs_clinical_review = needs_clinical_review or minimum is None
    level = COLORS.index(minimum) + 1 if minimum is not None else 1
    if needs_clinical_review and level < 2:
        level = 2
        result.setdefault("reasons", []).append(
            {
                "rule_id": "clinical_review_required",
                "color": "yellow",
                "message": "Aktuální údaje nelze spolehlivě posoudit automaticky. Je potřeba posouzení zdravotnickým týmem.",
                "source": f"{RULES_SOURCE}, §1 / Žlutá, §6.4; resources/triage_rules.md, §8",
                "evidence": deepcopy(
                    [
                        item
                        for field in (
                            "review_issues",
                            "adapter_issues",
                            "unprocessed_facts",
                        )
                        for item in result.get(field, [])
                    ]
                ),
                "provisional": True,
                "uncertainty_source": f"{RULES_SOURCE}, §6.4",
            }
        )
    color = COLORS[level - 1]
    step, contact, recommendation = ACTIONS[color]
    previous_route = result.get("routing") or {}
    care_context = (result.get("care_context") or {}).get("palliative_care") or {}
    route = timed_route(
        color,
        at
        if at is not None
        else result.get("evaluated_at") or previous_route.get("as_of"),
        palliative_care=palliative_care
        if palliative_care is not None
        else care_context.get("value")
        if care_context.get("value") is not None
        else previous_route.get("palliative_care", False),
        same_day=any(
            r["rule_id"] == "symptomatic_hyperglycemia" for r in result["reasons"]
        ),
        before_next_dose=any(
            r["rule_id"] in {"persistent_neuropathy", "cisplatin_tinnitus"}
            for r in result["reasons"]
        ),
    )
    contact = route.get("doporuceny_kontakt", contact)
    recommendation = route.get("doporuceni_pro_pacienta", recommendation)
    if color == "green" and result.get("reminder_required"):
        recommendation = (
            "Chybí kontrolní dotazník. Vyplňte jej prosím. " + recommendation
        )
    result.update(
        minimum_color=minimum,
        color=color,
        needs_clinical_review=needs_clinical_review,
        requires_review=bool(result.get("requires_review") or needs_clinical_review),
        assessment_status="incomplete"
        if result.get("requires_review") or needs_clinical_review
        else "complete",
        uroven=level,
        doporuceny_krok=step,
        doporuceny_kontakt=contact,
        doporuceni_pro_pacienta=recommendation,
        upozornit_tym=level >= 2,
        action_source=f"{RULES_SOURCE}, §1–2"
        + (", §5 / Paliativní péče" if route["routing"]["palliative_care"] else ""),
        routing=route["routing"],
    )
    return result
