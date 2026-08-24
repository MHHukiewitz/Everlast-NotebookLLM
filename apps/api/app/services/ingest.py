import io
import re
import time
import uuid
from pathlib import Path

import httpx
import trafilatura
from docx import Document
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Chunk, Citation, Notebook, Source
from app.services.connectors import router
from app.services.embeddings import embed_texts
from app.services.net import host_open

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_CITED_QUOTE = re.compile(r"\[(\d+)\]\s*[\"«„“](.+?)[\"»“”]", re.DOTALL)
_BARE_URL = re.compile(r"https?://[^\s)>\]]+")


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def ground_summary(summary: str, source: str) -> str:
    compact_source = _compact(source)

    def keep_quote(match: re.Match[str]) -> str:
        quote = _compact(match.group(2)).strip()
        if quote and (quote in source or quote in compact_source):
            return match.group(0)
        return f"[{match.group(1)}]"

    text = _CITED_QUOTE.sub(keep_quote, summary)
    source_urls = set(_BARE_URL.findall(source))

    def keep_url(match: re.Match[str]) -> str:
        url = match.group(0).rstrip(".,;)")
        if url in source_urls:
            return match.group(0)
        return ""

    text = _BARE_URL.sub(keep_url, text)

    def keep_year(match: re.Match[str]) -> str:
        if match.group(1) in source:
            return match.group(0)
        return ""

    text = re.sub(r"\((\d{4})\)", keep_year, text)
    text = re.sub(r"(?im)^quelle:\s*$", "", text)
    text = re.sub(r"\[\d+\]\s*$", "", text, flags=re.M)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _chunk_text(text: str, size: int = 900, overlap: int = 120) -> list[tuple[int, int, str]]:
    clean = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not clean:
        return []
    parts: list[tuple[int, int, str]] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + size)
        if end < len(clean):
            window = clean[start:end]
            split_at = window.rfind("\n")
            if split_at < size * 0.5:
                split_at = window.rfind(" ")
            if split_at > size * 0.4:
                end = start + split_at
        piece = clean[start:end].strip()
        if piece:
            parts.append((start, end, piece))
        if end >= len(clean):
            break
        start = max(end - overlap, start + 1)
    return parts


def parse_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def parse_docx(data: bytes) -> str:
    document = Document(io.BytesIO(data))
    return "\n\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text)


def parse_upload(filename: str, data: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return parse_pdf(data)
    if lower.endswith(".docx"):
        return parse_docx(data)
    return data.decode("utf-8", errors="replace")


def fetch_url_text(url: str) -> tuple[str, str]:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"Seite nicht erreichbar: {url}")
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=True) or ""
    if not text.strip():
        raise ValueError(f"Kein Text auf der Seite: {url}")
    metadata = trafilatura.extract_metadata(downloaded)
    title = metadata.title if metadata and metadata.title else url
    return title, text


def extract_html(html: str, fallback_title: str = "HTML") -> tuple[str, str]:
    text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    if not text.strip():
        raise ValueError("Kein Text im HTML")
    metadata = trafilatura.extract_metadata(html)
    title = metadata.title if metadata and metadata.title else fallback_title
    return title, text


