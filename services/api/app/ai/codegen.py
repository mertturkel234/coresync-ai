"""Deterministic request-plan construction and Python integration code generation.

Tool/execution arguments (the RequestPlan) are derived strictly from the indexed Endpoint record on
the server, never parsed from free-form LLM output (docs/SECURITY.md section 5).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.models import Endpoint


def _sample_value(schema: dict[str, Any], field_name: str = "value") -> Any:
    if "example" in schema:
        return schema["example"]
    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]
    stype = schema.get("type", "string")
    if stype == "integer":
        return max(int(schema.get("minimum", 1)), 1)
    if stype == "number":
        return float(schema.get("minimum", 1.0))
    if stype == "boolean":
        return True
    if stype == "array":
        item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        return [_sample_value(item_schema, field_name)]
    if stype == "object":
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        return {k: _sample_value(v, k) for k, v in props.items() if isinstance(v, dict)}
    return f"sample_{field_name}"


def build_request_plan(endpoint: Endpoint) -> dict[str, Any]:
    path = endpoint.path
    query_params: dict[str, Any] = {}

    for param in endpoint.parameters:
        if not isinstance(param, dict):
            continue
        pname = str(param.get("name") or "param")
        pin = str(param.get("in") or "query")
        pschema = param.get("schema") if isinstance(param.get("schema"), dict) else {}
        sample = _sample_value(pschema, pname)
        if pin == "path":
            path = path.replace("{" + pname + "}", str(sample))
        elif pin == "query" and param.get("required", False):
            query_params[pname] = sample

    json_body: Any = None
    if isinstance(endpoint.request_body, dict):
        content = endpoint.request_body.get("content")
        if isinstance(content, dict) and isinstance(content.get("application/json"), dict):
            schema = content["application/json"].get("schema")
            if isinstance(schema, dict):
                json_body = _sample_value(schema, "body")

    return {
        "method": endpoint.method.upper(),
        "path": path,
        "path_template": endpoint.path,
        "query": query_params,
        "json_body": json_body,
        "headers": {"X-Sandbox-Key": "${CORESYNC_SANDBOX_KEY}"},
    }


def generate_python_example(
    endpoint: Endpoint, *, base_url_placeholder: str = "http://localhost:8000"
) -> tuple[str, str, dict[str, Any]]:
    """Return (python_code, code_sha256, request_plan)."""
    plan = build_request_plan(endpoint)
    method = plan["method"]
    path = plan["path"]
    query_repr = repr(plan["query"]) if plan["query"] else "None"
    body_json = json.dumps(plan["json_body"], indent=4) if plan["json_body"] is not None else "None"
    summary_comment = f"# {endpoint.method} {endpoint.path}" + (
        f" — {endpoint.summary}" if endpoint.summary else ""
    )

    lines = [
        '"""CoreSync AI generated Python integration example.',
        "",
        "Status: GENERATED ONLY (not yet executed). Use a scoped sandbox credential to run a test.",
        '"""',
        "",
        "import os",
        "import httpx",
        "",
        summary_comment,
        f'BASE_URL = os.environ.get("CORESYNC_BASE_URL", "{base_url_placeholder}")',
        "# Never hardcode credentials; set CORESYNC_SANDBOX_KEY in your environment.",
        'SANDBOX_KEY = os.environ["CORESYNC_SANDBOX_KEY"]',
        "",
        "def run_integration_example() -> dict:",
        f'    url = f"{{BASE_URL}}{path}"',
        '    headers = {"X-Sandbox-Key": SANDBOX_KEY, "Accept": "application/json"}',
        f"    params = {query_repr}",
    ]
    if plan["json_body"] is not None:
        lines.append(f"    payload = {body_json}")
        call_line = (
            f'        response = client.request("{method}", url, headers=headers, '
            "params=params, json=payload)"
        )
    else:
        call_line = (
            f'        response = client.request("{method}", url, headers=headers, params=params)'
        )

    lines.extend(
        [
            "    with httpx.Client(timeout=10.0) as client:",
            call_line,
            "        response.raise_for_status()",
            "        return response.json()",
            "",
            'if __name__ == "__main__":',
            "    print(run_integration_example())",
            "",
        ]
    )
    code = "\n".join(lines)
    code_sha256 = hashlib.sha256(code.encode("utf-8")).hexdigest()
    return code, code_sha256, plan
