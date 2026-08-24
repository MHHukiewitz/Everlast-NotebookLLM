import re
from typing import Any

from app.config import settings

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


def start_trace(name: str, user_id: str, metadata: dict[str, Any] | None = None) -> str | None:
    if _LANGFUSE is None:
        return None
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
        name="chat",
        model=model,
        input=mask_text(prompt),
        output=mask_text(completion),
        metadata=metadata or {},
    )