def store_file(notebook_id: uuid.UUID, filename: str, data: bytes) -> str:
    folder = Path(settings.file_store) / str(notebook_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    target.write_bytes(data)
    return str(target)


async def rebuild_embeddings(session: AsyncSession) -> int:
    rows = list((await session.execute(select(Chunk))).scalars())
    if not rows:
        return 0
    vectors = embed_texts([row.text for row in rows])
    for row, vector in zip(rows, vectors, strict=True):
        row.embedding = vector
    await session.commit()
    return len(rows)


async def write_chunks(session: AsyncSession, source: Source, text: str) -> None:
    await session.execute(delete(Chunk).where(Chunk.source_id == source.id))
    pieces = _chunk_text(text)
    if not pieces:
        return
    vectors = embed_texts([piece[2] for piece in pieces])
    for index, ((start, end, piece), vector) in enumerate(zip(pieces, vectors, strict=True)):
        session.add(
            Chunk(
                tenant_id=source.tenant_id,
                notebook_id=source.notebook_id,
                source_id=source.id,
                ordinal=index,
                text=piece,
                start_offset=start,
                end_offset=end,
                token_count=len(piece.split()),
                embedding=vector,
            )
        )


def build_source_report(title: str, text: str, origin: str | None) -> str:
    preview = text.strip().split("\n")
    lead = " ".join(preview[:8])[:800]
    origin_line = f"\n\nQuelle: {origin}" if origin else ""
    return f"# {title}\n\n{lead}{origin_line}\n"


async def write_model_summary(session: AsyncSession, source: Source, text: str) -> tuple[str, int]:
    notebook = await session.get(Notebook, source.notebook_id)
    fallback = build_source_report(source.title, text, source.origin_uri)
    if notebook is None:
        return fallback, 0
    if notebook.provider == "ollama" and not host_open(settings.ollama_api_base):
        return fallback, 0
    if notebook.provider == "openrouter" and not settings.openrouter_api_key:
        return fallback, 0
    if notebook.provider == "eu" and not (settings.eu_llm_base_url and settings.eu_llm_api_key):
        return fallback, 0
    excerpt = text[:8000]
    messages = [
        {
            "role": "system",
            "content": (
                "Du bist Everlast Notebook, ein KI-System. "
                "Schreibe einen Quellenbericht auf Deutsch als Markdown. "
                "Nutze nur den gelieferten Quelltext. "
                "Ein Zitat [1] darf nur ein wörtliches Teilstück des Quelltexts sein. "
                "Setze keine Anführungszeichen um Sätze, die nicht wörtlich in der Quelle stehen. "
                "Erfinde keine Fakten, Zahlen, Namen, Jahre oder URLs. "
                "Schliesse mit der Zeile: Dieser Bericht ist KI-generiert."
            ),
        },
        {
            "role": "user",
            "content": f"Titel: {source.title}\n\nQuelltext:\n{excerpt}",
        },
    ]
    started = time.perf_counter()
    completion = await router.complete(notebook.provider, notebook.model_id, messages)
    latency_ms = int((time.perf_counter() - started) * 1000)
    body = completion.choices[0].message.content or ""
    if not body.strip():
        return fallback, latency_ms
    return ground_summary(body.strip(), text), latency_ms


async def finalize_source(
    session: AsyncSession,
    source: Source,
    text: str,
    citations: list[Citation] | None = None,
) -> Source:
    source.content_md = text
    summary, _latency = await write_model_summary(session, source, text)
    source.summary_md = summary
    source.status = "ready"
    await write_chunks(session, source, text)
    if citations:
        for citation in citations:
            session.add(citation)
    elif source.origin_uri:
        session.add(
            Citation(
                tenant_id=source.tenant_id,
                source_id=source.id,
                url=source.origin_uri,
                title=source.title,
                quote=text[:280],
                cited_in_report=True,
            )
        )
    await session.commit()
    await session.refresh(source)
    return source


async def ingest_url(session: AsyncSession, source: Source, url: str) -> Source:
    title, text = fetch_url_text(url)
    if not source.title or source.title == url:
        source.title = title
    source.origin_uri = url
    return await finalize_source(session, source, text)


async def ingest_text(session: AsyncSession, source: Source, text: str) -> Source:
    return await finalize_source(session, source, text)


async def get_source(session: AsyncSession, source_id: uuid.UUID, tenant_id: str) -> Source | None:
    result = await session.execute(
        select(Source).where(Source.id == source_id, Source.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


def http_get(url: str, timeout: float = 12.0) -> httpx.Response:
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "EverlastNotebook/1.0"}) as client:
        return client.get(url)
