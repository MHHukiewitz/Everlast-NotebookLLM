from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook
from app.services.studio.generate import STUDIO_USER, generate_json, save_artifact, source_ids_from_args, topic_from_args

SYSTEM = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge eine Präsentation nur aus den gelieferten Quellen.
Vier bis acht Folien.
Jede Folie hat eine Überschrift und drei bis fünf Stichpunkte.
Erfinde keine Fakten.
Antworte nur mit einem JSON-Objekt.
Schema: {"title": "string", "slides": [{"heading": "string", "bullets": ["string"], "notes": "string"}]}
"""

def prepare_slides(payload: dict[str, Any]) -> tuple[bool, str]:
    slides = payload.get("slides")
    if not isinstance(slides, list) or len(slides) < 4:
        return False, "weniger als vier Folien"
    for slide in slides:
        if not isinstance(slide, dict):
            return False, "Folie fehlt"
        if not str(slide.get("heading") or "").strip():
            return False, "Folie ohne Überschrift"
        bullets = slide.get("bullets")
        if not isinstance(bullets, list) or len(bullets) < 3:
            return False, "Folie hat zu wenige Stichpunkte"
    return True, ""


async def create_slides(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    payload = await generate_json(
        session,
        notebook,
        topic_from_args(args),
        SYSTEM,
        STUDIO_USER,
        source_ids_from_args(args),
        check=prepare_slides,
    )
    title = str(payload.get("title") or "Präsentation")
    return await save_artifact(session, notebook, "studio.slides", "slides", title, payload)
