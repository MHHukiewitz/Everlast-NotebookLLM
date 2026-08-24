from typing import Any, Literal

from app.config import settings
from app.models import Notebook
from app.schemas import ModelCard, ModalitiesOut, ProviderStatus
from app.services.connectors import router as model_router
from app.services.net import host_open
from app.services.piper_tts import piper_ready

Kind = Literal["tts", "image"]
ENGLISH_ONLY_TTS_MODELS = frozenset({"kokoro"})
LOCAL_GERMAN_TTS = "piper"
WEAK_IMAGE_MODELS = frozenset(
    {
        "google/gemini-2.5-flash-image",
        "google/gemini-3.1-flash-image",
    }
)
DEFAULT_IMAGE_OPENROUTER = [
    "google/gemini-3-pro-image",
    "openai/gpt-image-2",
    "black-forest-labs/flux.2-pro",
    "bytedance-seed/seedream-5-0-pro",
]
_IMAGE_LABELS = {
    "google/gemini-3-pro-image": "Gemini 3 Pro Image",
    "google/gemini-2.5-flash-image": "Gemini 2.5 Flash Image",
    "google/gemini-3.1-flash-image": "Gemini 3.1 Flash Image",
    "openai/gpt-image-2": "GPT Image 2",
    "black-forest-labs/flux.2-pro": "FLUX.2 Pro",
    "bytedance-seed/seedream-5-0-pro": "Seedream 5.0 Pro",
}


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _label(model_id: str) -> str:
    return _IMAGE_LABELS.get(model_id, model_id.split("/")[-1])


def image_openrouter_models() -> list[str]:
    configured = _csv(settings.image_openrouter_models)
    if not configured:
        return list(DEFAULT_IMAGE_OPENROUTER)
    if all(item in WEAK_IMAGE_MODELS for item in configured):
        return [*DEFAULT_IMAGE_OPENROUTER, *[item for item in configured if item not in DEFAULT_IMAGE_OPENROUTER]]
    return configured


def openai_v1(url: str) -> str:
    base = url.rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


def _lane_models(ids: list[str], provider: str) -> list[ModelCard]:
    return [
        ModelCard(id=model_id, label=_label(model_id), provider=provider, available=True)
        for model_id in ids
    ]


def list_modalities() -> ModalitiesOut:
    tts_local_up = piper_ready() or host_open(settings.tts_local_base_url)
    image_local_up = host_open(settings.image_local_base_url)
    eu_up = bool(settings.eu_llm_base_url and settings.eu_llm_api_key)
    or_up = bool(settings.openrouter_api_key)
    eu_notice = (
        "Nur EU-fähige Modelle. Gateway-Standort ist nicht gleich Inferenz-Standort. "
        "Ein AVV / DPA ist erforderlich. Es geht nur Skripttext, keine Embeddings."
        if settings.eu_llm_base_url
        else "EU_LLM_BASE_URL und EU_LLM_API_KEY fehlen."
    )
    or_notice = (
        "Drittland-Transfer. Nur für die Demo. Es geht nur Skripttext, keine Embeddings."
        if settings.openrouter_api_key
        else "OPENROUTER_API_KEY fehlt."
    )
    tts = [
        ProviderStatus(
            id="local",
            label="Lokal",
            available=tts_local_up,
            notice=(
                "Deutsche Studio-Ausgabe nutzt lokale Piper-Stimmen. Kokoro spricht nur Englisch."
                if tts_local_up
                else "Lokale Piper-Stimmen fehlen. Lege de_DE-thorsten-medium in data/tts-voices ab."
            ),
            models=_lane_models(_local_tts_models(), "local"),
        ),
        ProviderStatus(
            id="eu",
            label="EU",
            available=eu_up,
            notice=eu_notice,
            models=_lane_models(_csv(settings.tts_eu_models), "eu"),
        ),
        ProviderStatus(
            id="openrouter",
            label="OpenRouter",
            available=or_up,
            notice=or_notice,
            models=_lane_models(_csv(settings.tts_openrouter_models), "openrouter"),
        ),
    ]
    image = [
        ProviderStatus(
            id="local",
            label="Lokal",
            available=image_local_up,
            notice=(
                "Daten bleiben auf diesem Rechner. Starte ein OpenAI-kompatibles Bildmodell."
                if image_local_up
                else "Lokales Bildmodell ist nicht erreichbar. Video nutzt dann gezeichnete Folien."
            ),
            models=_lane_models(_csv(settings.image_local_models), "local"),
        ),
        ProviderStatus(
            id="eu",
            label="EU",
            available=eu_up,
            notice=eu_notice,
            models=_lane_models(_csv(settings.image_eu_models), "eu"),
        ),
        ProviderStatus(
            id="openrouter",
            label="OpenRouter",
            available=or_up,
            notice=or_notice,
            models=_lane_models(image_openrouter_models(), "openrouter"),
        ),
    ]
    return ModalitiesOut(llm=model_router.list_providers(), tts=tts, image=image)


