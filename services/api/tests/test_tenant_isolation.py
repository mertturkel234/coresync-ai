from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.test_auth import auth_headers, register_developer, register_vendor


def test_cross_tenant_project_access_is_rejected_with_404(client: TestClient) -> None:
    vendor_a = register_vendor(client, email="a@tenant-a.example", org="Tenant A")
    vendor_b = register_vendor(client, email="b@tenant-b.example", org="Tenant B")

    tenant_a_id = vendor_a["memberships"][0]["tenant_id"]
    tenant_b_id = vendor_b["memberships"][0]["tenant_id"]

    proj_r = client.post(
        "/v1/projects",
        headers=auth_headers(vendor_a["access_token"]),
        json={"tenant_id": tenant_a_id, "name": "Payments API", "description": "Core payments"},
    )
    assert proj_r.status_code == 201
    project_id = proj_r.json()["id"]

    # Vendor B cannot view, update, or list Vendor A's project, nor create in Tenant A.
    get_b = client.get(f"/v1/projects/{project_id}", headers=auth_headers(vendor_b["access_token"]))
    assert get_b.status_code == 404

    patch_b = client.patch(
        f"/v1/projects/{project_id}",
        headers=auth_headers(vendor_b["access_token"]),
        json={"name": "Hijacked"},
    )
    assert patch_b.status_code == 404

    create_in_a = client.post(
        "/v1/projects",
        headers=auth_headers(vendor_b["access_token"]),
        json={"tenant_id": tenant_a_id, "name": "Injected", "description": ""},
    )
    assert create_in_a.status_code == 404

    list_b = client.get("/v1/projects", headers=auth_headers(vendor_b["access_token"]))
    assert list_b.status_code == 200
    assert list_b.json() == []

    # Vendor B cannot inspect Tenant A's members or audit events.
    assert (
        client.get(
            f"/v1/tenants/{tenant_a_id}/members", headers=auth_headers(vendor_b["access_token"])
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/v1/tenants/{tenant_a_id}/audit-events",
            headers=auth_headers(vendor_b["access_token"]),
        ).status_code
        == 404
    )
    assert tenant_b_id != tenant_a_id


def test_developer_role_permissions_and_archived_visibility(client: TestClient) -> None:
    vendor = register_vendor(client, email="owner@acme.example", org="Acme")
    dev = register_developer(client, email="dev@partner.example")
    tenant_id = vendor["memberships"][0]["tenant_id"]

    proj = client.post(
        "/v1/projects",
        headers=auth_headers(vendor["access_token"]),
        json={"tenant_id": tenant_id, "name": "Orders API", "description": "v1"},
    ).json()

    # Before invite, developer cannot see the project.
    assert (
        client.get(
            f"/v1/projects/{proj['id']}", headers=auth_headers(dev["access_token"])
        ).status_code
        == 404
    )

    # Vendor invites developer.
    add = client.post(
        f"/v1/tenants/{tenant_id}/members",
        headers=auth_headers(vendor["access_token"]),
        json={"email": "dev@partner.example", "role": "developer"},
    )
    assert add.status_code == 201
    assert add.json()["role"] == "developer"

    # Developer can now view and list the project, but cannot create/update projects or view audits.
    get_dev = client.get(f"/v1/projects/{proj['id']}", headers=auth_headers(dev["access_token"]))
    assert get_dev.status_code == 200
    assert get_dev.json()["role"] == "developer"

    create_dev = client.post(
        "/v1/projects",
        headers=auth_headers(dev["access_token"]),
        json={"tenant_id": tenant_id, "name": "Nope", "description": ""},
    )
    assert create_dev.status_code == 403

    patch_dev = client.patch(
        f"/v1/projects/{proj['id']}",
        headers=auth_headers(dev["access_token"]),
        json={"name": "Renamed"},
    )
    assert patch_dev.status_code == 403

    audit_dev = client.get(
        f"/v1/tenants/{tenant_id}/audit-events", headers=auth_headers(dev["access_token"])
    )
    assert audit_dev.status_code == 403

    # Archiving hides the project from developers while remaining visible to vendors.
    arch = client.patch(
        f"/v1/projects/{proj['id']}",
        headers=auth_headers(vendor["access_token"]),
        json={"archived": True},
    )
    assert arch.status_code == 200
    assert arch.json()["archived"] is True

    assert (
        client.get(
            f"/v1/projects/{proj['id']}", headers=auth_headers(dev["access_token"])
        ).status_code
        == 404
    )
    assert client.get("/v1/projects", headers=auth_headers(dev["access_token"])).json() == []
    assert len(client.get("/v1/projects", headers=auth_headers(vendor["access_token"])).json()) == 1


def test_audit_events_record_actions_without_secrets(client: TestClient) -> None:
    vendor = register_vendor(
        client, email="sec@acme.example", org="Acme", password="super-secret-password"
    )
    tenant_id = vendor["memberships"][0]["tenant_id"]

    client.post(
        "/v1/projects",
        headers=auth_headers(vendor["access_token"]),
        json={"tenant_id": tenant_id, "name": "Billing API", "description": ""},
    )
    events_r = client.get(
        f"/v1/tenants/{tenant_id}/audit-events", headers=auth_headers(vendor["access_token"])
    )
    assert events_r.status_code == 200
    actions = [e["action"] for e in events_r.json()]
    assert "project.create" in actions
    assert "auth.register" in actions
    assert "super-secret-password" not in events_r.text
    assert vendor["access_token"] not in events_r.text
    assert (
        client.get(
            f"/v1/projects/{uuid.uuid4()}", headers=auth_headers(vendor["access_token"])
        ).status_code
        == 404
    )
