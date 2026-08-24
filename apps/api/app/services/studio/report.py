from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook
from app.services.studio.generate import generate_json, save_artifact

SYSTEM = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Schreibe einen sachlichen Bericht auf Deutsch als Markdown.
Nutze nur den gelieferten Quellenkontext.
Setze Zitate [n] an Sätze. n ist die Nummer im Quellenkontext.
Erfinde keine Fakten, Zahlen oder Namen.
Schliesse den Bericht mit der Zeile: Dieser Bericht ist KI-generiert.
Antworte nur mit einem JSON-Objekt.
Schema: {"title": "string", "body_md": "string"}
"""

USER = """Thema: {topic}

Quellenkontext:
{context}
"""


async def create_report(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    payload = await generate_json(session, notebook, args.get("topic") or "", SYSTEM, USER)
    body = str(payload.get("body_md") or "").strip()
    if not body:
        raise ValueError("Das Modell lieferte keinen Bericht.")
    title = str(payload.get("title") or "Bericht")
    return await save_artifact(session, notebook, "studio.report", "report", title, payload)
