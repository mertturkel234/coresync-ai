from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai.providers import OpenAICompatibleProvider, build_context_block
from app.ai.retrieval import ScoredChunk
from app.core.errors import UpstreamError
from app.models import DocChunk
from tests.test_auth import auth_headers, register_developer, register_vendor

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples"


def _setup_project_with_docs(client: TestClient) -> tuple[dict, dict, dict]:
    vendor = register_vendor(client, email="vendor@orders.example", org="Orders Inc")
    dev = register_developer(client, email="dev@integrator.example")
    tenant_id = vendor["memberships"][0]["tenant_id"]

    client.post(
        f"/v1/tenants/{tenant_id}/members",
        headers=auth_headers(vendor["access_token"]),
        json={"email": "dev@integrator.example", "role": "developer"},
    )
    proj = client.post(
        "/v1/projects",
        headers=auth_headers(vendor["access_token"]),
        json={"tenant_id": tenant_id, "name": "Orders API", "description": "Orders"},
    ).json()

    openapi_bytes = (SAMPLES_DIR / "orders_openapi.json").read_bytes()
    client.post(
        f"/v1/projects/{proj['id']}/documents",
        headers=auth_headers(vendor["access_token"]),
        files={"file": ("orders.json", openapi_bytes, "application/json")},
    )
    md_bytes = (SAMPLES_DIR / "orders_guide.md").read_bytes()
    client.post(
        f"/v1/projects/{proj['id']}/documents",
        headers=auth_headers(vendor["access_token"]),
        files={"file": ("orders_guide.md", md_bytes, "text/markdown")},
    )
    return vendor, dev, proj


def test_grounded_qa_and_python_codegen_with_references(client: TestClient) -> None:
    vendor, dev, proj = _setup_project_with_docs(client)

    sess_r = client.post(
        f"/v1/projects/{proj['id']}/sessions",
        headers=auth_headers(dev["access_token"]),
        json={"title": "Order creation flow"},
    )
    assert sess_r.status_code == 201
    session = sess_r.json()

    ask_r = client.post(
        f"/v1/sessions/{session['id']}/messages",
        headers=auth_headers(dev["access_token"]),
        json={
            "question": (
                "How do I create an order with POST /demo/orders and what fields are required?"
            ),
            "generate_code": True,
        },
    )
    assert ask_r.status_code == 201, ask_r.text
    body = ask_r.json()

    assistant = body["assistant_message"]
    assert assistant["grounded"] is True
    assert assistant["mode"] == "offline"
    refs = [r["ref"] for r in assistant["references"]]
    assert "POST /demo/orders" in refs

    example = body["code_example"]
    assert example is not None
    assert example["execution_state"] == "not_executed"
    assert 'os.environ["CORESYNC_SANDBOX_KEY"]' in example["code"]
    assert "csk_" not in example["code"]
    assert example["request_plan"]["method"] == "POST"
    assert example["request_plan"]["path"] == "/demo/orders"
    assert example["request_plan"]["json_body"]["customer_ref"] == "cust_acme_42"

    # Vendor can review the developer's integration session in the project.
    vendor_sessions = client.get(
        f"/v1/projects/{proj['id']}/sessions",
        headers=auth_headers(vendor["access_token"]),
    ).json()
    assert any(s["id"] == session["id"] for s in vendor_sessions)

    detail = client.get(
        f"/v1/sessions/{session['id']}",
        headers=auth_headers(dev["access_token"]),
    ).json()
    assert len(detail["messages"]) == 2
    assert len(detail["code_examples"]) == 1