def _local_tts_models() -> list[str]:
    models = _csv(settings.tts_local_models)
    if LOCAL_GERMAN_TTS not in models:
        return [LOCAL_GERMAN_TTS, *models]
    return models


def _allowlist(kind: Kind, provider: str) -> list[str]:
    if kind == "tts" and provider == "local":
        return _local_tts_models()
    if kind == "tts" and provider == "eu":
        return _csv(settings.tts_eu_models)
    if kind == "tts" and provider == "openrouter":
        return _csv(settings.tts_openrouter_models)
    if kind == "image" and provider == "local":
        return _csv(settings.image_local_models)
    if kind == "image" and provider == "eu":
        return _csv(settings.image_eu_models)
    if kind == "image" and provider == "openrouter":
        return image_openrouter_models()
    return []


def resolve_media(kind: Kind, provider: str, model_id: str) -> dict[str, Any]:
    allow = _allowlist(kind, provider)
    chosen = model_id or (allow[0] if allow else "")
    if kind == "image" and provider == "openrouter" and chosen in WEAK_IMAGE_MODELS:
        upgrade = next((item for item in DEFAULT_IMAGE_OPENROUTER if item in allow), "")
        if upgrade:
            chosen = upgrade
    if allow and chosen and chosen not in allow:
        label = "Sprachmodell" if kind == "tts" else "Bildmodell"
        raise ValueError(f"Dieses {label} steht auf der Allowlist nicht.")
    if provider == "local":
        base = settings.tts_local_base_url if kind == "tts" else settings.image_local_base_url
        missing = (
            "Lokales Sprachmodell ist nicht erreichbar."
            if kind == "tts"
            else "Lokales Bildmodell ist nicht erreichbar."
        )
        if not host_open(base):
            raise ValueError(missing)
        return {"provider": provider, "model": chosen, "api_base": openai_v1(base), "headers": {}}
    if provider == "eu":
        if not settings.eu_llm_base_url or not settings.eu_llm_api_key:
            raise ValueError("EU-Gateway ist nicht konfiguriert.")
        return {
            "provider": provider,
            "model": chosen,
            "api_base": openai_v1(settings.eu_llm_base_url),
            "headers": {"Authorization": f"Bearer {settings.eu_llm_api_key}"},
        }
    if provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ValueError("OpenRouter ist nicht konfiguriert.")
        return {
            "provider": provider,
            "model": chosen,
            "api_base": "https://openrouter.ai/api/v1",
            "headers": {
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": "https://everlast.local/notebook",
                "X-Title": "Everlast Notebook",
            },
        }
    raise ValueError(f"Unbekannter Provider: {provider}")


def tts_language_code(language: str | None) -> str:
    code = (language or "de").strip().lower().replace("_", "-")
    if code.startswith("en"):
        return "en"
    return "de"


def uses_english_only_local_tts(provider: str, model_id: str) -> bool:
    chosen = (model_id or "").strip() or "kokoro"
    return provider == "local" and chosen.split("/")[-1] in ENGLISH_ONLY_TTS_MODELS


def piper_route() -> dict[str, Any]:
    if not piper_ready():
        raise ValueError(
            f"Piper-Stimmen fehlen. Lege de_DE-thorsten-medium in {settings.tts_piper_voice_dir} ab."
        )
    return {"provider": "local", "model": LOCAL_GERMAN_TTS, "api_base": "piper", "headers": {}}


def require_tts(notebook: Notebook, language: str | None = "de") -> dict[str, Any]:
    provider = notebook.tts_provider
    model_id = notebook.tts_model
    local_model = ((model_id or "").strip() or LOCAL_GERMAN_TTS).split("/")[-1]
    if provider == "local" and tts_language_code(language) == "de":
        if local_model in ENGLISH_ONLY_TTS_MODELS or local_model == LOCAL_GERMAN_TTS:
            return piper_route()
    if provider == "local" and local_model == LOCAL_GERMAN_TTS:
        return piper_route()
    return resolve_media("tts", provider, model_id)


def image_ready(notebook: Notebook) -> bool:
    if notebook.image_provider == "local":
        return host_open(settings.image_local_base_url)
    if notebook.image_provider == "eu":
        return bool(settings.eu_llm_base_url and settings.eu_llm_api_key)
    if notebook.image_provider == "openrouter":
        return bool(settings.openrouter_api_key)
    return False
