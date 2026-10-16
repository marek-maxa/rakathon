"""Malý adaptér OpenAI kompatibilního Chat Completions API, bez SDK."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib import error, parse, request

from .core import Question, load_questions

ASSETS = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "https://apim-rakathon-q7146n.azure-api.net/openai/v1/"
DEFAULT_DEPLOYMENT = "gpt-6-1-sol-dz-eu"


class APIError(RuntimeError):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Přístupový klíč neposíláme na přesměrovaný endpoint.
        return None


@dataclass(frozen=True)
class Client:
    api_key: str = field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_DEPLOYMENT
    key_header: str = "api-key"

    def __post_init__(self):
        url = parse.urlsplit(self.base_url)
        if url.scheme != "https" or not url.netloc or url.username or url.password:
            raise ValueError("Base URL musí být HTTPS bez přihlašovacích údajů.")
        if url.query or url.fragment:
            raise ValueError("Base URL nesmí obsahovat query ani fragment.")
        if not self.api_key.strip():
            raise ValueError("Chybí MEDDI_LLM_API_KEY.")
        if self.key_header not in {
            "Authorization",
            "api-key",
            "Ocp-Apim-Subscription-Key",
        }:
            raise ValueError("Nepodporovaná autentizační hlavička.")

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.environ.get("MEDDI_LLM_API_KEY", ""),
            base_url=os.environ.get("MEDDI_LLM_BASE_URL", DEFAULT_BASE_URL),
            model=os.environ.get("MEDDI_LLM_MODEL", DEFAULT_DEPLOYMENT),
            key_header=os.environ.get("MEDDI_LLM_KEY_HEADER", "api-key"),
        )

    def payload(
        self,
        question: Question,
        sources: list[str],
        source_questions: list[str] | None = None,
    ) -> dict:
        messages = [
            {
                "role": "system",
                "content": (ASSETS / "prompt.md").read_text(encoding="utf-8"),
            }
        ]
        examples = json.loads((ASSETS / "examples.json").read_text(encoding="utf-8"))
        # Příklady drží jen ID; texty a možnosti mají jediný zdroj v definicích.
        questions = {(q.questionnaire_id, q.id): q for q in load_questions()}
        for example in examples:
            ref = example["input"]["question"]
            example_input = {
                **example["input"],
                "question": questions[
                    (ref["questionnaire_id"], ref["question_id"])
                ].specification(),
            }
            messages.extend(
                [
                    {
                        "role": "user",
                        "content": json.dumps(example_input, ensure_ascii=False),
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps(example["output"], ensure_ascii=False),
                    },
                ]
            )
        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question.specification(),
                        "source_messages": sources,
                        "source_questions": source_questions
                        or [question.text] * len(sources),
                    },
                    ensure_ascii=False,
                ),
            }
        )
        return self.structured_payload(messages, question.schema(), "question_answer")

    def structured_payload(self, messages: list[dict], schema: dict, name: str) -> dict:
        """Sdílený tvar požadavku pro cílenou odpověď i extrakci celé zprávy."""
        return {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": 4096,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }

    def __call__(
        self,
        question: Question,
        sources: list[str],
        source_questions: list[str] | None = None,
    ) -> dict:
        return self.send(self.payload(question, sources, source_questions))

    def send(self, payload: dict) -> dict:
        """Stejná autentizace a obsluha chyb pro oba extraktory."""
        auth = (
            f"Bearer {self.api_key}"
            if self.key_header == "Authorization"
            else self.api_key
        )
        req = request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(
                "utf-8"
            ),
            headers={self.key_header: auth, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.build_opener(NoRedirect()).open(req, timeout=60) as response:
                body = json.load(response)
        except error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise APIError(
                    f"LLM API: HTTP {exc.code}. Autentizace selhala; pro rakathonovou "
                    "bránu nastavte MEDDI_LLM_KEY_HEADER=api-key a ověřte klíč."
                ) from None
            if exc.code == 404:
                raise APIError(
                    "LLM API: HTTP 404. Ověřte base URL a přesný název nasazení "
                    "v MEDDI_LLM_MODEL (např. gpt-6-1-sol-dz-eu)."
                ) from None
            raise APIError(
                f"LLM API: HTTP {exc.code}. Ověřte parametry požadavku a podporu JSON schema."
            ) from None
        except (error.URLError, TimeoutError, OSError):
            raise APIError("LLM API není dostupné nebo vypršel časový limit.") from None
        except ValueError:
            raise APIError("LLM API nevrátilo platný JSON.") from None
        try:
            choice = body["choices"][0]
            if choice["finish_reason"] != "stop" or choice["message"].get("refusal"):
                raise APIError(
                    "Model odmítl odpověď nebo je výstup neúplný; návrh nebyl změněn."
                )
            return json.loads(choice["message"]["content"])
        except (KeyError, IndexError, TypeError, ValueError):
            raise APIError("LLM API vrátilo neplatnou strukturu odpovědi.") from None
