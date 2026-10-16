import json
import os
import secrets
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "llm_intake" / ".env")
sys.path.insert(0, str(ROOT))

from llm_intake.client import APIError, Client
from llm_intake.dialogue import MasterDialogue
from llm_intake.master import MasterExtractor
from llm_intake.master_contract import MessageEvent
from web.export import meddi_record

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(16)
app.config["MAX_QUESTIONS"] = 6
app.config["DATA_DIR"] = ROOT / "data"
MASTER_QUESTION = "Jak se dnes cítíte?"
sessions = {}


def state():
    key = session.get("id")
    if key not in sessions:
        key = session["id"] = secrets.token_urlsafe(16)
        sessions[key] = {"contact": None, "done": False}
    return key, sessions[key]


def page_for(data):
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


def save_packet(packet):
    record = meddi_record(packet, datetime.now().astimezone())
    content = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    directory = Path(app.config["DATA_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"questionnaire-{packet['message']['id']}.json"
    with TemporaryDirectory(dir=directory) as temporary:
        path = Path(temporary) / "result.json"
        path.write_text(content, encoding="utf-8")
        path.replace(destination)
    return destination


@app.route("/", methods=["GET", "POST"])
def index():
    key, saved = state()
    error = None
    data = saved
    if request.method == "POST":
        data = deepcopy(saved)
        try:
            if "restart" in request.form:
                sessions.pop(key)
                return redirect("/")
            if data["done"]:
                raise ValueError("Odpovědi už jsou potvrzené.")
            contact = data["contact"]
            if "confirm" in request.form:
                if contact is None:
                    raise ValueError("Nejprve dokončete všechny otázky.")
                data["packet"] = contact.confirm_all()
                data["output_file"] = str(save_packet(data["packet"]))
                data["done"] = True
            elif "edit" in request.form:
                if contact is None:
                    raise ValueError("Nejprve dokončete všechny otázky.")
                contact.revise(int(request.form["edit"]))
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
                        message(key, text, MASTER_QUESTION, "master_question")
                    )
                    data["contact"] = contact
                else:
                    if contact.state not in {"needs_answer", "needs_correction"}:
                        raise ValueError("Nyní zkontrolujte souhrn odpovědí.")
                    contact.submit(
                        message(
                            key, text, contact.active.next_question, "targeted_answer"
                        )
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
