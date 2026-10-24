from __future__ import annotations

from fastapi.testclient import TestClient


def register_vendor(
    client: TestClient,
    email: str = "vendor@acme.example",
    org: str = "Acme API",
    password: str = "correct-horse-battery",
) -> dict:
    r = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Ada Vendor",
            "account_type": "vendor",
            "organization_name": org,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def register_developer(
    client: TestClient,
    email: str = "dev@customer.example",
    password: str = "correct-horse-battery",
) -> dict:
    r = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Dev Integrator",
            "account_type": "developer",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_vendor_register_login_and_me(client: TestClient) -> None:
    reg = register_vendor(client)
    assert reg["token_type"] == "bearer"
    assert len(reg["memberships"]) == 1
    assert reg["memberships"][0]["role"] == "owner"
    assert reg["memberships"][0]["tenant_name"] == "Acme API"

    me = client.get("/v1/auth/me", headers=auth_headers(reg["access_token"]))
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "vendor@acme.example"

    login = client.post(
        "/v1/auth/login",
        json={"email": "VENDOR@acme.example", "password": "correct-horse-battery"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_duplicate_registration_rejected(client: TestClient) -> None:
    register_vendor(client)
    dup = client.post(
        "/v1/auth/register",
        json={
            "email": "VENDOR@acme.example",
            "password": "correct-horse-battery",
            "full_name": "Dup",
            "account_type": "developer",
        },
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "email_taken"


def test_login_errors_are_generic_and_do_not_leak_secrets(client: TestClient) -> None:
    register_vendor(client)
    wrong_pw = client.post(
        "/v1/auth/login",
        json={"email": "vendor@acme.example", "password": "wrong-password-123"},
    )
    unknown_user = client.post(
        "/v1/auth/login",
        json={"email": "nobody@acme.example", "password": "wrong-password-123"},
    )
    assert wrong_pw.status_code == 401
    assert unknown_user.status_code == 401
    assert wrong_pw.json()["error"]["message"] == unknown_user.json()["error"]["message"]
    assert "wrong-password-123" not in wrong_pw.text


def test_unauthenticated_and_tampered_tokens_rejected(client: TestClient) -> None:
    assert client.get("/v1/auth/me").status_code == 401
    assert (
        client.get("/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    )

    reg = register_vendor(client)
    tampered = reg["access_token"][:-4] + "aaaa"
    r = client.get("/v1/auth/me", headers=auth_headers(tampered))
    assert r.status_code == 401


def test_login_rate_limiting(client: TestClient) -> None:
    register_vendor(client)
    statuses = []
    for _ in range(12):
        r = client.post(
            "/v1/auth/login",
            json={"email": "vendor@acme.example", "password": "wrong-password-123"},
        )
        statuses.append(r.status_code)
    assert 429 in statuses
