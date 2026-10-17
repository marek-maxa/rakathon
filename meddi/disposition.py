"""Actionable four-level disposition, separate from assessment completeness.

Sources: bundle README §4/§6 and pravidla_triaze.md §1–2, §6.4.
Yellow review for unresolved current inputs is a conservative application policy,
not a diagnosis or a claim that the missing clinical mapping is implemented.
"""

from copy import deepcopy

RULES_SOURCE = "rakathon_meddi_onco_data/docs/pravidla_triaze.md"
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
        "Kontaktujte monitorovací centrum MEDDI Onco a požádejte o posouzení. "
        "Vyřízení má proběhnout nejpozději do konce následujícího pracovního dne. "
        "Při rychlém zhoršení nečekejte: volejte sloužícího lékaře MOÚ 724 590 848, při akutním ohrožení 155.",
    ),
    "orange": (
        "telekonzultace",
        "V pracovní době lékař MOÚ do 2 hodin; mimo pracovní dobu sloužící lékař MOÚ 724 590 848 ihned.",
        "V pracovní době Po–Pá 7:00–15:30 kontaktujte monitorovací centrum kvůli telekonzultaci s lékařem do 2 hodin. "
        "Mimo pracovní dobu volejte ihned sloužícího lékaře MOÚ 724 590 848. Při akutním ohrožení volejte 155.",
    ),
    "red": (
        "neodkladna_pomoc",
        "155 / urgentní příjem ihned.",
        "Volejte ihned 155 nebo vyhledejte urgentní příjem. Nečekejte na odpověď v aplikaci.",
    ),
}


def resolve_disposition(assessment: dict, *, needs_clinical_review: bool) -> dict:
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
                "source": f"{RULES_SOURCE}, §1 / Žlutá, §6.4; rakathon_meddi_onco_data/README.md, §6.2 a §6.7",
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
        action_source=f"{RULES_SOURCE}, §1–2",
    )
    return result
