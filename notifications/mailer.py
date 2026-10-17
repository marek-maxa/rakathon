import os
import smtplib
import ssl
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.message import EmailMessage

SUBJECT = "MEDDI ONCO – dotazník od vašeho lékaře"
BODY = "Dobrý den,\n\nváš ošetřující lékař vám posílá dotazník o vašem aktuálním zdravotním stavu.\nProsíme, otevřete aplikaci MEDDI ONCO a dotazník vyplňte. Vaše odpovědi pomohou ošetřujícímu týmu získat přehled o tom, jak se právě cítíte.\n\nDěkujeme za spolupráci.\nVáš ošetřující tým\n"


def valid_email(value):
    if not value or len(value) > 254 or any(char in value for char in "\r\n"):
        return False
    try:
        address = Address(addr_spec=value)
        return bool(address.username and address.domain) and value.isascii()
    except (ValueError, IndexError, HeaderParseError):
        return False


def send_notification(recipient):
    host = os.environ.get("SMTP_HOST", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip()
    username = os.environ.get("SMTP_USERNAME", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    security = os.environ.get("SMTP_SECURITY", "starttls").lower()
    if not host or not valid_email(sender) or security not in {"starttls", "ssl"}:
        raise ValueError("Email sending is not configured yet.")
    if bool(username) != bool(password):
        raise ValueError("Email sending is not configured yet.")
    try:
        port = int(os.environ.get("SMTP_PORT", "465" if security == "ssl" else "587"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise ValueError("Email sending is not configured yet.") from None
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = SUBJECT
    message.set_content(BODY)
    context = ssl.create_default_context()
    connection = (
        smtplib.SMTP_SSL(host, port, timeout=15, context=context)
        if security == "ssl"
        else smtplib.SMTP(host, port, timeout=15)
    )
    with connection as smtp:
        if security == "starttls":
            smtp.starttls(context=context)
        if username:
            smtp.login(username, password)
        smtp.send_message(message)
