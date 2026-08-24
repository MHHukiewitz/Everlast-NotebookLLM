from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook
from app.services.studio.generate import generate_json, save_artifact

SYSTEM = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge eine Datentabelle nur aus den gelieferten Quellen.
Mindestens zwei Spalten und drei Zeilen.
Zellen dürfen nur Fakten aus dem Quellenkontext enthalten.
Erfinde keine Zahlen, Namen oder Umsätze.
Antworte nur mit einem JSON-Objekt.
Schema: {"title": "string", "columns": ["string", "string"], "rows": [["string", "string"]]}
"""

USER = """Thema: {topic}

Quellenkontext:
{context}
"""


async def create_table(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    payload = await generate_json(session, notebook, args.get("topic") or "", SYSTEM, USER)
    columns = payload.get("columns")
    rows = payload.get("rows")
    if not isinstance(columns, list) or len(columns) < 2:
        raise ValueError("Das Modell lieferte keine Tabelle.")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Das Modell lieferte keine Tabelle.")
    title = str(payload.get("title") or "Datentabelle")
    return await save_artifact(session, notebook, "studio.table", "table", title, payload)
