"""Single-process server for the application's in-memory conversations."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

for name in (
    "FLASK_SECRET_KEY",
    "MEDDI_BASIC_AUTH_USERNAME",
    "MEDDI_BASIC_AUTH_PASSWORD",
):
    if not os.environ.get(name, "").strip():
        raise RuntimeError(f"Set {name} before starting the server.")

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = 1
worker_class = "gthread"
threads = 4
timeout = 180
accesslog = "-"
errorlog = "-"