def test_missing_documentation_is_acknowledged_without_fabricating_code(
    client: TestClient,
) -> None:
    _, dev, proj = _setup_project_with_docs(client)
    session = client.post(
        f"/v1/projects/{proj['id']}/sessions",
        headers=auth_headers(dev["access_token"]),
        json={"title": "Unknown topic"},
    ).json()

    ask_r = client.post(
        f"/v1/sessions/{session['id']}/messages",
        headers=auth_headers(dev["access_token"]),
        json={"question": "How do I subscribe to GraphQL websocketblockchain events?"},
    )
    assert ask_r.status_code == 201
    data = ask_r.json()
    assert data["assistant_message"]["grounded"] is False
    assert data["assistant_message"]["references"] == []
    assert data["code_example"] is None
    assert "does not contain sufficient information" in data["assistant_message"]["content"]


def test_retrieval_and_sessions_never_cross_tenant_or_developer_boundaries(
    client: TestClient,
) -> None:
    vendor_a, dev_a, proj_a = _setup_project_with_docs(client)
    dev_a2 = register_developer(client, email="dev2@integrator.example")
    tenant_a = vendor_a["memberships"][0]["tenant_id"]
    client.post(
        f"/v1/tenants/{tenant_a}/members",
        headers=auth_headers(vendor_a["access_token"]),
        json={"email": "dev2@integrator.example", "role": "developer"},
    )

    # Tenant B has its own project with no documents uploaded.
    vendor_b = register_vendor(client, email="vb@other.example", org="Other Corp")
    tenant_b = vendor_b["memberships"][0]["tenant_id"]
    proj_b = client.post(
        "/v1/projects",
        headers=auth_headers(vendor_b["access_token"]),
        json={"tenant_id": tenant_b, "name": "Empty Project", "description": ""},
    ).json()
    sess_b = client.post(
        f"/v1/projects/{proj_b['id']}/sessions",
        headers=auth_headers(vendor_b["access_token"]),
        json={"title": "Probe"},
    ).json()

    # Asking about Tenant A's "/demo/orders" inside Tenant B finds nothing.
    probe = client.post(
        f"/v1/sessions/{sess_b['id']}/messages",
        headers=auth_headers(vendor_b["access_token"]),
        json={"question": "POST /demo/orders createOrder customer_ref"},
    ).json()
    assert probe["assistant_message"]["grounded"] is False
    assert probe["assistant_message"]["references"] == []
    assert probe["code_example"] is None

    # Developer A2 in Tenant A cannot access Developer A's session.
    sess_a = client.post(
        f"/v1/projects/{proj_a['id']}/sessions",
        headers=auth_headers(dev_a["access_token"]),
        json={"title": "Private session"},
    ).json()
    assert (
        client.get(
            f"/v1/sessions/{sess_a['id']}",
            headers=auth_headers(dev_a2["access_token"]),
        ).status_code
        == 404
    )


def test_openai_compatible_provider_wraps_untrusted_docs_and_maps_failures() -> None:
    chunk = DocChunk(
        kind="endpoint",
        ref="GET /demo/orders",
        title="GET /demo/orders",
        content="Endpoint: GET /demo/orders\nSummary: List orders",
    )
    scored = [ScoredChunk(chunk=chunk, score=2.5)]
    ctx = build_context_block(scored)
    assert "<untrusted_documentation>" in ctx
    assert "[ref: GET /demo/orders]" in ctx

    captured: dict = {}

    def ok_handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Use GET /demo/orders with X-Sandbox-Key."}}]
            },
        )

    provider = OpenAICompatibleProvider(
        base_url="https://llm.example/v1",
        api_key="sk-test-only",
        model="test-model",
        transport=httpx.MockTransport(ok_handler),
    )
    res = provider.generate("How to list orders?", scored)
    assert res.mode == "llm"
    assert "GET /demo/orders" in res.content
    assert "<untrusted_documentation>" in captured["body"]["messages"][1]["content"]

    def fail_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "overloaded"})

    failing = OpenAICompatibleProvider(
        base_url="https://llm.example/v1",
        api_key="sk-test-only",
        model="test-model",
        transport=httpx.MockTransport(fail_handler),
    )
    with pytest.raises(UpstreamError):
        failing.generate("How to list orders?", scored)
