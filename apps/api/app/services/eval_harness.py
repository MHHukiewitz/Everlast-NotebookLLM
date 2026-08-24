import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Artifact, EvalItem, EvalRun, Notebook, Source
from app.services.chat_agent import run_chat
from app.services.ingest import extract_html, write_chunks, write_model_summary
from app.services.retrieve import overlap_score
from app.services.skills import run_skill

GOLD_PATH = Path(__file__).resolve().parent.parent / "eval" / "gold.json"
GOLD_SOURCES_PATH = Path(__file__).resolve().parent.parent / "eval" / "gold_sources.json"
GOLD_STUDIO_PATH = Path(__file__).resolve().parent.parent / "eval" / "gold_studio.json"
SOURCE_PATH = Path(__file__).resolve().parent.parent / "eval" / "source.md"
EXTRACT_HTML_PATH = Path(__file__).resolve().parent.parent / "eval" / "extract.html"
EXTRACT_GOLD_PATH = Path(__file__).resolve().parent.parent / "eval" / "extract_gold.md"
EVAL_TITLE = "Eval Gold"
REFUSE_MARKERS = (
    "nicht in den quellen",
    "keine klare antwort",
    "steht nicht",
    "nicht enthalten",
    "enthalten keine",
    "keine informationen",
    "keine solchen",
    "kann keine",
    "kann ich nicht",
    "es tut mir leid",
)


def load_gold() -> list[dict[str, Any]]:
    sources = json.loads(GOLD_SOURCES_PATH.read_text(encoding="utf-8"))
    chat = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    studio = json.loads(GOLD_STUDIO_PATH.read_text(encoding="utf-8"))
    return sources + chat + studio


