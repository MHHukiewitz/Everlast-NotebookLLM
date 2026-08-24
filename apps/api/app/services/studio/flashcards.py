from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook
from app.services.studio.generate import generate_json, save_artifact

SYSTEM = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge Karteikarten nur aus den gelieferten Quellen.
Sechs bis zehn Karten.
Vorderseite und Rückseite müssen im Quellenkontext stehen.
Erfinde keine Fakten.
Antworte nur mit einem JSON-Objekt.
Schema: {"title": "string", "cards": [{"front": "string", "back": "string", "cite": "string"}]}
cite ist die Quellennummer wie [1].
"""

USER = """Thema: {topic}

Quellenkontext:
{context}
"""


async def create_flashcards(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    payload = await generate_json(session, notebook, args.get("topic") or "", SYSTEM, USER)
    cards = payload.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("Das Modell lieferte keine Karteikarten.")
    title = str(payload.get("title") or "Karteikarten")
    return await save_artifact(session, notebook, "studio.flashcards", "flashcards", title, payload)
