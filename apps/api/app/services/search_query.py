from app.config import settings
from app.services.connectors import router
from app.services.net import host_open


REWRITE_SYSTEM = (
    "Schreibe nur eine kurze Suchanfrage für eine Vektorsuche. "
    "Nutze 5 bis 12 Stichwörter, Namen und Synonyme. "
    "Keine Sätze. Keine Erklärung. Keine Anführungszeichen."
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


async def rewrite_search_query(question: str) -> str:
    fallback = question.strip()
    route = rewrite_route()
    if route is None or not fallback:
        return fallback
    provider, model_id = route
    completion = await router.complete(
        provider,
        model_id,
        [
            {"role": "system", "content": REWRITE_SYSTEM},
            {"role": "user", "content": fallback},
        ],
        max_tokens=48,
    )
    raw = completion.choices[0].message.content or ""
    return clean_search_query(raw, fallback)
