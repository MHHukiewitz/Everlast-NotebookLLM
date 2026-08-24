import socket
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

import httpx
from litellm import acompletion

from app.config import settings
from app.schemas import ModelCard, ProviderStatus

_OPENROUTER_LABELS = {
    "claude-sonnet-4.6": "Claude Sonnet 4.6",
    "gpt-5.2": "GPT-5.2",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "gpt-5.6-sol": "GPT-5.6 Sol",
    "gemini-3.7-flash": "Gemini 3.7 Flash",
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "qwen3-235b-a22b-2507": "Qwen3 235B Instruct",
    "glm-5.2": "GLM 5.2",
}


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _label(model_id: str) -> str:
    return model_id.split("/")[-1]


def _hetzner_label(model_id: str) -> str:
    if "3.6" in model_id:
        return "Qwen3.6 35B"
    if "3.8" in model_id:
        return "Qwen3.8 27B"
    return _label(model_id)


def _openrouter_label(model_id: str) -> str:
    return _OPENROUTER_LABELS.get(_label(model_id), _label(model_id))


def _is_ollama_chat_model(name: str) -> bool:
    return "embed" not in name.lower()


def _ollama_model_ids() -> list[str]:
    fallback = _csv(settings.default_model)
    parsed = urlparse(settings.ollama_api_base)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434
    sock = socket.socket()
    sock.settimeout(0.2)
    code = sock.connect_ex((host, port))
    sock.close()
    if code != 0:
        return fallback
    response = httpx.get(f"{settings.ollama_api_base.rstrip('/')}/api/tags", timeout=0.6)
    names: list[str] = []
    for item in response.json().get("models") or []:
        name = str(item.get("name") or item.get("model") or "").strip()
        if name and _is_ollama_chat_model(name) and name not in names:
            names.append(name)
    return names or fallback


class ModelRouter:
    def list_providers(self) -> list[ProviderStatus]:
        ollama_models = [
            ModelCard(
                id=model_id,
                label=_label(model_id),
                provider="ollama",
                available=True,
                notice=None,
            )
            for model_id in _ollama_model_ids()
        ]
        hetzner_ready = bool(settings.hetzner_api_key)
        hetzner_models = [
            ModelCard(id=model_id, label=_hetzner_label(model_id), provider="hetzner", available=hetzner_ready)
            for model_id in _csv(settings.hetzner_models)
        ]
        eu_models = [
            ModelCard(id=model_id, label=_label(model_id), provider="eu", available=True)
            for model_id in _csv(settings.eu_llm_models)
        ]
        openrouter_models = [
            ModelCard(id=model_id, label=_openrouter_label(model_id), provider="openrouter", available=True)
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
                id="hetzner",
                label="Hetzner",
                available=hetzner_ready,
                notice=(
                    "Server in der EU. DSGVO-konform. In der Regel schneller als lokale Modelle."
                    if hetzner_ready
                    else "HETZNER_API_KEY fehlt."
                ),
                models=hetzner_models,
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
        if provider == "hetzner":
            if not settings.hetzner_api_key:
                raise ValueError("Hetzner Inference ist nicht konfiguriert.")
            allow = set(_csv(settings.hetzner_models))
            if allow and model_id not in allow:
                raise ValueError("Dieses Modell steht auf der Hetzner-Allowlist nicht.")
            return {
                "model": model_id,
                "custom_llm_provider": "openai",
                "api_base": settings.hetzner_api_base,
                "api_key": settings.hetzner_api_key,
                "extra_headers": {},
                "extra_body": {
                    "enable_thinking": False,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
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
        if route.get("custom_llm_provider"):
            kwargs["custom_llm_provider"] = route["custom_llm_provider"]
        if route.get("extra_body"):
            kwargs["extra_body"] = route["extra_body"]
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
        if route.get("custom_llm_provider"):
            kwargs["custom_llm_provider"] = route["custom_llm_provider"]
        if route.get("extra_body"):
            kwargs["extra_body"] = route["extra_body"]
        if route["extra_headers"]:
            kwargs["extra_headers"] = route["extra_headers"]
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return await acompletion(**kwargs)


router = ModelRouter()
