"""Secure document storage on disk with random keys and sanitized display filenames."""

from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from app.core.errors import PayloadTooLargeError, ValidationFailedError
from app.models import DocType

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")

EXTENSION_TO_DOCTYPE: dict[str, DocType] = {
    ".json": DocType.OPENAPI_JSON,
    ".yaml": DocType.OPENAPI_YAML,
    ".yml": DocType.OPENAPI_YAML,
    ".md": DocType.MARKDOWN,
    ".markdown": DocType.MARKDOWN,
}


def sanitize_filename(raw_name: str | None) -> tuple[str, DocType]:
    if not raw_name:
        raise ValidationFailedError("A filename with a supported extension is required.")
    base = Path(raw_name).name.strip()
    cleaned = _SAFE_FILENAME.sub("_", base).strip("._")
    if not cleaned or len(cleaned) > 200:
        raise ValidationFailedError("Invalid filename.")
    ext = Path(cleaned).suffix.lower()
    doc_type = EXTENSION_TO_DOCTYPE.get(ext)
    if doc_type is None:
        raise ValidationFailedError(
            "Unsupported file extension. Supported extensions: .json, .yaml, .yml, .md, .markdown."
        )
    return cleaned, doc_type


def validate_and_decode_bytes(raw: bytes, *, max_bytes: int) -> tuple[str, str]:
    """Validate size and UTF-8 encoding; return (decoded_text, sha256_hex)."""
    if len(raw) == 0:
        raise ValidationFailedError("Uploaded file is empty.")
    if len(raw) > max_bytes:
        raise PayloadTooLargeError(f"File exceeds the maximum size of {max_bytes} bytes.")
    if b"\x00" in raw:
        raise ValidationFailedError("Binary files are not allowed; upload UTF-8 text only.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationFailedError("File must be valid UTF-8 text.") from exc
    if not text.strip():
        raise ValidationFailedError("Uploaded file contains only whitespace.")
    sha256 = hashlib.sha256(raw).hexdigest()
    return text, sha256


def store_document_bytes(storage_dir: str, tenant_id: uuid.UUID, raw: bytes) -> str:
    """Write bytes under a random storage key (never derived from user input)."""
    root = Path(storage_dir).resolve()
    tenant_folder = (root / str(tenant_id)).resolve()
    if root not in tenant_folder.parents and tenant_folder != root:
        raise ValidationFailedError("Invalid storage path.")
    tenant_folder.mkdir(parents=True, exist_ok=True)
    key_name = f"{uuid.uuid4().hex}.blob"
    target = (tenant_folder / key_name).resolve()
    if tenant_folder not in target.parents:
        raise ValidationFailedError("Invalid storage key.")
    target.write_bytes(raw)
    return f"{tenant_id}/{key_name}"
