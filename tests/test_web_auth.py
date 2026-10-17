"""Authentication checks use synthetic credentials and never call the LLM."""

from base64 import b64encode

import pytest

from web.app import app, sessions


def basic(username, password):
    token = b64encode(f"{username}:{password}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(app.config, "TESTING", True)
    monkeypatch.setitem(app.config, "BASIC_AUTH_USERNAME", "demo")
    monkeypatch.setitem(app.config, "BASIC_AUTH_PASSWORD", "synthetic-password")
    sessions.clear()
    with app.test_client() as client:
        yield client
    sessions.clear()


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/patient",
        "/team",
        "/patients/ONC-004/report",
        "/static/style.css",
        "/missing",
    ],
)
@pytest.mark.parametrize("method", ["GET", "POST", "HEAD"])
def test_all_requests_require_authentication(client, path, method):
    response = client.open(path, method=method)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic ")
    assert response.headers["Cache-Control"] == "no-store"
    assert "Set-Cookie" not in response.headers
    assert not sessions


@pytest.mark.parametrize(
    "headers",
    [
        basic("demo", "wrong"),
        basic("wrong", "synthetic-password"),
        basic("", ""),
        {"Authorization": "Basic !!!"},
        {"Authorization": "Basic ZGVtbw=="},
        {"Authorization": "Bearer synthetic-token"},
    ],
)
def test_invalid_credentials_are_rejected(client, headers):
    assert client.get("/", headers=headers).status_code == 401
    assert not sessions


@pytest.mark.parametrize(
    "username,password", [("", ""), ("demo", ""), ("", "secret"), ("a:b", "secret")]
)
def test_incomplete_configuration_denies_even_authenticated_requests(
    client, monkeypatch, username, password
):
    monkeypatch.setitem(app.config, "BASIC_AUTH_USERNAME", username)
    monkeypatch.setitem(app.config, "BASIC_AUTH_PASSWORD", password)
    response = client.get("/", headers=basic("demo", "synthetic-password"))
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    assert not sessions


@pytest.mark.parametrize("path", ["/", "/static/style.css", "/patients/ONC-004/report"])
def test_valid_credentials_allow_access(client, path):
    assert (
        client.get(path, headers=basic("demo", "synthetic-password")).status_code == 200
    )


def test_authenticated_post_and_session_do_not_bypass_auth(client):
    response = client.post(
        "/patient",
        data={"patient_id": "ONC-004"},
        headers=basic("demo", "synthetic-password"),
    )
    assert response.status_code == 302
    assert client.get("/").status_code == 401


def test_unicode_credentials_and_colon_in_password(client, monkeypatch):
    monkeypatch.setitem(app.config, "BASIC_AUTH_USERNAME", "tým")
    monkeypatch.setitem(app.config, "BASIC_AUTH_PASSWORD", "heslo:žluťoučké")
    assert client.get("/", headers=basic("tým", "heslo:žluťoučké")).status_code == 200
