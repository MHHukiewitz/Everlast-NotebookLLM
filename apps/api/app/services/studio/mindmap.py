from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook
from app.services.studio.generate import generate_json, save_artifact

SYSTEM = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge eine Mindmap nur aus den gelieferten Quellen.
Antworte nur mit einem JSON-Objekt.
Schema: {"title": "string", "mermaid_lines": ["mindmap", "  root((Thema))", "    Zweig"]}
mermaid_lines ist ein Array von Zeilen. Keine Backslashes.
Nutze nur deutsche Begriffe, die in den Quellen stehen.
Erfinde keine Knoten, Zahlen oder Namen.
Markiere den Titel als KI-generiert, indem du '(KI-generiert)' anhängst.
"""

USER = """Thema: {topic}

Quellenkontext:
{context}
"""


async def create_mindmap(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    payload = await generate_json(session, notebook, args.get("topic") or "", SYSTEM, USER)
    mermaid = str(payload.get("mermaid") or "").strip()
    lines = payload.get("mermaid_lines")
    if not mermaid and isinstance(lines, list):
        mermaid = "\n".join(str(line) for line in lines)
    if not mermaid.strip():
        raise ValueError("Das Modell lieferte keine Mindmap.")
    payload["mermaid"] = mermaid
    title = str(payload.get("title") or "Mindmap")
    return await save_artifact(session, notebook, "studio.mindmap", "mindmap", title, payload)
