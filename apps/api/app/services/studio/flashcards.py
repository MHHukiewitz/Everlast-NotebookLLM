from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook
from app.services.studio.generate import STUDIO_USER, generate_json, save_artifact, source_ids_from_args, topic_from_args

SYSTEM = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge Karteikarten nur aus den gelieferten Quellen.
Sechs bis zehn Karten.
Vorderseite und Rückseite müssen im Quellenkontext stehen.
Erfinde keine Fakten.
Antworte nur mit einem JSON-Objekt.
Schema: {"title": "string", "cards": [{"front": "string", "back": "string", "cite": "string"}]}
cite ist die Quellennummer wie [1].
"""

def prepare_flashcards(payload: dict[str, Any]) -> tuple[bool, str]:
    cards = payload.get("cards")
    if not isinstance(cards, list) or len(cards) < 6:
        return False, "weniger als sechs Karten"
    for card in cards:
        if not isinstance(card, dict):
            return False, "Karte fehlt"
        if not str(card.get("front") or "").strip() or not str(card.get("back") or "").strip():
            return False, "Karte ohne Vorder- oder Rückseite"
    return True, ""


async def create_flashcards(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    payload = await generate_json(
        session,
        notebook,
        topic_from_args(args),
        SYSTEM,
        STUDIO_USER,
        source_ids_from_args(args),
        check=prepare_flashcards,
    )
    title = str(payload.get("title") or "Karteikarten")
    return await save_artifact(session, notebook, "studio.flashcards", "flashcards", title, payload)
