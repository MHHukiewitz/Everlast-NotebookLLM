from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notebook, Source

UNTITLED_TITLE = "Unbenanntes Notebook"
TITLE_MAX = 80

GENERIC_HINTS = {
    "informationen zu einem neuen thema",
    "etwas neues erstellen",
    "ein projekt voranbringen",
    "frage stellen oder etwas erstellen",
}

NAME_SKILLS = {
    "sources.add_url",
    "sources.add_text",
    "notes.create",
    "research.fast",
    "research.deep",
}


def is_untitled(title: str | None) -> bool:
    return not (title or "").strip() or title.strip() == UNTITLED_TITLE


def title_from_hint(hint: str) -> str:
    text = " ".join((hint or "").split()).strip(" \"'“”„")
    if not text:
        return ""
    if text.casefold() in GENERIC_HINTS:
        return ""
    if "://" in text and " " not in text:
        host = (urlparse(text).hostname or "").removeprefix("www.")
        if host:
            text = host
    if len(text) > TITLE_MAX:
        cut = text[:TITLE_MAX].rsplit(" ", 1)[0]
        text = cut or text[:TITLE_MAX]
    return text


def maybe_autoname(notebook: Notebook, hint: str) -> bool:
    if not is_untitled(notebook.title):
        return False
    title = title_from_hint(hint)
    if not title:
        return False
    notebook.title = title
    return True


def hint_from_skill(skill_id: str, args: dict, result: dict) -> str:
    for key in ("topic", "focus", "query", "title", "url"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value
    text = args.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip().split("\n", 1)[0]
    title = result.get("title")
    if isinstance(title, str):
        return title
    if skill_id in NAME_SKILLS or skill_id.startswith("studio."):
        return ""
    return ""


def should_autoname_skill(skill_id: str) -> bool:
    return skill_id in NAME_SKILLS or skill_id.startswith("studio.")


async def first_source_title(session: AsyncSession, notebook_id) -> str:
    title = await session.scalar(
        select(Source.title)
        .where(Source.notebook_id == notebook_id)
        .order_by(Source.created_at.asc())
        .limit(1)
    )
    return title or ""


async def autoname_from_skill(
    session: AsyncSession, notebook: Notebook, skill_id: str, args: dict, result: dict
) -> bool:
    if not should_autoname_skill(skill_id):
        return False
    hint = hint_from_skill(skill_id, args, result)
    if not hint:
        hint = await first_source_title(session, notebook.id)
    if maybe_autoname(notebook, hint):
        session.add(notebook)
        return True
    return False
