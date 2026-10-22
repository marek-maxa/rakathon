# MEDDI ONCO

A demo of oncology patient monitoring between appointments, using synthetic
profiles. Conversational check-ins, explainable triage, and a shared view of
symptoms, measurements, and follow-up for patients and care teams.

## Run locally

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --locked
```

Copy `.env.example` to `.env`. Set the web username and password, a random
`FLASK_SECRET_KEY`, and your LLM provider's API key, URL, model, and auth header.

```sh
uv run --locked python -m web.app
```

Open **http://127.0.0.1:5000** and sign in with the configured credentials.

- **Patient:** enter a sample profile code, such as `ONC-001`, submit a check-in,
  review the answers, and confirm to save. Use the portal to update measurements.
- **Care team:** open `/team` to review priorities, inspect patient histories,
  and schedule follow-up. Email requires the optional SMTP settings in `.env`.

## Share the demo

On a Linux server, use the same environment settings and run:

```sh
uv sync --locked --no-dev
uv run --locked --no-dev gunicorn --config gunicorn.conf.py web.app:app
```

Serve port 8000 through HTTPS when sharing access. Gunicorn uses one worker
because active conversations are held in memory and reset on restart.
Saved check-ins and original messages remain in `data/`; set `MEDDI_DATA_DIR`
to a persistent directory on the host.

## Checks

```sh
uv sync --locked
uv run --locked pytest -q
uv run --locked ruff check .
```

This demo uses shared access and simulates clinical handoff. It is intended
for demonstrations, not real patient care.
