import json
import os
import secrets
import sqlite3
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request, session
from itsdangerous import BadSignature, URLSafeSerializer

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "llm_intake" / ".env")
load_dotenv(ROOT / "notifications" / ".env")
sys.path.insert(0, str(ROOT))

from llm_intake.client import APIError, Client
from llm_intake.core import DEFINITIONS
from llm_intake.dialogue import MasterDialogue
from llm_intake.master import MasterExtractor
from llm_intake.master_contract import MessageEvent
from meddi.loader import list_patient_ids, load_patient
from web.event_store import EventStore
from web.export import meddi_record
from web.patient_mail import patient_mail
from web.patient_report import patient_report
from web.patient_store import append_checkins
from web.patient_store import load_patient as load_working_patient
from web.triage import assess_contact

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(16)
app.register_blueprint(patient_report)
app.register_blueprint(patient_mail)
app.config["MAX_QUESTIONS"] = 6
app.config["BASIC_AUTH_USERNAME"] = os.environ.get("MEDDI_BASIC_AUTH_USERNAME", "")
app.config["BASIC_AUTH_PASSWORD"] = os.environ.get("MEDDI_BASIC_AUTH_PASSWORD", "")
app.config["DATA_DIR"] = Path(os.environ.get("MEDDI_DATA_DIR") or ROOT / "data")
MASTER_QUESTION = "Jak se dnes cítíte?"
sessions = {}


@app.before_request
def require_basic_auth():
    """Protect every route, including reports and static files; fail closed."""
    username = app.config["BASIC_AUTH_USERNAME"]
    password = app.config["BASIC_AUTH_PASSWORD"]
    if not username or not password or ":" in username:
        return Response(
            "Web authentication is not configured.",
            status=503,
            headers={"Cache-Control": "no-store"},
            mimetype="text/plain",
        )
    auth = request.authorization
    if auth is not None and auth.type == "basic":
        username_matches = secrets.compare_digest(
            (auth.username or "").encode("utf-8"), username.encode("utf-8")
        )
        password_matches = secrets.compare_digest(
            (auth.password or "").encode("utf-8"), password.encode("utf-8")
        )
        if username_matches and password_matches:
            return None
    return Response(
        "Authentication required.",
        status=401,
        headers={
            "WWW-Authenticate": 'Basic realm="MEDDI demo", charset="UTF-8"',
            "Cache-Control": "no-store",
        },
        mimetype="text/plain",
    )


def state():
    key = session.get("id")
    if key not in sessions:
        # Keep ownership of the durable journal after process memory is lost.
        key = session["id"] = key or secrets.token_urlsafe(16)
        sessions[key] = {"contact": None, "done": False, "patient_id": None}
    return key, sessions[key]


def patient_choices():
    return [
        {
            "id": patient_id,
            "name": load_patient(patient_id)["demografie"]["jmeno_fiktivni"],
        }
        for patient_id in list_patient_ids()
    ]


def page_for(data):
    if data["patient_id"] is None:
        return {"select_patient": True, "patients": patient_choices()}
    page = survey_page(data)
    if "question" in page:
        page["submission_token"] = submission_token(data)
    return {
        **page,
        "patient_id": data["patient_id"],
        "patient_name": data["patient_name"],
        "assessment": data.get("assessment"),
        "safety_notice": data.get("safety_notice"),
    }


def survey_page(data):
    contact = data["contact"]
    if contact is None:
        return {"master": True, "question": MASTER_QUESTION}
    if contact.state == "paused":
        return {"paused": True}
    packet = contact.snapshot()
    names = {
        f["id"]: f["nazev"] for f in json.loads(DEFINITIONS.read_text(encoding="utf-8"))
    }
    selected = [names[flow["questionnaire_id"]] for flow in packet["dialogue"]["flows"]]
    if contact.state in {"needs_answer", "needs_correction"}:
        return {
            "question": contact.active.next_question,
            "questionnaire_name": names[contact.active.question.questionnaire_id],
            "selected_questionnaires": selected,
            "instruction": contact.active.question.instruction,
            "options": contact.active.question.patient_options(),
        }
    return {
        "done": data["done"],
        "review": True,
        "patient_message_text": "\n".join(
            event["text"]
            for event in packet["messages"]
            if event["source"] in {"master_question", "patient_message"}
        ),
        "selected_questionnaires": selected,
        "drafts": contact.review_sessions,
        "gaps": packet["analysis_status"] == "no_facts"
        or bool(packet["unmapped_concepts"])
        or bool(packet["unknown_subject_fact_indices"]),
        "blocked": any(
            q["state"] == "blocked"
            for flow in packet["dialogue"]["flows"]
            for q in flow["questions"]
        ),
        "limited": contact.state == "limited",
        "pending": packet["dialogue"]["pending_topic_ids"],
        "warnings": list(
            dict.fromkeys(
                warning
                for form in meddi_record(
                    packet, datetime.now().astimezone(), include_drafts=True
                )["checkiny"][0]["dotazniky"]
                for warning in form["zobrazena_upozorneni"]
            )
        ),
    }


