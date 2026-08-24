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

    default_provider: str = "ollama"
    default_model: str = "llama3.2"
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

    embedding_backend: str = "ollama"
    embedding_dim: int = 768
    embedding_model: str = "nomic-embed-text"

    searxng_url: str = "http://localhost:8080"
    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    file_store: str = "./data/files"
    retention_days: int = 30
    research_scratch_days: int = 30
    prompt_version: str = "notebook-v1"


settings = Settings()
