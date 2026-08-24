import json
import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import GenerationLog

_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_LANGFUSE = None
if settings.langfuse_public_key and settings.langfuse_secret_key and settings.langfuse_host:
    from langfuse import Langfuse

    _LANGFUSE = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def mask_text(value: str) -> str:
    return _EMAIL.sub("[email]", value)


def pack_prompt(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in messages:
        content = item.get("content")
        if content is None:
            content = json.dumps(
                {"tool_calls": item.get("tool_calls"), "name": item.get("name")},
                default=str,
                ensure_ascii=False,
            )
        parts.append(f"{item.get('role')}: {content}")
    return "\n\n".join(parts)


def start_trace(name: str, user_id: str, metadata: dict[str, Any] | None = None) -> str:
    local_id = str(uuid.uuid4())
    if _LANGFUSE is None:
        return local_id
    trace = _LANGFUSE.trace(name=name, user_id=user_id, metadata=metadata or {})
    return trace.id


def score_trace(trace_id: str, name: str, value: float) -> None:
    if _LANGFUSE is None:
        return
    _LANGFUSE.score(trace_id=trace_id, name=name, value=value)


def delete_user_traces(user_id: str) -> None:
    if _LANGFUSE is None:
        return
    if hasattr(_LANGFUSE, "delete_traces"):
        _LANGFUSE.delete_traces(user_id=user_id)


def log_generation(
    trace_id: str | None,
    model: str,
    prompt: str,
    completion: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if _LANGFUSE is None or not trace_id:
        return
    _LANGFUSE.generation(
        trace_id=trace_id,
        name="llm",
        model=model,
        input=mask_text(prompt),
        output=mask_text(completion),
        metadata=metadata or {},
    )


async def record_generation(
    session: AsyncSession,
    *,
    tenant_id: str,
    notebook_id: uuid.UUID,
    kind: str,
    model: str,
    prompt: str,
    raw_output: str,
    visible_output: str = "",
    reasoning: list[Any] | None = None,
    tool_calls: list[Any] | None = None,
    extra: dict[str, Any] | None = None,
    message_id: uuid.UUID | None = None,
    latency_ms: int = 0,
    trace_id: str | None = None,
) -> GenerationLog:
    steps = list(reasoning or [])
    calls = list(tool_calls or [])
    meta = dict(extra or {})
    row = GenerationLog(
        tenant_id=tenant_id,
        notebook_id=notebook_id,
        message_id=message_id,
        kind=kind,
        model=model,
        prompt=prompt,
        raw_output=raw_output,
        visible_output=visible_output,
        reasoning=steps,
        tool_calls=calls,
        extra=meta,
        latency_ms=latency_ms,
    )
    session.add(row)
    log_generation(
        trace_id,
        model,
        prompt,
        raw_output or visible_output,
        {
            **meta,
            "kind": kind,
            "visible_output": mask_text(visible_output),
            "reasoning": steps,
            "tool_calls": calls,
        },
    )
    return row
