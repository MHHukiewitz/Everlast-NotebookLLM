import re
import socket
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
from app.services.connectors import router
from app.services.ingest import favicon_from_html, favicon_from_url, finalize_source
from app.services.tracing import pack_prompt, record_generation, start_trace

_SKIP = {".pdf", ".jpg", ".png", ".gif", ".zip", ".css", ".js"}


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
                "title": item.get("title") or url,
                "quote": item.get("content") or "",
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
                title=item.get("title") or item["url"],
                quote=item.get("quote") or item.get("text", "")[:280],
                cited_in_report=item["url"] in cited,
            )
        )


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
    job.report_md = "# Schnelle Recherche\n\n" + "\n".join(
        f"- [{item['title']}]({item['url']}) — {item['quote']}" for item in results
    )
    await _add_candidates(session, job, results, set())
    job.status = "ready"
    job.progress = f"{len(results)} Treffer"
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
    notebook = await session.get(Notebook, job.notebook_id)
    context = "\n\n".join(f"Quelle: {page['url']}\n{page['text'][:2500]}" for page in pages)
    messages = [
        {
            "role": "system",
            "content": (
                "Schreibe einen sachlichen Recherchebericht auf Deutsch. "
                "Nutze nur die gelieferten Seiten. Setze Zitate als [n]. "
                "Markiere den Text als KI-generiert."
            ),
        },
        {
            "role": "user",
            "content": f"Frage: {job.query}\n\nMaterial:\n{context}",
        },
    ]
    report = ""
    raw_report = ""
    if notebook and pages:
        completion = await router.complete(notebook.provider, notebook.model_id, messages)
        raw_report = completion.choices[0].message.content or ""
        report = raw_report
    if not report:
        report = "# Deep Research\n\n" + "\n\n".join(
            f"## {page['title']}\n\n{page['text'][:600]}" for page in pages
        )
    cited_urls = {page["url"] for page in pages if page["url"] in report or page["title"] in report}
    if not cited_urls and pages:
        cited_urls = {pages[0]["url"]}
    if notebook:
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
            trace_id=start_trace("research", job.tenant_id, {"job_id": str(job.id)}),
        )
    job.report_md = report
    await _add_candidates(
        session,
        job,
        [{"url": page["url"], "title": page["title"], "text": page["text"]} for page in pages]
        + [item for item in seeds if item["url"] not in {page["url"] for page in pages}],
        cited_urls,
    )
    job.status = "ready"
    job.progress = f"{len(pages)} Seiten"
    await session.commit()


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


async def import_research(
    session: AsyncSession,
    job: ResearchJob,
    citation_ids: list[uuid.UUID],
    import_report: bool,
) -> list[Source]:
    created: list[Source] = []
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
        await finalize_source(session, source, job.report_md, copies)
        created.append(source)
    chosen = (
        await session.execute(
            select(Citation).where(Citation.id.in_(citation_ids), Citation.research_job_id == job.id)
        )
    ).scalars()
    for cite in chosen:
        source = Source(
            tenant_id=job.tenant_id,
            notebook_id=job.notebook_id,
            type="url",
            title=cite.title,
            status="pending",
            origin_uri=cite.url,
            favicon_url=favicon_from_url(cite.url) or None,
            research_mode=job.mode,
        )
        session.add(source)
        await session.flush()
        extracted = trafilatura.fetch_url(cite.url)
        if extracted:
            source.favicon_url = favicon_from_html(extracted, cite.url) or source.favicon_url
        text = (trafilatura.extract(extracted) if extracted else None) or cite.quote or cite.url
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
        )
        created.append(source)
    job.status = "imported"
    await session.commit()
    return created
