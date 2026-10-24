from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from tests.test_auth import auth_headers, register_developer, register_vendor

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples"


def _create_project(client: TestClient, vendor: dict, name: str = "Orders API") -> dict:
    tenant_id = vendor["memberships"][0]["tenant_id"]
    r = client.post(
        "/v1/projects",
        headers=auth_headers(vendor["access_token"]),
        json={"tenant_id": tenant_id, "name": name, "description": "Orders"},
    )
    assert r.status_code == 201
    return r.json()


def test_openapi_json_and_yaml_and_markdown_ingestion(client: TestClient) -> None:
    vendor = register_vendor(client)
    proj = _create_project(client, vendor)
    headers = auth_headers(vendor["access_token"])

    openapi_bytes = (SAMPLES_DIR / "orders_openapi.json").read_bytes()
    r1 = client.post(
        f"/v1/projects/{proj['id']}/documents",
        headers=headers,
        files={"file": ("orders.json", openapi_bytes, "application/json")},
    )
    assert r1.status_code == 201, r1.text
    doc1 = r1.json()
    assert doc1["status"] == "processed"
    assert doc1["version"] == 1
    assert doc1["endpoint_count"] == 3
    assert doc1["title"] == "Acme Orders Demo API"

    # Re-uploading the same filename increments version to 2.
    r2 = client.post(
        f"/v1/projects/{proj['id']}/documents",
        headers=headers,
        files={"file": ("orders.json", openapi_bytes, "application/json")},
    )
    assert r2.status_code == 201
    assert r2.json()["version"] == 2

    # YAML upload also succeeds.
    yaml_bytes = yaml.safe_dump(json.loads(openapi_bytes.decode())).encode()
    r_yaml = client.post(
        f"/v1/projects/{proj['id']}/documents",
        headers=headers,
        files={"file": ("orders.yaml", yaml_bytes, "application/x-yaml")},
    )
    assert r_yaml.status_code == 201
    assert r_yaml.json()["status"] == "processed"
    assert r_yaml.json()["doc_type"] == "openapi_yaml"

    # Markdown upload succeeds.
    md_bytes = (SAMPLES_DIR / "orders_guide.md").read_bytes()
    r_md = client.post(
        f"/v1/projects/{proj['id']}/documents",
        headers=headers,
        files={"file": ("orders_guide.md", md_bytes, "text/markdown")},
    )
    assert r_md.status_code == 201
    assert r_md.json()["status"] == "processed"
    assert r_md.json()["doc_type"] == "markdown"

    # List documents and endpoints.
    docs = client.get(f"/v1/projects/{proj['id']}/documents", headers=headers).json()
    assert len(docs) == 4

    endpoints = client.get(f"/v1/projects/{proj['id']}/endpoints", headers=headers).json()
    methods_paths = {(e["method"], e["path"]) for e in endpoints}
    assert ("GET", "/demo/orders") in methods_paths
    assert ("POST", "/demo/orders") in methods_paths
    assert ("GET", "/demo/orders/{order_id}") in methods_paths

    # Local $ref was resolved inside POST /demo/orders requestBody schema.
    post_ep = next(e for e in endpoints if e["method"] == "POST" and e["path"] == "/demo/orders")
    schema = post_ep["request_body"]["content"]["application/json"]["schema"]
    assert "customer_ref" in schema["properties"]

    ep_detail = client.get(f"/v1/projects/{proj['id']}/endpoints/{post_ep['id']}", headers=headers)
    assert ep_detail.status_code == 200
    assert ep_detail.json()["operation_id"] == "createOrder"


def test_invalid_and_unsafe_documents_are_rejected_safely(client: TestClient) -> None:
    vendor = register_vendor(client)
    proj = _create_project(client, vendor)
    headers = auth_headers(vendor["access_token"])

    # Unsupported extension -> 422 before creating a document record.
    bad_ext = client.post(
        f"/v1/projects/{proj['id']}/documents",
        headers=headers,
        files={"file": ("script.exe", b"hello", "application/octet-stream")},
    )
    assert bad_ext.status_code == 422

    # Binary content -> 422.
    binary = client.post(
        f"/v1/projects/{proj['id']}/documents",
        headers=headers,
        files={"file": ("bad.json", b"\x00\x01\x02", "application/json")},
    )
    assert binary.status_code == 422

    # External $ref (SSRF attempt) -> recorded as failed with validation_errors and HTTP 422.
    ssrf_spec = {
        "openapi": "3.0.0",
        "info": {"title": "Bad", "version": "1.0"},
        "paths": {
            "/items": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "http://169.254.169.254/latest/meta-data/"}
                                }
                            },
                        }
                    }
                }
            }
        },
    }
    r_ssrf = client.post(
        f"/v1/projects/{proj['id']}/documents",
        headers=headers,
        files={"file": ("ssrf.json", json.dumps(ssrf_spec).encode(), "application/json")},
    )
    assert r_ssrf.status_code == 422
    body = r_ssrf.json()
    assert body["status"] == "failed"
    assert any("External or unsupported $ref" in err for err in body["validation_errors"])

    # YAML anchor/alias bomb -> rejected with status=failed.
    yaml_alias = (
        b"openapi: '3.0.0'\ninfo: &a\n  title: T\n  version: '1'\n"
        b"paths:\n  /x:\n    get:\n      <<: *a\n"
        b"      responses:\n        '200':\n          description: ok\n"
    )
    r_alias = client.post(
        f"/v1/projects/{proj['id']}/documents",
        headers=headers,
        files={"file": ("bomb.yaml", yaml_alias, "application/x-yaml")},
    )
    assert r_alias.status_code == 422
    assert r_alias.json()["status"] == "failed"
    assert any("anchors and aliases" in e for e in r_alias.json()["validation_errors"])


def test_document_and_endpoint_ownership_boundaries(client: TestClient) -> None:
    vendor_a = register_vendor(client, email="va@a.example", org="Org A")
    vendor_b = register_vendor(client, email="vb@b.example", org="Org B")
    dev = register_developer(client, email="dev@a.example")

    proj_a = _create_project(client, vendor_a)
    tenant_a = vendor_a["memberships"][0]["tenant_id"]
    client.post(
        f"/v1/tenants/{tenant_a}/members",
        headers=auth_headers(vendor_a["access_token"]),
        json={"email": "dev@a.example", "role": "developer"},
    )

    openapi_bytes = (SAMPLES_DIR / "orders_openapi.json").read_bytes()
    doc = client.post(
        f"/v1/projects/{proj_a['id']}/documents",
        headers=auth_headers(vendor_a["access_token"]),
        files={"file": ("orders.json", openapi_bytes, "application/json")},
    ).json()

    # Developer in Org A can view documents and endpoints, but cannot upload.
    assert (
        client.get(
            f"/v1/projects/{proj_a['id']}/documents/{doc['id']}",
            headers=auth_headers(dev["access_token"]),
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/v1/projects/{proj_a['id']}/documents",
            headers=auth_headers(dev["access_token"]),
            files={"file": ("orders.json", openapi_bytes, "application/json")},
        ).status_code
        == 403
    )

    # Vendor B in Org B gets 404 on every Org A document/endpoint route.
    assert (
        client.get(
            f"/v1/projects/{proj_a['id']}/documents",
            headers=auth_headers(vendor_b["access_token"]),
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/v1/projects/{proj_a['id']}/documents/{doc['id']}",
            headers=auth_headers(vendor_b["access_token"]),
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/v1/projects/{proj_a['id']}/endpoints",
            headers=auth_headers(vendor_b["access_token"]),
        ).status_code
        == 404
    )
