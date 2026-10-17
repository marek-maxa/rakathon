import os
import secrets
import smtplib
import ssl
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.message import EmailMessage

from flask import Flask, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

SUBJECT = "MEDDI ONCO notification"
BODY = "Hello,\n\nThis is a test notification from MEDDI ONCO.\n\nThe MEDDI ONCO team\n"


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


@app.get("/")
def index():
    session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return render_template("index.html")


@app.post("/send")
def send_mail():
    recipient = request.form.get("email", "").strip()
    token = session.get("csrf_token", "")
    if not token or not secrets.compare_digest(
        token.encode(), request.form.get("csrf_token", "").encode()
    ):
        return render_template(
            "index.html",
            error="Please refresh the page and try again.",
            email=recipient,
        ), 400
    if not valid_email(recipient):
        return render_template(
            "index.html", error="Enter a valid email address.", email=recipient
        ), 400
    try:
        send_notification(recipient)
    except ValueError as error:
        return render_template("index.html", error=str(error), email=recipient), 503
    except (smtplib.SMTPException, OSError):
        return render_template(
            "index.html",
            error="The email could not be sent. Please try again.",
            email=recipient,
        ), 502
    flash("Your notification has been sent.")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run()
