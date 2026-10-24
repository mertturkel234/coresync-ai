"""Redaction of secrets from text and structured data (audit metadata, run output, logs)."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEY = re.compile(
    r"(pass(word)?|secret|token|authorization|api[-_]?key|cookie|credential|csk)", re.IGNORECASE
)

_PATTERNS = [
    re.compile(r"csk_[A-Za-z0-9_-]{6,}"),  # CoreSync sandbox credentials
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # JWTs
    re.compile(r"(?i)\b(sk|pk|ghp|gho|xox[abp])[-_][A-Za-z0-9_-]{16,}"),  # common API key shapes
    re.compile(r"(?i)(password|passwd|secret|api[_-]?key|token)(\"?\s*[:=]\s*\"?)[^\s\",;&}]{4,}"),
]


def redact_text(text: str) -> str:
    out = text
    for pat in _PATTERNS[:-1]:
        out = pat.sub(REDACTED, out)
    out = _PATTERNS[-1].sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", out)
    return out


def scrub(value: Any, _depth: int = 0) -> Any:
    """Recursively redact dictionary values under sensitive keys and secret-looking strings."""
    if _depth > 8:
        return REDACTED
    if isinstance(value, dict):
        return {
            str(k): (REDACTED if _SENSITIVE_KEY.search(str(k)) else scrub(v, _depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [scrub(v, _depth + 1) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
