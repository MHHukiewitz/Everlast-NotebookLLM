from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook
from app.services.studio.generate import generate_json, save_artifact

SYSTEM = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge ein Quiz nur aus den gelieferten Quellen.
Vier bis sechs Fragen. Jede Frage hat genau vier Antwortoptionen.
Die richtige Antwort muss im Quellenkontext stehen.
Erfinde keine Fakten.
Antworte nur mit einem JSON-Objekt.
Schema: {"title": "string", "questions": [{"question": "string", "choices": ["string", "string", "string", "string"], "answer_index": 0, "explanation": "string"}]}
answer_index ist 0 bis 3.
"""

USER = """Thema: {topic}

Quellenkontext:
{context}
"""


async def create_quiz(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    payload = await generate_json(session, notebook, args.get("topic") or "", SYSTEM, USER)
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("Das Modell lieferte kein Quiz.")
    title = str(payload.get("title") or "Quiz")
    return await save_artifact(session, notebook, "studio.quiz", "quiz", title, payload)
