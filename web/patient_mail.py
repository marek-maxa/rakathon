import secrets
import smtplib

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    request,
    session,
    url_for,
)
from itsdangerous import BadSignature, URLSafeSerializer

from meddi.loader import list_patient_ids
from notifications import mailer
from web.patient_store import load_patient, save_patient_email

patient_mail = Blueprint("patient_mail", __name__)


def serializer():
    return URLSafeSerializer(current_app.secret_key, salt="patient-email/v1")


def email_token(patient_id):
    return serializer().dumps(
        {
            "patient_id": patient_id,
            "owner": session.setdefault(
                "patient_email_owner", secrets.token_urlsafe(16)
            ),
            "id": secrets.token_urlsafe(16),
        }
    )


@patient_mail.post("/patients/<patient_id>/email")
def send_patient_email(patient_id):
    if patient_id not in list_patient_ids():
        abort(404)
    target = (
        url_for("patient_report.team_overview")
        if request.form.get("return_to") == "team"
        else url_for("patient_report.report_patient", patient_id=patient_id)
    )
    try:
        ticket = serializer().loads(request.form.get("email_token", ""))
    except BadSignature:
        ticket = None
    if (
        not isinstance(ticket, dict)
        or ticket.get("patient_id") != patient_id
        or not ticket.get("owner")
        or ticket["owner"] != session.get("patient_email_owner")
        or not ticket.get("id")
    ):
        flash(
            "Formulář není platný. Obnovte stránku a zkuste to znovu.",
            "patient-email-error",
        )
        return redirect(target)
    if request.form.get("action") == "save_contact":
        recipient = request.form.get("email", "").strip()
        if not mailer.valid_email(recipient):
            flash("Zadejte platnou e-mailovou adresu pacienta.", "patient-email-error")
            return redirect(target)
        try:
            save_patient_email(patient_id, recipient)
        except (OSError, ValueError):
            flash(
                "Kontakt se nepodařilo uložit. Zkuste to znovu.", "patient-email-error"
            )
        else:
            flash("E-mail pacienta byl uložen.", "patient-email-success")
        return redirect(target)
    sent = session.get("sent_patient_emails", [])
    if ticket["id"] in sent:
        flash(
            "Tento formulář už byl odeslán. E-mail neposíláme znovu.",
            "patient-email-info",
        )
        return redirect(target)
    recipient = (load_patient(patient_id).get("kontakt") or {}).get("email", "")
    if not mailer.valid_email(recipient):
        flash("Zadejte platnou e-mailovou adresu pacienta.", "patient-email-error")
        return redirect(target)
    try:
        mailer.send_notification(recipient)
    except ValueError:
        flash(
            "Odesílání e-mailů není nastavené. Zkontrolujte konfiguraci SMTP.",
            "patient-email-error",
        )
    except (smtplib.SMTPException, OSError):
        flash("E-mail se nepodařilo odeslat. Zkuste to znovu.", "patient-email-error")
    else:
        session["sent_patient_emails"] = [*sent, ticket["id"]][-20:]
        flash(
            f"Zpráva pro pacienta {patient_id} byla předána poštovnímu serveru.",
            "patient-email-success",
        )
    return redirect(target)
