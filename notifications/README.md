# Notifications

One email field sends the predefined `SUBJECT` and `BODY` in `app.py`.
No recipient, subject, or message is read from patient data.

Copy `.env.example` to `.env` in this directory and replace the SMTP settings
with your provider's values. `SMTP_FROM` must be an address your server allows
you to send from. `SMTP_SECURITY=starttls` uses port 587 by default;
`SMTP_SECURITY=ssl` uses port 465. Leave both username and password empty only
if your server allows unauthenticated sending over TLS.

Run from the repository root on Linux or Windows PowerShell:

```text
uv run --env-file notifications/.env python notifications/app.py
```

Open `http://127.0.0.1:5000`. Enter a recipient and press **Send notification**.
The app reports success only after the SMTP server accepts the message;
this does not confirm inbox delivery. Local `.env` files are ignored by Git.

Tests use a mocked SMTP connection and never send real messages:

```text
uv run --locked pytest tests/test_notifications.py -q
```
