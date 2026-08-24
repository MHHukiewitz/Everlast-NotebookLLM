from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook
from app.services.studio.generate import STUDIO_USER, generate_json, save_artifact, source_ids_from_args, topic_from_args

SYSTEM = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge eine Datentabelle nur aus den gelieferten Quellen.
Mindestens zwei Spalten und drei Zeilen.
Zellen dürfen nur Fakten aus dem Quellenkontext enthalten.
Erfinde keine Zahlen, Namen oder Umsätze.
Antworte nur mit einem JSON-Objekt.
Schema: {"title": "string", "columns": ["string", "string"], "rows": [["string", "string"]]}
"""

def prepare_table(payload: dict[str, Any]) -> tuple[bool, str]:
    columns = payload.get("columns")
    rows = payload.get("rows")
    if not isinstance(columns, list) or len(columns) < 2:
        return False, "weniger als zwei Spalten"
    if not isinstance(rows, list) or len(rows) < 3:
        return False, "weniger als drei Zeilen"
    width = len(columns)
    for row in rows:
        if not isinstance(row, list) or len(row) != width:
            return False, "Zeile passt nicht zu den Spalten"
        if not any(str(cell).strip() for cell in row):
            return False, "leere Zeile"
    return True, ""


async def create_table(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    payload = await generate_json(
        session,
        notebook,
        topic_from_args(args),
        SYSTEM,
        STUDIO_USER,
        source_ids_from_args(args),
        check=prepare_table,
    )
    title = str(payload.get("title") or "Datentabelle")
    return await save_artifact(session, notebook, "studio.table", "table", title, payload)
