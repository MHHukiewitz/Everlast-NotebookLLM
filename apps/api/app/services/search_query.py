import re

from app.config import settings
from app.services.connectors import router
from app.services.net import host_open


REWRITE_SYSTEM = (
    "Schreibe nur eine kurze Suchanfrage für eine Vektorsuche. "
    "Nutze 5 bis 12 Stichwörter, Namen und Synonyme. "
    "Bleibe beim Thema der Frage. Verwechsle keine gleichnamigen Marken. "
    "Keine Sätze. Keine Erklärung. Keine Anführungszeichen."
)
WEB_REWRITE_SYSTEM = (
    "Schreibe nur eine Anfrage für eine Websuchmaschine. "
    "Entferne Wörter wie recherchiere, suche, bitte, wichtig. "
    "Behalte Namen, Produkte, Orte, Branche und Jahr. "
    "Bleibe beim Thema der Frage. Verwechsle keine gleichnamigen Marken. "
    "Ergänze sinnvolle Suchwörter und Synonyme. "
    "Eine Zeile, 4 bis 12 Wörter. Keine Anführungszeichen. Keine Erklärung."
)
RETRY_WEB_SYSTEM = (
    "Die erste Websuche hat die Frage nicht beantwortet. "
    "Schreibe eine andere Suchanfrage. "
    "Ändere Winkel, Synonyme oder schließe die falsche Bedeutung aus. "
    "Bleibe beim Thema. Eine Zeile, 4 bis 12 Wörter. Keine Erklärung."
)
_WEB_PREFIX = re.compile(
    r"^(?:bitte\s+)?(?:recherchiere(?:n)?|research|suche(?:\s+im\s+web)?(?:\s+nach)?|search(?:\s+for)?)\s+",
    re.I,
)


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def rewrite_route() -> tuple[str, str] | None:
    if settings.search_rewrite_provider.strip() and settings.search_rewrite_model.strip():
        return settings.search_rewrite_provider.strip(), settings.search_rewrite_model.strip()
    if settings.hetzner_api_key:
        for model_id in _csv(settings.hetzner_models):
            if "3.8" in model_id:
                return "hetzner", model_id
    if host_open(settings.ollama_api_base) and settings.default_provider == "ollama":
        model_id = _csv(settings.default_model)[0] if _csv(settings.default_model) else ""
        if model_id:
            return "ollama", model_id
    return None


def clean_search_query(raw: str, fallback: str) -> str:
    text = (raw or "").strip()
    if not text:
        return fallback
    line = text.splitlines()[0].strip().strip("\"'`“”")
    if not line:
        return fallback
    return line[:180]


def strip_web_query(text: str) -> str:
    line = (text or "").strip()
    cleaned = _WEB_PREFIX.sub("", line).strip(" .")
    return clean_search_query(cleaned, line)


async def _rewrite(question: str, system: str) -> str:
    fallback = question.strip()
    route = rewrite_route()
    if route is None or not fallback:
        return fallback
    provider, model_id = route
    completion = await router.complete(
        provider,
        model_id,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": fallback},
        ],
        max_tokens=48,
    )
    raw = completion.choices[0].message.content or ""
    return clean_search_query(raw, fallback)


async def rewrite_search_query(question: str) -> str:
    return await _rewrite(question.strip(), REWRITE_SYSTEM)


async def rewrite_web_query(question: str) -> str:
    fallback = strip_web_query(question)
    return await _rewrite(fallback, WEB_REWRITE_SYSTEM)


def looks_like_web_query(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned or cleaned != strip_web_query(cleaned):
        return False
    words = cleaned.split()
    return 1 <= len(words) <= 12


async def prepare_web_query(question: str) -> str:
    if looks_like_web_query(question):
        return question.strip()
    return await rewrite_web_query(question)


async def rewrite_retry_web_query(question: str, first_query: str, note: str = "") -> str:
    payload = f"Frage: {question}\nErste Suche: {first_query}"
    if note.strip():
        payload = f"{payload}\nHinweis: {note.strip()[:400]}"
    alt = await _rewrite(payload, RETRY_WEB_SYSTEM)
    if alt.casefold() == first_query.casefold():
        return first_query
    return alt
