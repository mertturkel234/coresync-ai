"""Tenant- and project-scoped documentation retrieval.

All candidate chunks are loaded with an authoritative SQL filter on (tenant_id, project_id), so
another tenant's documents can never enter the retrieval set.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.models import DocChunk
from app.repositories import documents as docs_repo

_TOKEN_RE = re.compile(r"[A-Za-z0-9_/{}-]{2,}")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "how",
        "what",
        "can",
        "you",
        "use",
        "using",
        "from",
        "that",
        "this",
        "into",
        "does",
        "show",
        "example",
        "python",
        "code",
        "api",
        "endpoint",
        "request",
        "call",
    }
)

MIN_SCORE_THRESHOLD = 0.85


class Embedder(Protocol):
    """Extension point for pgvector semantic search when an embedding provider is configured."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class ScoredChunk:
    chunk: DocChunk
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[ScoredChunk]
    sufficient: bool


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(text.lower()):
        cleaned = raw.strip("{}/_-")
        if (len(cleaned) >= 3 or cleaned in {"get", "put"}) and cleaned not in _STOPWORDS:
            tokens.append(cleaned)
            # Split camelCase / snake_case identifiers so "createOrder" matches "create" + "order".
            parts = re.findall(r"[a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1_\2", raw).lower())
            for p in parts:
                if len(p) >= 3 and p not in _STOPWORDS and p != cleaned:
                    tokens.append(p)
                if p.endswith("s") and len(p) > 3:
                    tokens.append(p[:-1])
        if cleaned.endswith("s") and len(cleaned) > 3:
            tokens.append(cleaned[:-1])
    return tokens


def retrieve_chunks(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    query: str,
    top_k: int = 5,
    preferred_endpoint_id: uuid.UUID | None = None,
) -> RetrievalResult:
    candidates = docs_repo.list_chunks(db, tenant_id=tenant_id, project_id=project_id)
    if not candidates:
        return RetrievalResult(chunks=[], sufficient=False)

    q_tokens = tokenize(query)
    if not q_tokens and preferred_endpoint_id is None:
        return RetrievalResult(chunks=[], sufficient=False)

    q_lower = query.lower()
    doc_tokens = [tokenize(f"{c.ref} {c.title} {c.content}") for c in candidates]
    n_docs = len(candidates)
    avg_dl = sum(len(t) for t in doc_tokens) / max(n_docs, 1)

    df: Counter[str] = Counter()
    for toks in doc_tokens:
        for term in set(toks):
            df[term] += 1

    scored: list[ScoredChunk] = []
    k1 = 1.5
    b = 0.75

    for chunk, toks in zip(candidates, doc_tokens, strict=True):
        tf = Counter(toks)
        dl = max(len(toks), 1)
        score = 0.0
        for term in set(q_tokens):
            if tf[term] == 0:
                continue
            idf = math.log(1.0 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            denom = tf[term] + k1 * (1.0 - b + b * (dl / max(avg_dl, 1.0)))
            score += idf * ((tf[term] * (k1 + 1.0)) / denom)

        # Boost exact HTTP method or path mentions in the query.
        ref_lower = chunk.ref.lower()
        for method in ("get", "post", "put", "patch", "delete"):
            if re.search(rf"\b{method}\b", q_lower) and ref_lower.startswith(f"{method} "):
                score += 0.6
        if chunk.kind == "endpoint":
            parts = chunk.ref.split(" ", 1)
            if len(parts) == 2 and parts[1].lower() in q_lower:
                score += 2.0
        if preferred_endpoint_id is not None and chunk.endpoint_id == preferred_endpoint_id:
            score += 5.0

        if score > 0:
            scored.append(ScoredChunk(chunk=chunk, score=round(score, 4)))

    scored.sort(key=lambda s: s.score, reverse=True)
    top = scored[:top_k]
    sufficient = bool(top and top[0].score >= MIN_SCORE_THRESHOLD)
    return RetrievalResult(chunks=top, sufficient=sufficient)
