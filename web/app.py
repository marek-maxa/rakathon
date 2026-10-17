import os
import secrets
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request, session

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "llm_intake" / ".env")
sys.path.insert(0, str(ROOT))

from llm_intake.client import APIError, Client
from llm_intake.dialogue import MasterDialogue
from llm_intake.master import MasterExtractor
from llm_intake.master_contract import MessageEvent
from meddi.loader import list_patient_ids, load_patient
from web.export import meddi_record
from web.patient_report import patient_report
from web.patient_store import append_checkins
from web.patient_store import load_patient as load_working_patient
from web.triage import assess_contact

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(16)
app.config["BASIC_AUTH_USERNAME"] = os.environ.get("MEDDI_BASIC_AUTH_USERNAME", "")
app.config["BASIC_AUTH_PASSWORD"] = os.environ.get("MEDDI_BASIC_AUTH_PASSWORD", "")
app.register_blueprint(patient_report)
app.config["MAX_QUESTIONS"] = 6
app.config["DATA_DIR"] = ROOT / "data"
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
        key = session["id"] = secrets.token_urlsafe(16)
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
    return {
        **survey_page(data),
        "patient_id": data["patient_id"],
        "patient_name": data["patient_name"],
        "assessment": data.get("assessment"),
    }


def survey_page(data):
    contact = data["contact"]
    if contact is None:
        return {"master": True, "question": MASTER_QUESTION}
    packet = contact.snapshot()
    if contact.state in {"needs_answer", "needs_correction"}:
        return {
            "question": contact.active.next_question,
            "instruction": contact.active.question.instruction,
            "options": contact.active.question.patient_options(),
        }
    return {
        "done": data["done"],
        "review": True,
        "master_text": packet["message"]["text"],
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


def message(key, text, question, source):
    return MessageEvent(
        id=secrets.token_urlsafe(16),
        patient_id=key,
        text=text,
        available_at=datetime.now(UTC).isoformat(),
        source=source,
        author="patient",
        question=question,
    )


def save_packet(packet, patient_id, assessment):
    if packet["message"]["patient_id"] != patient_id:
        raise ValueError("Odpovědi nepatří vybranému pacientovi.")
    record = meddi_record(packet, datetime.now().astimezone())
    record["checkiny"][0]["triage_assessment"] = assessment
    return append_checkins(patient_id, record["checkiny"])


@app.route("/", methods=["GET", "POST"])
def index():
    key, saved = state()
    error = None
    data = saved
    if request.method == "POST":
        data = deepcopy(saved)
        try:
            if "restart" in request.form:
                data.update(contact=None, done=False)
                data.pop("packet", None)
                data.pop("output_file", None)
                data.pop("assessment", None)
                sessions[key] = data
                return redirect("/")
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
                return redirect("/")
            contact = data["contact"]
            if "confirm" in request.form:
                if contact is None:
                    raise ValueError("Nejprve dokončete všechny otázky.")
                data["packet"] = contact.confirm_all()
                data["assessment"] = assess_contact(
                    data["packet"],
                    load_working_patient(data["patient_id"]),
                    datetime.now().astimezone(),
                )
                data["output_file"] = str(
                    save_packet(data["packet"], data["patient_id"], data["assessment"])
                )
                data["done"] = True
            elif "edit" in request.form:
                if contact is None:
                    raise ValueError("Nejprve dokončete všechny otázky.")
                contact.revise(int(request.form["edit"]))
                data.pop("assessment", None)
            elif "answer" in request.form:
                text = request.form["answer"].strip()
                if not text:
                    raise ValueError("Odpověď nesmí být prázdná.")
                if contact is None:
                    client = Client.from_env()
                    contact = MasterDialogue(
                        MasterExtractor(client),
                        client,
                        extract_with_events=client.extract_events,
                        max_questions=app.config["MAX_QUESTIONS"],
                        bulk_confirmation=True,
                    )
                    contact.start(
                        message(
                            data["patient_id"], text, MASTER_QUESTION, "master_question"
                        )
                    )
                    data["contact"] = contact
                else:
                    if contact.state not in {"needs_answer", "needs_correction"}:
                        raise ValueError("Nyní zkontrolujte souhrn odpovědí.")
                    contact.submit(
                        message(
                            data["patient_id"],
                            text,
                            contact.active.next_question,
                            "targeted_answer",
                        )
                    )
                data["assessment"] = assess_contact(
                    contact.snapshot(),
                    load_working_patient(data["patient_id"]),
                    datetime.now().astimezone(),
                )
            else:
                raise ValueError("Neplatná akce formuláře.")
            sessions[key] = data
            return redirect("/")
        except (APIError, ValueError, TypeError) as exc:
            error = str(exc)
            data = saved
        except OSError:
            error = "Odpovědi se nepodařilo uložit. Zkuste potvrzení znovu."
            data = saved
    return render_template("index.html", page=page_for(data), error=error)


if __name__ == "__main__":
    app.run()