def event_store():
    return EventStore(Path(app.config["DATA_DIR"]) / "events.sqlite3")


def submission_serializer():
    return URLSafeSerializer(app.secret_key, salt="meddi-message/v1")


def submission_token(data):
    """Bind a stable submission ID to the actual displayed question."""
    if "submission" not in data:
        active = data["contact"].active if data["contact"] else None
        source_events = active.snapshot().get("source_events", []) if active else []
        corrects = (
            next((event["id"] for event in reversed(source_events) if event), None)
            if active and active.state == "needs_correction"
            else None
        )
        data["submission"] = {
            "owner_id": session["id"],
            "contact_id": data.setdefault("contact_id", secrets.token_urlsafe(16)),
            "patient_id": data["patient_id"],
            "id": secrets.token_urlsafe(16),
            "source": "targeted_answer" if active else "master_question",
            "question": active.next_question if active else MASTER_QUESTION,
            "question_id": (
                f"{active.question.questionnaire_id}/{active.question.id}"
                if active
                else None
            ),
            "corrects_event_id": corrects,
        }
    return submission_serializer().dumps(data["submission"])


def read_submission(key):
    try:
        ticket = submission_serializer().loads(request.form.get("submission_token", ""))
    except BadSignature:
        raise ValueError("Obnovte stránku a odešlete odpověď znovu.") from None
    if not isinstance(ticket, dict) or ticket.get("owner_id") != key:
        raise ValueError("Odeslání nepatří tomuto rozhovoru.")
    return ticket


def accept_message(key, ticket, text):
    stored = event_store().accept(
        key,
        ticket["contact_id"],
        MessageEvent(
            id=ticket["id"],
            patient_id=ticket["patient_id"],
            text=text,
            available_at=datetime.now(UTC).isoformat(),
            source=ticket["source"],
            author="patient",
            question=ticket["question"],
        ),
        question_id=ticket["question_id"],
        corrects_event_id=ticket["corrects_event_id"],
    )
    return stored.message


def save_packet(packet, patient_id, assessment):
    if packet["message"]["patient_id"] != patient_id:
        raise ValueError("Odpovědi nepatří vybranému pacientovi.")
    record = meddi_record(
        packet,
        datetime.fromisoformat(assessment["evaluated_at"]),
        assessment=assessment,
    )
    record["checkiny"][0]["triage_assessment"] = assessment
    return append_checkins(patient_id, record["checkiny"])


def retain_safety_notice(data, saved, assessment):
    """Retain the alert across rollback; return whether it is new or increased."""
    data["assessment"] = assessment
    if assessment.get("minimum_color") not in {"orange", "red"}:
        return False
    previous = saved.get("safety_notice")
    newly_urgent = previous is None or (
        assessment["minimum_color"] == "red"
        and previous["assessment"]["minimum_color"] != "red"
    )
    # An unfinished correction or failed processing cannot erase a known
    # urgent instruction. Explicit clinical resolution is outside this MVP.
    if (
        previous is None
        or assessment["minimum_color"] == "red"
        or previous["assessment"]["minimum_color"] != "red"
    ):
        notice = {"assessment": assessment}
        saved["safety_notice"] = data["safety_notice"] = notice
    else:
        data["safety_notice"] = previous
    return newly_urgent


def safety_checkpoint(data, saved):
    """Evaluate before targeted LLM; the dialogue never stores this closure."""
    patient = load_working_patient(data["patient_id"])

    def checkpoint(packet):
        assessment = assess_contact(packet, patient, datetime.now().astimezone())
        return retain_safety_notice(data, saved, assessment)

    return checkpoint


@app.get("/")
def home():
    return render_template("welcome.html")


