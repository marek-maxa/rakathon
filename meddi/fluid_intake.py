"""Narrow offline recognition of explicit fluid reports, not general NLP.

Unknown wording remains unassessed. No reference labels or patient IDs are used.
"""

import re
import unicodedata
from datetime import timedelta


def _normalize(text):
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(c)
    )


def _reports(checkin):
    if checkin.get("vyplnil") not in {"pacient", "patient"}:
        return []
    texts = [("zprava_pacienta", checkin.get("zprava_pacienta"))]
    for form in checkin.get("dotazniky", []):
        for answer in form.get("odpovedi", []):
            if answer.get("otazka_id") == "jine":
                texts.append(("dotazniky.jine", answer.get("odpoved")))
    return [(field, text) for field, text in texts if isinstance(text, str)]


def _find(checkin, pattern):
    for field, text in _reports(checkin):
        for sentence in re.split(r"[.!?;\n]+", text):
            if re.fullmatch(pattern, _normalize(sentence).strip()):
                return {
                    "checkin_id": checkin["checkin_id"],
                    "field": field,
                    "evidence": sentence.strip(),
                }
    return None


def fluid_observations(checkin, history, instant):
    """Bridge yesterday's explicit failure only with current corroboration.

    The mentor explicitly confirmed the previous-day link. Require a current
    report about yesterday's drinking and ongoing swallowing limitation; do not
    expire/carry arbitrary older symptoms or treat reduced intake as failure.
    """
    observations = {}

    def put(field, value, source):
        if source:
            observations[field] = {"value": value, "source": source}

    failure = _find(
        checkin,
        r"(?:dnes |nyni )?(?:nepolknu (?:ani )?(?:vodu|tekutiny)"
        r"|nepolknu skoro nic, ani vodu(?: moc ne)?"
        r"(?:, sliny vyplivuju)?"
        r"|(?:nemohu|nemuzu|nedokazu|nezvladnu) (?:pit|polknout vodu))",
    )
    recovery = _find(
        checkin,
        r"(?:uz |dnes |nyni )?(?:zase )?(?:piju|piji|polykam) "
        r"(?:vodu|tekutiny) (?:normalne|bez potizi|bez problemu)",
    )
    put("cannot_drink_fluids", True, failure)
    if recovery and not failure:
        put("cannot_drink_fluids", False, recovery)
    for field, pattern in (
        ("low_urine", r"malo mocim"),
        ("dizziness", r"toci se (?:mi )?hlava"),
    ):
        for name, text in _reports(checkin):
            for clause in re.split(r"[,\.!?;\n]+", text):
                if re.fullmatch(
                    r"(?:dnes |nyni )?" + pattern, _normalize(clause).strip()
                ):
                    put(
                        field,
                        True,
                        {
                            "checkin_id": checkin["checkin_id"],
                            "field": name,
                            "evidence": clause.strip(),
                        },
                    )
    yesterday_report = _find(
        checkin,
        r"vcera jsem (?:vypil|vypila) .+",
    )
    limited_swallowing = any(
        form.get("dotaznik_id") == "nezadouci_ucinky"
        and answer.get("otazka_id") == "afty"
        and answer.get("odpoved_index") == 3
        for form in checkin.get("dotazniky", [])
        for answer in form.get("odpovedi", [])
    )
    if (
        not failure
        and not recovery
        and yesterday_report
        and limited_swallowing
        and history
    ):
        previous = history[-1]
        if instant(previous).date() == instant(checkin).date() - timedelta(days=1):
            prior = fluid_observations(previous, [], instant).get("cannot_drink_fluids")
            if prior and prior["value"] is True:
                put(
                    "cannot_drink_fluids",
                    True,
                    {
                        "prior_failure": prior["source"],
                        "current_report": yesterday_report,
                        "continuity": "previous_day_with_current_swallowing_limitation",
                    },
                )
    return observations
