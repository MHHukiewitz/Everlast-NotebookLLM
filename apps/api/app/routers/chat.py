import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import owned_notebook
from app.models import Message, Notebook
from app.schemas import ChatIn, MessageOut
from app.services.chat_agent import run_chat
from app.services.tracing import score_trace

api = APIRouter(prefix="/api/notebooks/{notebook_id}")


@api.get("/messages", response_model=list[MessageOut])
async def list_messages(
    notebook: Notebook = Depends(owned_notebook), session: AsyncSession = Depends(get_session)
) -> list[Message]:
    result = await session.execute(
        select(Message).where(Message.notebook_id == notebook.id).order_by(Message.created_at.asc())
    )
    return list(result.scalars())


@api.delete("/messages")
async def clear_messages(
    notebook: Notebook = Depends(owned_notebook), session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    await session.execute(delete(Message).where(Message.notebook_id == notebook.id))
    await session.commit()
    return {"status": "cleared"}


@api.post("/chat")
async def chat(
    body: ChatIn,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    async def events():
        async for payload in run_chat(session, notebook, body.content):
            yield f"data: {json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@api.post("/messages/{message_id}/feedback")
async def feedback(
    message_id: uuid.UUID,
    value: int,
    notebook: Notebook = Depends(owned_notebook),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    message = await session.get(Message, message_id)
    if message is None or message.notebook_id != notebook.id:
        raise HTTPException(404, "Nachricht nicht gefunden")
    if message.trace_id:
        score_trace(message.trace_id, "user_feedback", float(value))
    return {"status": "ok"}
