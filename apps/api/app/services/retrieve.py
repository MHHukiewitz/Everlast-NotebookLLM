import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Source
from app.services.embeddings import embed_text


async def hybrid_search(
    session: AsyncSession,
    notebook_id: uuid.UUID,
    tenant_id: str,
    query: str,
    source_ids: list[uuid.UUID] | None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    if not source_ids:
        return []
    query_vec = embed_text(query)
    stmt = (
        select(
            Chunk.id,
            Chunk.source_id,
            Chunk.text,
            Chunk.ordinal,
            (1 - Chunk.embedding.cosine_distance(query_vec)).label("dense"),
            func.ts_rank(
                func.to_tsvector("german", Chunk.text),
                func.plainto_tsquery("german", query),
            ).label("sparse"),
        )
        .where(
            Chunk.notebook_id == notebook_id,
            Chunk.tenant_id == tenant_id,
            Chunk.source_id.in_(source_ids),
            Chunk.embedding.is_not(None),
        )
        .limit(40)
    )
    rows = (await session.execute(stmt)).all()
    ranked = sorted(
        rows,
        key=lambda row: (0.7 * float(row.dense or 0) + 0.3 * float(row.sparse or 0)),
        reverse=True,
    )
    top = ranked[:limit]
    if not top:
        return []
    source_rows = await session.execute(select(Source.id, Source.title).where(Source.id.in_([row.source_id for row in top])))
    titles = {row.id: row.title for row in source_rows}
    return [
        {
            "chunk_id": str(row.id),
            "source_id": str(row.source_id),
            "source_title": titles.get(row.source_id, ""),
            "text": row.text,
            "ordinal": row.ordinal,
            "score": 0.7 * float(row.dense or 0) + 0.3 * float(row.sparse or 0),
        }
        for row in top
    ]


def overlap_score(answer: str, chunks: list[dict[str, Any]]) -> float:
    words = {word.lower() for word in answer.split() if len(word) > 4}
    if not words:
        return 1.0
    context = {word.lower() for chunk in chunks for word in chunk["text"].split() if len(word) > 4}
    if not words:
        return 1.0
    return len(words & context) / len(words)