def keyword_hit_rate(answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    lower = answer.lower()
    hits = sum(1 for word in keywords if word.lower() in lower)
    return hits / len(keywords)


def forbidden_hit(answer: str, forbidden: list[str]) -> bool:
    if not forbidden:
        return False
    lower = answer.lower()
    return any(word.lower() in lower for word in forbidden)


def looks_like_refuse(answer: str) -> bool:
    lower = answer.lower()
    return any(marker in lower for marker in REFUSE_MARKERS)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


async def upsert_eval_source(
    session: AsyncSession,
    notebook: Notebook,
    origin_uri: str,
    title: str,
    text: str,
) -> tuple[Source, int]:
    source = (
        await session.execute(
            select(Source).where(Source.notebook_id == notebook.id, Source.origin_uri == origin_uri)
        )
    ).scalar_one_or_none()
    if source is None:
        source = Source(
            tenant_id=notebook.tenant_id,
            notebook_id=notebook.id,
            type="text",
            title=title,
            status="pending",
            origin_uri=origin_uri,
        )
        session.add(source)
        await session.flush()
    else:
        source.title = title
    source.content_md = text
    summary, latency_ms = await write_model_summary(session, source, text)
    source.summary_md = summary
    source.status = "ready"
    await write_chunks(session, source, text)
    await session.commit()
    await session.refresh(source)
    return source, latency_ms


async def ensure_eval_notebook(
    session: AsyncSession, provider: str, model_id: str
) -> tuple[Notebook, Source, Source, int]:
    result = await session.execute(
        select(Notebook).where(
            Notebook.tenant_id == settings.default_tenant_id,
            Notebook.title == EVAL_TITLE,
        )
    )
    notebook = result.scalar_one_or_none()
    if notebook is None:
        notebook = Notebook(
            tenant_id=settings.default_tenant_id,
            title=EVAL_TITLE,
            provider=provider,
            model_id=model_id,
        )
        session.add(notebook)
        await session.flush()
    else:
        notebook.provider = provider
        notebook.model_id = model_id
    gold_source, summary_latency_ms = await upsert_eval_source(
        session,
        notebook,
        "eval://gold",
        "Eval-Quelle Wissensdatenbank",
        SOURCE_PATH.read_text(encoding="utf-8"),
    )
    html = EXTRACT_HTML_PATH.read_text(encoding="utf-8")
    extract_title, extract_text = extract_html(html, fallback_title="Eval-HTML Nordhafen")
    extract_source, _extract_summary_ms = await upsert_eval_source(
        session,
        notebook,
        "eval://extract",
        extract_title,
        extract_text,
    )
    gold_source.selected = True
    extract_source.selected = False
    await session.commit()
    await session.refresh(notebook)
    return notebook, gold_source, extract_source, summary_latency_ms


def flatten_studio_payload(payload: dict[str, Any], artifact_type: str) -> str:
    title = str(payload.get("title") or "")
    if artifact_type == "mindmap":
        return f"{title}\n{payload.get('mermaid') or ''}"
    if artifact_type == "report":
        return f"{title}\n{payload.get('body_md') or ''}"
    if artifact_type == "quiz":
        parts = [title]
        for question in payload.get("questions") or []:
            parts.append(str(question.get("question") or ""))
            parts.extend(str(choice) for choice in question.get("choices") or [])
            parts.append(str(question.get("explanation") or ""))
        return "\n".join(parts)
    if artifact_type == "flashcards":
        parts = [title]
        for card in payload.get("cards") or []:
            parts.append(str(card.get("front") or ""))
            parts.append(str(card.get("back") or ""))
            parts.append(str(card.get("cite") or ""))
        return "\n".join(parts)
    if artifact_type == "table":
        parts = [title]
        parts.extend(str(column) for column in payload.get("columns") or [])
        for row in payload.get("rows") or []:
            parts.extend(str(cell) for cell in row)
        return "\n".join(parts)
    if artifact_type == "note":
        return f"{title}\n{payload.get('body') or ''}"
    return json.dumps(payload, ensure_ascii=False)


async def collect_studio(
    session: AsyncSession, notebook: Notebook, skill_id: str, args: dict[str, Any]
) -> dict[str, Any]:
    started = time.perf_counter()
    result = await run_skill(session, notebook, skill_id, args)
    artifact = await session.get(Artifact, uuid.UUID(result["artifact_id"]))
    if artifact is None:
        raise ValueError("Studio-Artefakt nicht gespeichert")
    latency_ms = int((time.perf_counter() - started) * 1000)
    payload = artifact.payload or {}
    return {
        "answer": flatten_studio_payload(payload, artifact.type),
        "payload": payload,
        "type": artifact.type,
        "citations": payload.get("citations") or [],
        "latency_ms": latency_ms,
    }


def score_studio_output(
    case: dict[str, Any],
    output: str,
    payload: dict[str, Any],
    reference: str,
    latency_ms: int,
    citations: list[Any],
) -> dict[str, Any]:
    scored = score_source_output(case, output, reference, latency_ms)
    scored["citations"] = citations
    min_questions = int(case.get("min_questions") or 0)
    if min_questions:
        count = len(payload.get("questions") or [])
        if count < min_questions:
            scored["hit"] = scored["hit"] * 0.5
    min_cards = int(case.get("min_cards") or 0)
    if min_cards:
        count = len(payload.get("cards") or [])
        if count < min_cards:
            scored["hit"] = scored["hit"] * 0.5
    return scored


async def collect_answer(session: AsyncSession, notebook: Notebook, question: str) -> dict[str, Any]:
    started = time.perf_counter()
    answer = ""
    done: dict[str, Any] = {}
    async for event in run_chat(session, notebook, question, tools_enabled=False, use_history=False):
        if event.get("event") == "token":
            answer += str(event.get("text") or "")
        if event.get("event") == "done":
            done = event
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "answer": answer,
        "citations": done.get("citations") or [],
        "retrieved": done.get("retrieved") or [],
        "overlap": float(done.get("overlap") or 0.0),
        "latency_ms": latency_ms,
    }


def score_source_output(
    case: dict[str, Any],
    output: str,
    reference: str,
    latency_ms: int,
) -> dict[str, Any]:
    keywords = list(case.get("keywords") or [])
    forbidden = list(case.get("forbidden") or [])
    hit = keyword_hit_rate(output, keywords)
    dirty = forbidden_hit(output, forbidden)
    if dirty:
        hit = hit * 0.5
    overlap = overlap_score(output, [{"text": reference}])
    return {
        "answer": output,
        "citations": [],
        "retrieved": [{"source_title": case["id"], "text": reference[:400]}],
        "overlap": overlap,
        "latency_ms": latency_ms,
        "keywords": keywords,
        "hit": hit,
        "must_refuse": False,
        "refuse_ok": not dirty,
    }


