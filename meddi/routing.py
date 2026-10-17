"""Ordinary weekday routing from pravidla_triaze.md §2 and §5.

No clock reads, clinical thresholds, notifications or holiday assumptions.
"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")
SOURCE = "rakathon_meddi_onco_data/docs/pravidla_triaze.md, §1–2, §5"
ON_CALL = "724 590 848"


def checkin_time(prepared):
    """Organizer check-in date/time is Prague-local; missing time stays unknown."""
    if not prepared.get("date") or not prepared.get("time"):
        return None
    return datetime.fromisoformat(f"{prepared['date']}T{prepared['time']}").replace(
        tzinfo=PRAGUE
    )


def _next_weekday(day):
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _at(day, hour, minute=0):
    return datetime.combine(day, time(hour, minute), PRAGUE)


def timed_route(
    color, at, *, palliative_care=False, same_day=False, before_next_dose=False
):
    """Return a concrete route at a supplied instant, never change severity."""
    if isinstance(at, str):
        at = datetime.fromisoformat(at)
    if at is not None and (not isinstance(at, datetime) or at.utcoffset() is None):
        raise ValueError("Čas směrování musí obsahovat časové pásmo.")
    local = at.astimezone(PRAGUE) if at is not None else None
    working = (
        local.weekday() < 5 and time(7) <= local.time() < time(15, 30)
        if local is not None
        else None
    )
    opening = None
    if local is not None and not working:
        day = local.date()
        if local.weekday() >= 5 or local.time() >= time(15, 30):
            day = _next_weekday(day)
        opening = _at(day, 7)
    deadline, team_deadline = None, None
    contact = recommendation = None
    code = None
    phone = None
    if color == "red":
        code, phone = "emergency", "155"
    if local is not None:
        if color == "green":
            code = "monitoring"
            contact = (
                "Záznam vidí zdravotnický tým v přehledu; pokračujte ve sledování."
            )
        elif color == "yellow":
            code = "monitoring_center"
            deadline = _at(
                _next_weekday(local.date()) if working else opening.date(), 15, 30
            )
            if working:
                contact = "Monitorovací centrum MEDDI Onco; vyřízení do konce následujícího pracovního dne."
                recommendation = "Kontaktujte monitorovací centrum MEDDI Onco a požádejte o posouzení."
            else:
                contact = "Monitorovací centrum MEDDI Onco v nejbližší pracovní den."
                recommendation = f"Centrum je nyní mimo pracovní dobu. Kontaktujte je od {opening:%d.%m.%Y %H:%M}."
            recommendation += (
                f" Vyřízení nejpozději do {deadline:%d.%m.%Y %H:%M}."
                f" Při rychlém zhoršení nečekejte: volejte sloužícího lékaře MOÚ {ON_CALL}, při akutním ohrožení 155."
            )
        elif color == "orange":
            deadline = (
                (local.astimezone(UTC) + timedelta(hours=2)).astimezone(PRAGUE)
                if working
                else local
            )
            code = "mou_doctor" if working else "mou_on_call"
            phone = None if working else ON_CALL
            if working:
                contact = "Monitorovací centrum / lékař MOÚ, telekonzultace do 2 hodin."
                recommendation = (
                    f"Kontaktujte monitorovací centrum kvůli telekonzultaci s lékařem MOÚ, nejpozději do {deadline:%d.%m.%Y %H:%M}."
                    f" Při nedostupnosti centra nebo po jeho uzavření volejte ihned sloužícího lékaře MOÚ {ON_CALL}."
                )
            else:
                contact = f"Sloužící lékař MOÚ {ON_CALL} ihned."
                recommendation = f"Mimo pracovní dobu volejte ihned sloužícího lékaře MOÚ {ON_CALL}. Nečekejte na otevření centra."
            recommendation += " Při akutním ohrožení volejte 155."
        elif color == "red":
            code, phone, deadline = "emergency", "155", local
            team_deadline = (local.astimezone(UTC) + timedelta(minutes=15)).astimezone(
                PRAGUE
            )
            contact = "155 / urgentní příjem ihned."
            recommendation = "Volejte ihned 155 nebo vyhledejte urgentní příjem. Nečekejte na odpověď v aplikaci."
    if color == "yellow" and same_day and local is not None:
        deadline = _at(local.date(), 15, 30) if working else local
        code = "monitoring_center" if working else "mou_on_call"
        phone = None if working else ON_CALL
        contact = (
            "Monitorovací centrum ještě dnes."
            if working
            else f"Sloužící lékař MOÚ {ON_CALL} ihned."
        )
        recommendation = (
            "Kontaktujte zdravotnický tým ještě dnes. "
            + (
                "V pracovní době monitorovací centrum."
                if working
                else f"Mimo pracovní dobu volejte sloužícího lékaře MOÚ {ON_CALL}; nečekejte na další pracovní den."
            )
            + " Při akutním ohrožení volejte 155."
        )
    elif color == "yellow" and same_day:
        code = "same_day_team"
        contact = f"Zdravotnický tým ještě dnes; mimo pracovní dobu sloužící lékař MOÚ {ON_CALL}."
        recommendation = (
            "Kontaktujte zdravotnický tým ještě dnes. "
            f"Pokud je centrum mimo pracovní dobu, volejte sloužícího lékaře MOÚ {ON_CALL}. "
            "Při akutním ohrožení volejte 155."
        )
    if palliative_care and color in {"yellow", "orange"}:
        code, phone = "palliative_team_24h", None
        deadline = local
        contact = "24h linka vašeho paliativního týmu / hospice dle plánu péče; při nedostupnosti 155."
        recommendation = (
            "Kontaktujte 24h linku svého paliativního týmu nebo hospice podle svého plánu péče. "
            "Pokud není dostupná, volejte 155. Dříve vyslovená přání sdělte týmu; nejsou důvodem neposkytnout pomoc."
        )
    elif palliative_care and color == "red":
        recommendation = (
            "Volejte ihned 155 nebo vyhledejte urgentní příjem. Nečekejte na odpověď v aplikaci. "
            "Současně lze kontaktovat 24h linku paliativního týmu / hospice a sdělit dříve vyslovená přání; neodkládejte neodkladnou pomoc."
        )
    if before_next_dose and color in {"yellow", "orange"}:
        recommendation = (
            (recommendation or "Kontaktujte zdravotnický tým.")
            + " Nález předejte lékaři před další aplikací nebo dávkou léčby. Léčbu ani dávkování sami neměňte."
        )
    return {
        "routing": {
            "version": 1,
            "as_of": local.isoformat() if local is not None else None,
            "timezone": "Europe/Prague",
            "time_status": "known" if local is not None else "unknown",
            "calendar": "weekdays_07:00_15:30",
            "within_working_hours": working,
            "next_center_open_at": opening.isoformat() if opening is not None else None,
            "contact_code": code,
            "phone": phone,
            "response_due_at": deadline.isoformat() if deadline is not None else None,
            "response_due_label": deadline.strftime("%d.%m.%Y %H:%M %Z")
            if deadline is not None
            else None,
            "team_notify_by": team_deadline.isoformat()
            if team_deadline is not None
            else None,
            "team_notify_by_label": team_deadline.strftime("%d.%m.%Y %H:%M %Z")
            if team_deadline is not None
            else None,
            "as_of_label": local.strftime("%d.%m.%Y %H:%M %Z")
            if local is not None
            else None,
            "before_next_dose": before_next_dose,
            "same_day": same_day,
            "palliative_care": palliative_care,
            "source": SOURCE,
        },
        **({"doporuceny_kontakt": contact} if contact else {}),
        **({"doporuceni_pro_pacienta": recommendation} if recommendation else {}),
    }
