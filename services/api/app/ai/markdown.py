"""Markdown documentation parser and section chunker."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ai.openapi import ChunkSpec, EndpointSpec

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
_ENDPOINT_HEADING_RE = re.compile(
    r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;={}-]*)\b",
    re.IGNORECASE,
)


@dataclass
class ParsedMarkdown:
    title: str
    endpoints: list[EndpointSpec] = field(default_factory=list)
    chunks: list[ChunkSpec] = field(default_factory=list)


class MarkdownValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def parse_markdown(text: str, *, filename: str) -> ParsedMarkdown:
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_heading = filename
    current_lines: list[str] = []
    doc_title: str | None = None

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = m.group(2).strip()
            if doc_title is None:
                doc_title = current_heading
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    chunks: list[ChunkSpec] = []
    endpoints: list[EndpointSpec] = []
    for idx, (heading, body_lines) in enumerate(sections, start=1):
        body = "\n".join(body_lines).strip()
        if not body and heading == filename:
            continue
        content = f"{heading}\n{body}".strip()
        ep_match = _ENDPOINT_HEADING_RE.match(heading)
        if ep_match:
            method = ep_match.group(1).upper()
            path = ep_match.group(2)
            endpoints.append(
                EndpointSpec(
                    method=method,
                    path=path,
                    operation_id=None,
                    summary=heading,
                    description=body[:2000],
                    tags=["markdown"],
                    parameters=[],
                    request_body=None,
                    responses={"200": {"description": "Documented in Markdown"}},
                    security=[],
                    source="markdown",
                )
            )
            chunks.append(
                ChunkSpec(
                    kind="endpoint",
                    ref=f"{method} {path}",
                    title=heading,
                    content=content[:4000],
                    endpoint_key=(method, path),
                )
            )
        else:
            chunks.append(
                ChunkSpec(
                    kind="section",
                    ref=f"{filename}#section-{idx}",
                    title=heading[:300],
                    content=content[:4000],
                )
            )

    if not chunks:
        raise MarkdownValidationError(["Markdown document does not contain any readable content."])

    return ParsedMarkdown(title=doc_title or filename, endpoints=endpoints, chunks=chunks)
