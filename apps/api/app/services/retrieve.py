import re
import uuid
from typing import Any

from sqlalchemy import case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Source
from app.services.embeddings import embed_text

_TOKEN = re.compile(r"[A-Za-zÄÖÜäöüß0-9]{4,}")


def query_tokens(query: str) -> set[str]:
    return {token.lower() for token in _TOKEN.findall(query)}


def title_boost(title: str, tokens: set[str]) -> float:
    if not tokens:
        return 0.0
    lower = title.lower()
    if any(token in lower for token in tokens):
        return 0.2
    return 0.0


SEARCH_LIMIT = 8
WIDE_LIMIT = 20
LOW_SCORE = 0.22


def select_diverse_chunks(rows: list[Any], limit: int = 8, per_source: int = 3) -> list[Any]:
    picked: list[Any] = []
    counts: dict[Any, int] = {}
    leftover: list[Any] = []
    for row in rows:
        source_id = row.source_id
        if counts.get(source_id, 0) < per_source:
            picked.append(row)
            counts[source_id] = counts.get(source_id, 0) + 1
        else:
            leftover.append(row)
        if len(picked) >= limit:
            return picked
    for row in leftover:
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


async def hybrid_search(
    session: AsyncSession,
    notebook_id: uuid.UUID,
    tenant_id: str,
    query: str,
    source_ids: list[uuid.UUID] | None,
    limit: int = SEARCH_LIMIT,
    per_source: int = 3,
) -> list[dict[str, Any]]:
    if not source_ids:
        return []
    query_vec = embed_text(query)
    tokens = query_tokens(query)
    dense = case((Chunk.embedding.is_(None), literal(0.0)), else_=(1 - Chunk.embedding.cosine_distance(query_vec)))
    sparse = func.ts_rank(
        func.to_tsvector("german", Chunk.text),
        func.plainto_tsquery("german", query),
    )
    stmt = (
        select(
            Chunk.id,
            Chunk.source_id,
            Chunk.text,
            Chunk.ordinal,
            dense.label("dense"),
            sparse.label("sparse"),
            Source.title,
        )
        .join(Source, Source.id == Chunk.source_id)
        .where(
            Chunk.notebook_id == notebook_id,
            Chunk.tenant_id == tenant_id,
            Chunk.source_id.in_(source_ids),
        )
        .order_by((0.7 * dense + 0.3 * sparse).desc())
        .limit(80)
    )
    rows = list((await session.execute(stmt)).all())
    ranked = sorted(
        rows,
        key=lambda row: (
            0.7 * float(row.dense or 0) + 0.3 * float(row.sparse or 0) + title_boost(row.title or "", tokens)
        ),
        reverse=True,
    )
    top = select_diverse_chunks(ranked, limit=limit, per_source=per_source)
    if not top:
        return []
    return [
        {
            "chunk_id": str(row.id),
            "source_id": str(row.source_id),
            "source_title": row.title or "",
            "text": row.text,
            "ordinal": row.ordinal,
            "score": 0.7 * float(row.dense or 0) + 0.3 * float(row.sparse or 0) + title_boost(row.title or "", tokens),
        }
        for row in top
    ]


def chunk_score(chunk: dict[str, Any]) -> float:
    return float(chunk.get("score") or 0)


def search_is_weak(chunks: list[dict[str, Any]], source_count: int) -> bool:
    if not chunks:
        return True
    if max(chunk_score(chunk) for chunk in chunks) < LOW_SCORE:
        return True
    hit_sources = {str(chunk.get("source_id") or "") for chunk in chunks}
    hit_sources.discard("")
    if source_count > SEARCH_LIMIT and len(hit_sources) < min(source_count, 6):
        return True
    return False


def merge_chunks(*groups: list[dict[str, Any]], limit: int = WIDE_LIMIT) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for group in groups:
        for chunk in group:
            key = str(chunk.get("chunk_id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(chunk)
            if len(out) >= limit:
                return out
    return out


async def notebook_search(
    session: AsyncSession,
    notebook_id: uuid.UUID,
    tenant_id: str,
    query: str,
    source_ids: list[uuid.UUID] | None,
    rewritten: str = "",
    force_wide: bool = False,
) -> list[dict[str, Any]]:
    primary = (rewritten or query).strip() or query
    first = await hybrid_search(session, notebook_id, tenant_id, primary, source_ids, limit=SEARCH_LIMIT)
    source_count = len(source_ids or [])
    if not force_wide and not search_is_weak(first, source_count):
        return first
    wide = await hybrid_search(
        session, notebook_id, tenant_id, primary, source_ids, limit=WIDE_LIMIT, per_source=2
    )
    extra: list[dict[str, Any]] = []
    if primary != query.strip():
        extra = await hybrid_search(
            session, notebook_id, tenant_id, query, source_ids, limit=WIDE_LIMIT, per_source=2
        )
    return merge_chunks(wide, extra, first, limit=WIDE_LIMIT)


def overlap_score(answer: str, chunks: list[dict[str, Any]]) -> float:
    words = {word.lower() for word in answer.split() if len(word) > 4}
    if not words:
        return 1.0
    context = {word.lower() for chunk in chunks for word in chunk["text"].split() if len(word) > 4}
    if not words:
        return 1.0
    return len(words & context) / len(words)