@app.route("/patient", methods=["GET", "POST"])
def index():
    key, saved = state()
    error = None
    received = False
    data = saved
    if request.method == "POST":
        data = deepcopy(saved)
        try:
            if "restart" in request.form:
                data.update(contact=None, done=False)
                data.pop("packet", None)
                data.pop("output_file", None)
                data.pop("assessment", None)
                data.pop("contact_id", None)
                data.pop("submission", None)
                data.pop("received_message", None)
                data.pop("safety_notice", None)
                sessions[key] = data
                return redirect("/patient")
            ticket = None
            if "answer" in request.form and "submission_token" in request.form:
                ticket = read_submission(key)
                if ticket != data.get("submission"):
                    previous = event_store().get(key, ticket["id"])
                    if previous is None:
                        raise ValueError("Otázka již není aktuální. Obnovte stránku.")
                    if previous.message.text != request.form["answer"]:
                        raise ValueError("Toto odeslání již obsahuje jinou zprávu.")
                    if data["contact"] is None:
                        raise ValueError(
                            "Zpráva je uložená, ale přerušený rozhovor zatím nelze "
                            "obnovit. Vyberte profil a začněte nový rozhovor."
                        )
                    # A stale POST must not become an answer to the next question.
                    return redirect("/patient")
            if data["done"]:
                raise ValueError("Odpovědi už jsou potvrzené.")
            if data["patient_id"] is None:
                selected_id = request.form.get("patient_id", "")
                selected = next(
                    (p for p in patient_choices() if p["id"] == selected_id), None
                )
                if selected is None:
                    raise ValueError("Vyberte platný profil pacienta.")
                data["patient_id"] = selected_id
                data["patient_name"] = selected["name"]
                sessions[key] = data
                return redirect("/patient")
            contact = data["contact"]
            if "continue" in request.form:
                if contact is None:
                    raise ValueError("Nejprve zahajte rozhovor.")
                contact.resume()
                data["assessment"] = assess_contact(
                    contact.snapshot(),
                    load_working_patient(data["patient_id"]),
                    datetime.now().astimezone(),
                )
                retain_safety_notice(data, saved, data["assessment"])
            elif "confirm" in request.form:
                if contact is None:
                    raise ValueError("Nejprve dokončete všechny otázky.")
                data["packet"] = contact.confirm_all()
                data["assessment"] = assess_contact(
                    data["packet"],
                    load_working_patient(data["patient_id"]),
                    datetime.now().astimezone(),
                )
                retain_safety_notice(data, saved, data["assessment"])
                data["output_file"] = str(
                    save_packet(data["packet"], data["patient_id"], data["assessment"])
                )
                data["done"] = True
            elif "edit" in request.form:
                if contact is None:
                    raise ValueError("Nejprve dokončete všechny otázky.")
                contact.revise(int(request.form["edit"]))
                data.pop("assessment", None)
                data.pop("submission", None)
            elif "replace_message" in request.form:
                ticket = read_submission(key)
                if (
                    ticket != data.get("submission")
                    or event_store().get(key, ticket["id"]) is None
                ):
                    raise ValueError("Není k dispozici uložená zpráva k opravě.")
                data["submission"] = {
                    **ticket,
                    "id": secrets.token_urlsafe(16),
                    "corrects_event_id": ticket["id"],
                }
                data.pop("received_message", None)
            elif "answer" in request.form:
                text = request.form["answer"]
                if not text.strip():
                    raise ValueError("Odpověď nesmí být prázdná.")
                ticket = ticket or read_submission(key)
                if ticket != data.get("submission"):
                    raise ValueError("Otázka již není aktuální. Obnovte stránku.")
                if contact is not None and contact.state not in {
                    "needs_answer",
                    "needs_correction",
                }:
                    raise ValueError("Nyní zkontrolujte souhrn odpovědí.")
                original = accept_message(key, ticket, text)
                received = True
                # Keep only the receipt on failure; the dialogue still rolls back.
                saved["received_message"] = original
                if contact is None:
                    client = Client.from_env()
                    contact = MasterDialogue(
                        MasterExtractor(client),
                        client,
                        extract_with_events=client.extract_events,
                        max_questions=app.config["MAX_QUESTIONS"],
                        bulk_confirmation=True,
                    )
                    contact.start(original, checkpoint=safety_checkpoint(data, saved))
                    data["contact"] = contact
                else:
                    contact.submit(original, checkpoint=safety_checkpoint(data, saved))
                data["assessment"] = assess_contact(
                    contact.snapshot(),
                    load_working_patient(data["patient_id"]),
                    datetime.now().astimezone(),
                )
                retain_safety_notice(data, saved, data["assessment"])
                data.pop("submission", None)
                data.pop("received_message", None)
            else:
                raise ValueError("Neplatná akce formuláře.")
            sessions[key] = data
            return redirect("/patient")
        except (APIError, ValueError, TypeError) as exc:
            error = str(exc)
            data = saved
        except (OSError, sqlite3.Error):
            error = "Odpovědi se nepodařilo uložit. Zkuste odeslání znovu."
            data = saved
    pending = data.get("received_message")
    answer_text = (
        pending.text if pending else request.form.get("answer", "") if error else ""
    )
    return render_template(
        "index.html",
        page=page_for(data),
        error=error,
        received=received or pending is not None,
        answer_text=answer_text,
    )


if __name__ == "__main__":
    app.run()