async def run_eval(session: AsyncSession, provider: str, model_id: str) -> EvalRun:
    notebook, gold_source, extract_source, summary_latency_ms = await ensure_eval_notebook(
        session, provider, model_id
    )
    run = EvalRun(
        tenant_id=settings.default_tenant_id,
        notebook_id=notebook.id,
        provider=provider,
        model_id=model_id,
        status="running",
        metrics={},
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    cases = load_gold()
    latencies: list[int] = []
    overlaps: list[float] = []
    keyword_rates: list[float] = []
    chat_hits: list[float] = []
    source_hits: list[float] = []
    source_overlaps: list[float] = []
    studio_hits: list[float] = []
    studio_overlaps: list[float] = []
    refuse_hits = 0
    refuse_total = 0
    extract_gold = EXTRACT_GOLD_PATH.read_text(encoding="utf-8")
    gold_text = gold_source.content_md or ""
    for case in cases:
        task = str(case.get("task") or "chat")
        if task == "source_extract":
            scored = score_source_output(case, extract_source.content_md or "", extract_gold, 0)
        elif task == "source_summary":
            scored = score_source_output(
                case, gold_source.summary_md or "", gold_text, summary_latency_ms
            )
        elif task.startswith("studio_"):
            studio = await collect_studio(
                session, notebook, str(case["skill_id"]), {"topic": case.get("topic") or ""}
            )
            scored = score_studio_output(
                case,
                studio["answer"],
                studio["payload"],
                gold_text,
                studio["latency_ms"],
                studio["citations"],
            )
        else:
            result = await collect_answer(session, notebook, case["question"])
            keywords = list(case.get("keywords") or [])
            must_refuse = bool(case.get("must_refuse"))
            hit = keyword_hit_rate(result["answer"], keywords)
            refused = looks_like_refuse(result["answer"])
            refuse_ok = refused if must_refuse else not refused
            if must_refuse:
                refuse_total += 1
                if refused:
                    refuse_hits += 1
                hit = 1.0 if refused else 0.0
            scored = {
                "answer": result["answer"],
                "citations": result["citations"],
                "retrieved": result["retrieved"],
                "overlap": result["overlap"],
                "latency_ms": result["latency_ms"],
                "keywords": keywords,
                "hit": hit,
                "must_refuse": must_refuse,
                "refuse_ok": refuse_ok,
            }
        item = EvalItem(
            tenant_id=settings.default_tenant_id,
            run_id=run.id,
            case_id=case["id"],
            task=task,
            question=case["question"],
            expected_answer=case.get("expected_answer") or "",
            expected_keywords=scored["keywords"],
            must_refuse=scored["must_refuse"],
            answer=scored["answer"],
            citations=scored["citations"],
            retrieved=scored["retrieved"],
            latency_ms=scored["latency_ms"],
            overlap_score=scored["overlap"],
            keyword_hit_rate=scored["hit"],
            refuse_ok=scored["refuse_ok"],
        )
        session.add(item)
        latencies.append(scored["latency_ms"])
        overlaps.append(scored["overlap"])
        keyword_rates.append(scored["hit"])
        if task == "chat":
            chat_hits.append(scored["hit"])
        elif task.startswith("studio_"):
            studio_hits.append(scored["hit"])
            studio_overlaps.append(scored["overlap"])
        else:
            source_hits.append(scored["hit"])
            source_overlaps.append(scored["overlap"])
        await session.commit()
    run.status = "ready"
    run.finished_at = datetime.now(timezone.utc)
    run.metrics = {
        "n": len(cases),
        "n_chat": len(chat_hits),
        "n_source": len(source_hits),
        "n_studio": len(studio_hits),
        "avg_latency_ms": round(mean(latencies), 1),
        "avg_overlap": round(mean(overlaps), 3),
        "avg_keyword_hit": round(mean(keyword_rates), 3),
        "chat_avg_keyword_hit": round(mean(chat_hits), 3),
        "source_avg_keyword_hit": round(mean(source_hits), 3),
        "source_avg_overlap": round(mean(source_overlaps), 3),
        "studio_avg_keyword_hit": round(mean(studio_hits), 3),
        "studio_avg_overlap": round(mean(studio_overlaps), 3),
        "refuse_accuracy": round(refuse_hits / refuse_total, 3) if refuse_total else 1.0,
        "human_reviewed": 0,
    }
    await session.commit()
    await session.refresh(run)
    return run
