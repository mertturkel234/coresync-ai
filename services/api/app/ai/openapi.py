"""Controlled OpenAPI 3.x JSON/YAML parser and validator.

Security properties (ADR-005, docs/SECURITY.md):
- YAML is parsed with SafeLoader and any anchor/alias token is rejected before object construction.
- External $ref values (anything not starting with '#/') are rejected to prevent SSRF / file reads.
- Local '#/' references are resolved with cycle and depth limits.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import yaml

ALLOWED_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
MAX_REF_DEPTH = 12
MAX_TREE_DEPTH = 64


@dataclass
class EndpointSpec:
    method: str
    path: str
    operation_id: str | None
    summary: str
    description: str
    tags: list[str]
    parameters: list[dict[str, Any]]
    request_body: dict[str, Any] | None
    responses: dict[str, Any]
    security: list[dict[str, Any]]
    source: str = "openapi"


@dataclass
class ChunkSpec:
    kind: str  # endpoint | schema | section
    ref: str
    title: str
    content: str
    endpoint_key: tuple[str, str] | None = None


@dataclass
class ParsedOpenAPI:
    title: str
    api_version: str
    server_url: str | None
    endpoints: list[EndpointSpec] = field(default_factory=list)
    chunks: list[ChunkSpec] = field(default_factory=list)


class OpenAPIValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def _load_yaml_without_aliases(text: str) -> Any:
    try:
        tokens = list(yaml.scan(text, Loader=yaml.SafeLoader))
    except yaml.YAMLError as exc:
        raise OpenAPIValidationError([f"Invalid YAML syntax: {exc}"]) from exc
    for tok in tokens:
        if isinstance(tok, yaml.AnchorToken | yaml.AliasToken):
            raise OpenAPIValidationError(
                ["YAML anchors and aliases are not permitted in uploaded specifications."]
            )
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise OpenAPIValidationError([f"Invalid YAML content: {exc}"]) from exc


def _load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenAPIValidationError(
            [f"Invalid JSON syntax at line {exc.lineno}: {exc.msg}"]
        ) from exc


def _lookup_pointer(root: dict[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise OpenAPIValidationError(
            [f"External or unsupported $ref '{ref}'. Only local '#/' references are allowed."]
        )
    parts = [p.replace("~1", "/").replace("~0", "~") for p in ref[2:].split("/")]
    cur: Any = root
    for part in parts:
        if not isinstance(cur, dict) or part not in cur:
            raise OpenAPIValidationError([f"Unresolvable local $ref '{ref}'."])
        cur = cur[part]
    return cur


def _resolve_refs(
    node: Any, root: dict[str, Any], seen: tuple[str, ...] = (), depth: int = 0
) -> Any:
    if len(seen) > MAX_REF_DEPTH or depth > MAX_TREE_DEPTH:
        raise OpenAPIValidationError(["Maximum $ref resolution depth exceeded."])
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if not isinstance(ref, str):
                raise OpenAPIValidationError(["$ref value must be a string."])
            if ref in seen:
                return {"type": "object", "description": f"Recursive reference to {ref}"}
            target = _lookup_pointer(root, ref)
            return _resolve_refs(target, root, (*seen, ref), depth + 1)
        return {str(k): _resolve_refs(v, root, seen, depth + 1) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve_refs(item, root, seen, depth + 1) for item in node]
    return node


def _format_endpoint_chunk(
    method: str,
    path: str,
    summary: str,
    description: str,
    parameters: list[dict[str, Any]],
    request_body: dict[str, Any] | None,
    responses: dict[str, Any],
    security: list[dict[str, Any]],
    security_schemes: dict[str, Any],
) -> str:
    lines = [f"Endpoint: {method} {path}"]
    if summary:
        lines.append(f"Summary: {summary}")
    if description:
        lines.append(f"Description: {description}")
    if security:
        sec_names = []
        for item in security:
            if isinstance(item, dict):
                for name in item:
                    scheme = security_schemes.get(name, {})
                    header = scheme.get("name") or name
                    sec_type = scheme.get("type", "auth")
                    sec_names.append(f"{name} ({sec_type}, header/param: {header})")
        if sec_names:
            lines.append("Authentication: " + ", ".join(sec_names))
    if parameters:
        param_bits = []
        for p in parameters:
            pname = p.get("name", "param")
            pin = p.get("in", "query")
            req = "required" if p.get("required") else "optional"
            pschema = p.get("schema", {}) if isinstance(p.get("schema"), dict) else {}
            ptype = pschema.get("type", "string")
            param_bits.append(f"{pname} ({pin}, {ptype}, {req})")
        lines.append("Parameters: " + "; ".join(param_bits))
    if request_body and isinstance(request_body, dict):
        content = request_body.get("content", {})
        json_media = content.get("application/json", {}) if isinstance(content, dict) else {}
        schema = json_media.get("schema", {}) if isinstance(json_media, dict) else {}
        if isinstance(schema, dict) and schema.get("properties"):
            props = []
            required_set = set(schema.get("required") or [])
            for k, v in schema["properties"].items():
                vtype = v.get("type", "any") if isinstance(v, dict) else "any"
                tag = "required" if k in required_set else "optional"
                props.append(f"{k}:{vtype} ({tag})")
            lines.append("Request JSON fields: " + ", ".join(props))
    if responses:
        resp_bits = []
        for code, rspec in responses.items():
            rdesc = rspec.get("description", "") if isinstance(rspec, dict) else ""
            resp_bits.append(f"{code} ({rdesc})" if rdesc else str(code))
        lines.append("Responses: " + "; ".join(resp_bits))
    return "\n".join(lines)


def parse_openapi(text: str, *, is_yaml: bool, max_endpoints: int = 2000) -> ParsedOpenAPI:
    raw = _load_yaml_without_aliases(text) if is_yaml else _load_json(text)
    if not isinstance(raw, dict):
        raise OpenAPIValidationError(["OpenAPI document root must be a JSON/YAML object."])

    errors: list[str] = []
    openapi_ver = raw.get("openapi")
    if not isinstance(openapi_ver, str) or not openapi_ver.startswith("3."):
        errors.append("Field 'openapi' must be a string starting with '3.' (OpenAPI 3.x).")

    info = raw.get("info")
    if not isinstance(info, dict):
        errors.append("Field 'info' must be an object containing 'title' and 'version'.")
        title, api_version = "", ""
    else:
        title = str(info.get("title") or "").strip()
        api_version = str(info.get("version") or "").strip()
        if not title:
            errors.append("Field 'info.title' is required.")
        if not api_version:
            errors.append("Field 'info.version' is required.")

    paths = raw.get("paths")
    if not isinstance(paths, dict) or not paths:
        errors.append("Field 'paths' must be a non-empty object.")

    if errors:
        raise OpenAPIValidationError(errors)

    resolved = _resolve_refs(raw, raw)
    servers = resolved.get("servers")
    server_url: str | None = None
    if isinstance(servers, list) and servers and isinstance(servers[0], dict):
        url_val = servers[0].get("url")
        if isinstance(url_val, str) and url_val.strip():
            server_url = url_val.strip()

    global_security = resolved.get("security")
    if not isinstance(global_security, list):
        global_security = []

    components = resolved.get("components") if isinstance(resolved.get("components"), dict) else {}
    security_schemes = (
        components.get("securitySchemes")
        if isinstance(components.get("securitySchemes"), dict)
        else {}
    )
    schemas = components.get("schemas") if isinstance(components.get("schemas"), dict) else {}

    endpoints: list[EndpointSpec] = []
    chunks: list[ChunkSpec] = []

    for path_key, path_item in resolved["paths"].items():
        if not isinstance(path_key, str) or not path_key.startswith("/"):
            raise OpenAPIValidationError([f"Path '{path_key}' must start with '/'."])
        if not isinstance(path_item, dict):
            raise OpenAPIValidationError([f"Path item for '{path_key}' must be an object."])
        path_params = (
            path_item.get("parameters") if isinstance(path_item.get("parameters"), list) else []
        )

        for method_lower in ALLOWED_HTTP_METHODS:
            if method_lower not in path_item:
                continue
            op = path_item[method_lower]
            if not isinstance(op, dict):
                raise OpenAPIValidationError(
                    [f"Operation '{method_lower.upper()} {path_key}' must be an object."]
                )
            method = method_lower.upper()
            op_params = op.get("parameters") if isinstance(op.get("parameters"), list) else []
            merged_params = [p for p in (*path_params, *op_params) if isinstance(p, dict)]
            responses = op.get("responses") if isinstance(op.get("responses"), dict) else {}
            if not responses:
                raise OpenAPIValidationError(
                    [f"Operation '{method} {path_key}' must define at least one response."]
                )
            op_security = (
                op.get("security") if isinstance(op.get("security"), list) else global_security
            )
            summary = str(op.get("summary") or "").strip()
            description = str(op.get("description") or "").strip()
            operation_id = str(op.get("operationId")).strip() if op.get("operationId") else None
            tags = [str(t) for t in (op.get("tags") or []) if isinstance(t, str | int)]
            request_body = (
                op.get("requestBody") if isinstance(op.get("requestBody"), dict) else None
            )

            spec = EndpointSpec(
                method=method,
                path=path_key,
                operation_id=operation_id,
                summary=summary,
                description=description,
                tags=tags,
                parameters=merged_params,
                request_body=request_body,
                responses=responses,
                security=[s for s in op_security if isinstance(s, dict)],
            )
            endpoints.append(spec)
            if len(endpoints) > max_endpoints:
                raise OpenAPIValidationError(
                    [f"Document exceeds the maximum of {max_endpoints} endpoints."]
                )

            ref_label = f"{method} {path_key}"
            chunk_title = f"{ref_label} — {summary}" if summary else ref_label
            chunk_text = _format_endpoint_chunk(
                method=method,
                path=path_key,
                summary=summary,
                description=description,
                parameters=merged_params,
                request_body=request_body,
                responses=responses,
                security=spec.security,
                security_schemes=security_schemes,
            )
            chunks.append(
                ChunkSpec(
                    kind="endpoint",
                    ref=ref_label,
                    title=chunk_title,
                    content=chunk_text,
                    endpoint_key=(method, path_key),
                )
            )

    if not endpoints:
        raise OpenAPIValidationError(
            ["OpenAPI specification does not contain any HTTP operations."]
        )

    for schema_name, schema_obj in schemas.items():
        if not isinstance(schema_obj, dict):
            continue
        props = (
            schema_obj.get("properties") if isinstance(schema_obj.get("properties"), dict) else {}
        )
        req = set(schema_obj.get("required") or [])
        prop_desc = ", ".join(
            f"{k}:{v.get('type', 'any')} ({'required' if k in req else 'optional'})"
            for k, v in props.items()
            if isinstance(v, dict)
        )
        chunks.append(
            ChunkSpec(
                kind="schema",
                ref=f"schema:{schema_name}",
                title=f"Schema {schema_name}",
                content=f"Schema {schema_name}: {prop_desc or json.dumps(schema_obj)[:500]}",
            )
        )

    return ParsedOpenAPI(
        title=title,
        api_version=api_version,
        server_url=server_url,
        endpoints=endpoints,
        chunks=chunks,
    )
