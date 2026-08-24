import asyncio
import re
import socket
import time
import uuid
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal
from app.models import Citation, Notebook, ResearchJob, Source
from app.services.autoname import maybe_autoname
from app.services.connectors import router
from app.services.ingest import (
    embed_source_isolated,
    favicon_from_html,
    favicon_from_url,
    finalize_source,
    ground_summary,
    refresh_model_summary,
    unwrap_markdown_fence,
)
from app.services.net import host_open
from app.services.tracing import pack_prompt, record_generation, start_trace

_SKIP = {".pdf", ".jpg", ".png", ".gif", ".zip", ".css", ".js"}
_FETCH_CAP = 4
_QUOTE_LIMIT = 2000


def _plain(text: str) -> str:
    return "".join(ch if ch in "\n\t" or ord(ch) >= 32 else " " for ch in text)


def _host_open(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    sock = socket.socket()
    sock.settimeout(1.0)
    code = sock.connect_ex((host, port))
    sock.close()
    return code == 0


def searx_reachable() -> bool:
    return _host_open(settings.searxng_url)


def searx_search(query: str, count: int = 8) -> list[dict[str, str]]:
    if not searx_reachable():
        raise ValueError("SearXNG ist nicht erreichbar. Starte den SearXNG-Container.")
    response = httpx.get(
        f"{settings.searxng_url.rstrip('/')}/search",
        params={"q": query, "format": "json", "language": "de-DE"},
        timeout=20.0,
    )
    response.raise_for_status()
    items = response.json().get("results", [])
    out: list[dict[str, str]] = []
    for item in items[:count]:
        url = item.get("url") or ""
        if not url:
            continue
        out.append(
            {
                "url": url,
                "title": _plain(item.get("title") or url),
                "quote": _plain(item.get("content") or ""),
            }
        )
    return out


def _same_site(base: str, url: str) -> bool:
    return urlparse(base).netloc == urlparse(url).netloc


def _extract_links(html: str, base: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = urljoin(base, tag["href"])
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        if any(parsed.path.lower().endswith(ext) for ext in _SKIP):
            continue
        links.append(href.split("#")[0])
    return links


def browse_pages(start_urls: list[str], max_pages: int = 8, max_depth: int = 2) -> list[dict[str, str]]:
    seen: set[str] = set()
    queue: list[tuple[str, int]] = [(url, 0) for url in start_urls]
    pages: list[dict[str, str]] = []
    headers = {"User-Agent": "EverlastNotebook/1.0"}
    with httpx.Client(timeout=12.0, follow_redirects=True, headers=headers) as client:
        while queue and len(pages) < max_pages:
            url, depth = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            response = client.get(url)
            if response.status_code != 200:
                continue
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                continue
            text = trafilatura.extract(response.text, include_comments=False) or ""
            if len(text.strip()) < 80:
                continue
            title_match = re.search(r"<title>(.*?)</title>", response.text, re.I | re.S)
            title = re.sub("<.*?>", "", title_match.group(1)).strip() if title_match else url
            pages.append({"url": url, "title": title, "text": text[:12000]})
            if depth < max_depth:
                for link in _extract_links(response.text, url):
                    if _same_site(url, link) and link not in seen:
                        queue.append((link, depth + 1))
    return pages


async def _add_candidates(
    session: AsyncSession, job: ResearchJob, items: list[dict[str, str]], cited: set[str]
) -> None:
    for item in items:
        session.add(
            Citation(
                tenant_id=job.tenant_id,
                research_job_id=job.id,
                url=item["url"],
                title=_plain(item.get("title") or item["url"]),
                quote=_plain((item.get("quote") or item.get("text", ""))[:_QUOTE_LIMIT]),
                cited_in_report=item["url"] in cited,
            )
        )


def fallback_report(mode: str, items: list[dict[str, str]]) -> str:
    if mode == "deep":
        if not items:
            return "# Deep Research\n"
        return _plain(
            "# Deep Research\n\n"
            + "\n\n".join(
                f"## {item.get('title') or item.get('url')}\n\n{(item.get('quote') or item.get('text') or '')[:600]}"
                for item in items
            )
        )
    return _plain(
        "# Schnelle Recherche\n\n"
        + "\n".join(
            f"- [{item.get('title') or item.get('url')}]({item.get('url')}) — {item.get('quote') or ''}"
            for item in items
        )
    )


def _citation_items(cites: list[Citation]) -> list[dict[str, str]]:
    return [{"url": cite.url, "title": cite.title, "quote": cite.quote} for cite in cites]


def _provider_ready(notebook: Notebook | None) -> bool:
    if notebook is None:
        return False
    if notebook.provider == "ollama" and not host_open(settings.ollama_api_base):
        return False
    if notebook.provider == "openrouter" and not settings.openrouter_api_key:
        return False
    if notebook.provider == "eu" and not (settings.eu_llm_base_url and settings.eu_llm_api_key):
        return False
    return True


async def write_research_report(session: AsyncSession, job: ResearchJob) -> None:
    cites = list(
        (await session.execute(select(Citation).where(Citation.research_job_id == job.id))).scalars()
    )
    items = _citation_items(cites)
    fallback = fallback_report(job.mode, items)
    notebook = await session.get(Notebook, job.notebook_id)
    if not items or not _provider_ready(notebook):
        job.report_md = fallback
        await session.commit()
        return
    assert notebook is not None
    context = "\n\n".join(
        f"[{index}] {item['title']}\n{item['url']}\n{item['quote']}" for index, item in enumerate(items, start=1)
    )
    messages = [
        {
            "role": "system",
            "content": (
                "Du bist Everlast Notebook, ein KI-System. "
                "Schreibe eine kurze sachliche Zusammenfassung auf Deutsch als Markdown. "
                "Thema ist die Suchanfrage. "
                "Nutze nur die gelieferten Treffer. Setze Zitate als [n]. "
                "Erfinde keine Fakten, Zahlen, Namen, Jahre oder URLs. "
                "Schliesse mit der Zeile: Dieser Bericht ist KI-generiert."
            ),
        },
        {
            "role": "user",
            "content": f"Frage: {job.query}\n\nTreffer:\n{context}",
        },
    ]
    started = time.perf_counter()
    completion = await router.complete(notebook.provider, notebook.model_id, messages)
    latency_ms = int((time.perf_counter() - started) * 1000)
    raw_report = completion.choices[0].message.content or ""
    material = "\n".join(f"{item['title']}\n{item['url']}\n{item['quote']}" for item in items)
    report = ground_summary(raw_report.strip(), material) if raw_report.strip() else fallback
    await record_generation(
        session,
        tenant_id=job.tenant_id,
        notebook_id=job.notebook_id,
        kind="research",
        model=f"{notebook.provider}/{notebook.model_id}",
        prompt=pack_prompt(messages),
        raw_output=raw_report,
        visible_output=report,
        extra={"job_id": str(job.id), "query": job.query, "mode": job.mode},
        latency_ms=latency_ms,
        trace_id=start_trace("research", job.tenant_id, {"job_id": str(job.id)}),
    )
    job.report_md = _plain(unwrap_markdown_fence(report))
    await session.commit()


async def write_research_report_isolated(job_id: uuid.UUID) -> None:
    async with SessionLocal() as session:
        job = await session.get(ResearchJob, job_id)
        if job is None:
            return
        await write_research_report(session, job)


def queue_research_report(job_id: uuid.UUID) -> None:
    asyncio.create_task(write_research_report_isolated(job_id))


def queue_source_followup(source_id: uuid.UUID) -> None:
    asyncio.create_task(embed_source_isolated(source_id))
    asyncio.create_task(refresh_model_summary(source_id))


async def run_fast_research(session: AsyncSession, job: ResearchJob) -> None:
    if not searx_reachable():
        job.status = "error"
        job.progress = "SearXNG ist nicht erreichbar. Starte den SearXNG-Container."
        await session.commit()
        return
    job.status = "running"
    job.progress = "Suche läuft"
    await session.commit()
    results = searx_search(job.query)
    await _add_candidates(session, job, results, {item["url"] for item in results})
    job.status = "ready"
    job.progress = f"{len(results)} Treffer"
    if results:
        job.report_md = ""
        await session.commit()
        queue_research_report(job.id)
        return
    job.report_md = fallback_report("fast", results)
    await session.commit()


async def run_deep_research(session: AsyncSession, job: ResearchJob) -> None:
    if not searx_reachable():
        job.status = "error"
        job.progress = "SearXNG ist nicht erreichbar. Starte den SearXNG-Container."
        await session.commit()
        return
    job.status = "running"
    job.progress = "Suche und Browse"
    await session.commit()
    seeds = searx_search(job.query, count=5)
    pages = browse_pages([item["url"] for item in seeds], max_pages=8, max_depth=2)
    page_urls = {page["url"] for page in pages}
    items = [{"url": page["url"], "title": page["title"], "text": page["text"]} for page in pages] + [
        item for item in seeds if item["url"] not in page_urls
    ]
    await _add_candidates(session, job, items, page_urls or {seeds[0]["url"]} if seeds else set())
    job.status = "ready"
    job.progress = f"{len(pages)} Seiten"
    if items:
        job.report_md = ""
        await session.commit()
        queue_research_report(job.id)
        return
    job.report_md = fallback_report("deep", items)
    await session.commit()


async def enqueue_research(
    session: AsyncSession, notebook: Notebook, query: str, mode: str
) -> ResearchJob:
    job = ResearchJob(
        tenant_id=notebook.tenant_id,
        notebook_id=notebook.id,
        query=query.strip(),
        mode=mode,
        status="queued",
        progress="Suche läuft",
    )
    maybe_autoname(notebook, job.query)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def run_research_job(session: AsyncSession, job_id: uuid.UUID) -> None:
    job = await session.get(ResearchJob, job_id)
    if job is None:
        return
    if job.mode == "deep":
        await run_deep_research(session, job)
        return
    await run_fast_research(session, job)


async def run_research_job_isolated(job_id: uuid.UUID) -> None:
    async with SessionLocal() as session:
        await run_research_job(session, job_id)


async def import_research_isolated(
    job_id: uuid.UUID, citation_ids: list[uuid.UUID], import_report: bool
) -> None:
    async with SessionLocal() as session:
        job = await session.get(ResearchJob, job_id)
        if job is None:
            return
        await import_research(session, job, citation_ids, import_report)


def _fetch_citation_page(url: str, fallback: str) -> tuple[str, str | None]:
    extracted = trafilatura.fetch_url(url)
    icon = favicon_from_html(extracted, url) if extracted else None
    text = (trafilatura.extract(extracted) if extracted else None) or fallback
    return text, icon


async def _fetch_citation(cite: Citation) -> tuple[Citation, str, str | None]:
    text, icon = await asyncio.to_thread(_fetch_citation_page, cite.url, cite.quote or cite.url)
    return cite, text, icon


async def import_research(
    session: AsyncSession,
    job: ResearchJob,
    citation_ids: list[uuid.UUID],
    import_report: bool,
) -> list[Source]:
    created: list[Source] = []
    chosen: list[Citation] = []
    if citation_ids:
        chosen = list(
            (
                await session.execute(
                    select(Citation).where(Citation.id.in_(citation_ids), Citation.research_job_id == job.id)
                )
            ).scalars()
        )
    total = len(chosen) + (1 if import_report and job.report_md else 0)
    done = 0
    job.status = "importing"
    job.progress = "Import läuft"
    await session.commit()
    followup_ids: list[uuid.UUID] = []
    if import_report and job.report_md:
        report_cites = list(
            (
                await session.execute(
                    select(Citation).where(
                        Citation.research_job_id == job.id,
                        Citation.cited_in_report.is_(True),
                    )
                )
            ).scalars()
        )
        first_url = next((cite.url for cite in report_cites if cite.url), "")
        source = Source(
            tenant_id=job.tenant_id,
            notebook_id=job.notebook_id,
            type="research_report",
            title=f"Bericht: {job.query}",
            status="pending",
            origin_uri=first_url or None,
            favicon_url=favicon_from_url(first_url) or None,
            research_mode=job.mode,
        )
        session.add(source)
        await session.flush()
        copies = [
            Citation(
                tenant_id=job.tenant_id,
                source_id=source.id,
                url=cite.url,
                title=cite.title,
                quote=cite.quote,
                cited_in_report=True,
            )
            for cite in report_cites
        ]
        await finalize_source(
            session,
            source,
            job.report_md,
            copies,
            use_model_summary=False,
            embed=False,
        )
        created.append(source)
        followup_ids.append(source.id)
        done += 1
        job.progress = f"Import {done}/{total}"
        await session.commit()
    fetched: list[tuple[Citation, str, str | None]] = []
    if chosen:
        sem = asyncio.Semaphore(_FETCH_CAP)

        async def _bounded(cite: Citation) -> tuple[Citation, str, str | None]:
            async with sem:
                return await _fetch_citation(cite)

        fetched = await asyncio.gather(*[_bounded(cite) for cite in chosen])
    for cite, text, icon in fetched:
        source = Source(
            tenant_id=job.tenant_id,
            notebook_id=job.notebook_id,
            type="url",
            title=cite.title,
            status="pending",
            origin_uri=cite.url,
            favicon_url=icon or favicon_from_url(cite.url) or None,
            research_mode=job.mode,
        )
        session.add(source)
        await session.flush()
        await finalize_source(
            session,
            source,
            text,
            [
                Citation(
                    tenant_id=job.tenant_id,
                    source_id=source.id,
                    url=cite.url,
                    title=cite.title,
                    quote=cite.quote,
                    cited_in_report=True,
                )
            ],
            use_model_summary=False,
            embed=False,
        )
        created.append(source)
        followup_ids.append(source.id)
        done += 1
        job.progress = f"Import {done}/{total}"
        await session.commit()
    job.status = "imported"
    notebook = await session.get(Notebook, job.notebook_id)
    if notebook is not None:
        maybe_autoname(notebook, job.query)
    await session.commit()
    for source_id in followup_ids:
        queue_source_followup(source_id)
    return created
