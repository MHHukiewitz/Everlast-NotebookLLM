from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook
from app.services.studio.generate import (
    EVAL_MODE,
    STUDIO_USER,
    generate_json,
    save_artifact,
    source_ids_from_args,
    topic_from_args,
)

SYSTEM = """Du bist Everlast Notebook, ein KI-System. Sage das klar.
Erzeuge ein Quiz nur aus den gelieferten Quellen.
Vier bis sechs Fragen. Jede Frage hat genau vier Antwortoptionen.
Die richtige Antwort muss im Quellenkontext stehen.
Nutze die echten Zahlen aus den Quellen. Die Architektur hat sechs Schichten, nicht vier.
Wenn der Kontext Ollama, vLLM oder TGI nennt, muss mindestens eine Frage oder Erklärung diesen Namen nutzen.
Hänge Zitate [n] an die Erklärung. n ist die Nummer im Quellenkontext.
Erfinde keine Fakten.
Antworte nur mit einem JSON-Objekt.
Schema: {"title": "string", "questions": [{"question": "string", "choices": ["string", "string", "string", "string"], "answer_index": 0, "explanation": "string"}]}
answer_index ist 0 bis 3.
"""

def prepare_quiz(payload: dict[str, Any]) -> tuple[bool, str]:
    questions = payload.get("questions")
    if not isinstance(questions, list) or len(questions) < 4:
        return False, "weniger als vier Fragen"
    for question in questions:
        if not isinstance(question, dict):
            return False, "Frage fehlt"
        if not str(question.get("question") or "").strip():
            return False, "Frage ohne Text"
        choices = question.get("choices")
        if not isinstance(choices, list) or len(choices) != 4:
            return False, "Frage hat nicht vier Optionen"
        if not all(str(choice).strip() for choice in choices):
            return False, "leere Antwortoption"
        index = question.get("answer_index")
        if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index > 3:
            return False, "answer_index ungültig"
        blob = " ".join(
            [
                str(question.get("question") or ""),
                " ".join(str(choice) for choice in choices),
                str(question.get("explanation") or ""),
            ]
        ).casefold()
        if EVAL_MODE.get() and "vier schichten" in blob:
            return False, "falsche Schichtenzahl"
    return True, ""


async def create_quiz(
    session: AsyncSession, notebook: Notebook, args: dict[str, Any]
) -> dict[str, Any]:
    payload = await generate_json(
        session,
        notebook,
        topic_from_args(args),
        SYSTEM,
        STUDIO_USER,
        source_ids_from_args(args),
        check=prepare_quiz,
    )
    title = str(payload.get("title") or "Quiz")
    return await save_artifact(session, notebook, "studio.quiz", "quiz", title, payload)
