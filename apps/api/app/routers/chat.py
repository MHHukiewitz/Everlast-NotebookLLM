import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Message, Notebook
from app.schemas import ChatIn, MessageOut
from app.services.chat_agent import run_chat
from app.services.tracing import score_trace

api = APIRouter(prefix="/api/notebooks/{notebook_id}")


@api.get("/messages", response_model=list[MessageOut])
async def list_messages(notebook_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> list[Message]:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None or notebook.tenant_id != settings.default_tenant_id:
        raise HTTPException(404, "Notebook nicht gefunden")
    result = await session.execute(
        select(Message).where(Message.notebook_id == notebook_id).order_by(Message.created_at.asc())
    )
    return list(result.scalars())


@api.delete("/messages")
async def clear_messages(notebook_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(delete(Message).where(Message.notebook_id == notebook_id))
    await session.commit()
    return {"status": "cleared"}


@api.post("/chat")
async def chat(
    notebook_id: uuid.UUID, body: ChatIn, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    notebook = await session.get(Notebook, notebook_id)
    if notebook is None or notebook.tenant_id != settings.default_tenant_id:
        raise HTTPException(404, "Notebook nicht gefunden")

    async def events():
        async for payload in run_chat(session, notebook, body.content):
            yield f"data: {json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@api.post("/messages/{message_id}/feedback")
async def feedback(
    notebook_id: uuid.UUID,
    message_id: uuid.UUID,
    value: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    message = await session.get(Message, message_id)
    if message is None or message.notebook_id != notebook_id:
        raise HTTPException(404, "Nachricht nicht gefunden")
    if message.trace_id:
        score_trace(message.trace_id, "user_feedback", float(value))
    return {"status": "ok"}
