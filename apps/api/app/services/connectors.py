from collections.abc import AsyncIterator
from typing import Any

from litellm import acompletion

from app.config import settings
from app.schemas import ModelCard, ProviderStatus


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _label(model_id: str) -> str:
    return model_id.split("/")[-1]


class ModelRouter:
    def list_providers(self) -> list[ProviderStatus]:
        ollama_models = [
            ModelCard(
                id=settings.default_model,
                label=settings.default_model,
                provider="ollama",
                available=True,
                notice=None,
            )
        ]
        eu_models = [
            ModelCard(id=model_id, label=_label(model_id), provider="eu", available=True)
            for model_id in _csv(settings.eu_llm_models)
        ]
        openrouter_models = [
            ModelCard(id=model_id, label=_label(model_id), provider="openrouter", available=True)
            for model_id in _csv(settings.openrouter_models)
        ]
        return [
            ProviderStatus(
                id="ollama",
                label="Lokal",
                available=True,
                notice="Daten bleiben auf diesem Rechner.",
                models=ollama_models,
            ),
            ProviderStatus(
                id="eu",
                label="EU",
                available=bool(settings.eu_llm_base_url and settings.eu_llm_api_key),
                notice=(
                    "Nur EU-fähige Modelle. Gateway-Standort ist nicht gleich Inferenz-Standort. "
                    "Ein AVV / DPA ist erforderlich."
                    if settings.eu_llm_base_url
                    else "EU_LLM_BASE_URL und EU_LLM_API_KEY fehlen."
                ),
                models=eu_models,
            ),
            ProviderStatus(
                id="openrouter",
                label="OpenRouter",
                available=bool(settings.openrouter_api_key),
                notice=(
                    "Drittland-Transfer. Nur für die Demo. Prompts und Chunks verlassen den Rechner."
                    if settings.openrouter_api_key
                    else "OPENROUTER_API_KEY fehlt."
                ),
                models=openrouter_models,
            ),
        ]

    def resolve(self, provider: str, model_id: str) -> dict[str, Any]:
        if provider == "ollama":
            return {
                "model": f"ollama/{model_id.removeprefix('ollama/')}",
                "api_base": settings.ollama_api_base,
                "extra_headers": {},
            }
        if provider == "eu":
            if not settings.eu_llm_base_url or not settings.eu_llm_api_key:
                raise ValueError("EU-Gateway ist nicht konfiguriert.")
            allow = set(_csv(settings.eu_llm_models))
            if allow and model_id not in allow:
                raise ValueError("Dieses Modell steht auf der EU-Allowlist nicht.")
            return {
                "model": model_id if "/" in model_id else f"openai/{model_id}",
                "api_base": settings.eu_llm_base_url,
                "api_key": settings.eu_llm_api_key,
                "extra_headers": {},
            }
        if provider == "openrouter":
            if not settings.openrouter_api_key:
                raise ValueError("OpenRouter ist nicht konfiguriert.")
            allow = set(_csv(settings.openrouter_models))
            if allow and model_id not in allow:
                raise ValueError("Dieses Modell steht auf der OpenRouter-Allowlist nicht.")
            routed = model_id if model_id.startswith("openrouter/") else f"openrouter/{model_id}"
            return {
                "model": routed,
                "api_key": settings.openrouter_api_key,
                "extra_headers": {
                    "HTTP-Referer": "https://everlast.local/notebook",
                    "X-Title": "Everlast Notebook",
                },
            }
        raise ValueError(f"Unbekannter Provider: {provider}")

    async def stream_chat(
        self,
        provider: str,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        route = self.resolve(provider, model_id)
        kwargs: dict[str, Any] = {
            "model": route["model"],
            "messages": messages,
            "stream": True,
        }
        if "api_base" in route:
            kwargs["api_base"] = route["api_base"]
        if "api_key" in route:
            kwargs["api_key"] = route["api_key"]
        if route["extra_headers"]:
            kwargs["extra_headers"] = route["extra_headers"]
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = await acompletion(**kwargs)
        async for chunk in response:
            yield chunk

    async def complete(
        self,
        provider: str,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        route = self.resolve(provider, model_id)
        kwargs: dict[str, Any] = {
            "model": route["model"],
            "messages": messages,
            "stream": False,
        }
        if "api_base" in route:
            kwargs["api_base"] = route["api_base"]
        if "api_key" in route:
            kwargs["api_key"] = route["api_key"]
        if route["extra_headers"]:
            kwargs["extra_headers"] = route["extra_headers"]
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return await acompletion(**kwargs)


router = ModelRouter()
