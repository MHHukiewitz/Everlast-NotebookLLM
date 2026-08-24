from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    default_tenant_id: str = "default"
    default_user_id: str = "demo"
    session_secret: str = "change-me-session-secret"
    session_https: bool = False
    demo_email: str = ""
    demo_password: str = ""
    register_allowlist: str = ""
    database_url: str = "postgresql+asyncpg://notebook:notebook@localhost:5432/notebook"
    redis_url: str = ""

    default_provider: str = "hetzner"
    default_model: str = "Qwen/Qwen3.6-35B-A3B-FP8"
    ollama_api_base: str = "http://localhost:11434"

    openrouter_api_key: str = ""
    openrouter_models: str = (
        "openrouter/anthropic/claude-sonnet-4.6,"
        "openrouter/openai/gpt-5.2,"
        "openrouter/google/gemini-2.5-pro"
    )

    eu_llm_base_url: str = ""
    eu_llm_api_key: str = ""
    eu_llm_models: str = ""

    hetzner_api_base: str = "https://inference.hetzner.com/api/v1"
    hetzner_api_key: str = ""
    hetzner_models: str = "Qwen/Qwen3.6-35B-A3B-FP8,Qwen3.8-27B"

    embedding_backend: str = "ollama"
    embedding_dim: int = 768
    embedding_model: str = "nomic-embed-text"

    tts_local_base_url: str = "http://127.0.0.1:8880"
    tts_local_models: str = "kokoro"
    tts_eu_models: str = ""
    tts_openrouter_models: str = "openai/gpt-4o-mini-tts"
    tts_voice_a: str = "alloy"
    tts_voice_b: str = "nova"

    image_local_base_url: str = "http://127.0.0.1:8081"
    image_local_models: str = "flux"
    image_eu_models: str = ""
    image_openrouter_models: str = "google/gemini-2.5-flash-image"
    default_image_provider: str = "openrouter"
    default_image_model: str = "google/gemini-2.5-flash-image"

    searxng_url: str = "http://localhost:8080"
    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    file_store: str = "./data/files"
    retention_days: int = 30
    research_scratch_days: int = 30
    prompt_version: str = "notebook-v1"


settings = Settings()
