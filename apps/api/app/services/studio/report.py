from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook
from app.services.studio.generate import STUDIO_USER, generate_json, save_artifact, source_ids_from_args, topic_from_args

SYSTEM = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Schreibe einen sachlichen Bericht auf Deutsch als Markdown.
Nutze nur den gelieferten Quellenkontext.
Setze Zitate [n] an Sätze. n ist die Nummer im Quellenkontext.
Erfinde keine Fakten, Zahlen oder Namen.
Schliesse den Bericht mit der Zeile: Dieser Bericht ist KI-generiert.
Antworte nur mit einem JSON-Objekt.
Schema: {"title": "string", "body_md": "string"}
"""

def prepare_report(payload: dict[str, Any]) -> tuple[bool, str]:
    body = str(payload.get("body_md") or "").strip()
    if len(body) < 80:
        return False, "Bericht ist zu kurz"
    if "[" not in body:
        return False, "Bericht hat keine Zitate"
    return True, ""


async def create_report(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    payload = await generate_json(
        session,
        notebook,
        topic_from_args(args),
        SYSTEM,
        STUDIO_USER,
        source_ids_from_args(args),
        check=prepare_report,
    )
    title = str(payload.get("title") or "Bericht")
    return await save_artifact(session, notebook, "studio.report", "report", title, payload)
