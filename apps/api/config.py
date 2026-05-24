from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenRouter / DeepSeek
    openrouter_api_key: str = ""
    llm_model: str = "deepseek/deepseek-v4-pro"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Materials Project
    mp_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://leilmat:leilmat@localhost:5432/leilmat"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # CORS / origins
    allowed_origins: list[str] = ["http://localhost:3000"]

    # ── Rate limiting + LLM cost controls ────────────────────────────
    # Per-IP-per-minute limits.  Apply to every LLM-firing endpoint.
    rate_limit_llm_per_minute: int = 10
    # Heavy CPU endpoints (e.g. Publication-preset microstructure) get
    # a tighter limit because each call can pin a core for minutes.
    rate_limit_heavy_compute_per_minute: int = 4
    # Catch-all default for non-LLM, non-compute endpoints (predict,
    # phase/equilibrium, cost/compute, …).
    rate_limit_default_per_minute: int = 60

    # Daily aggregate spend cap on LLM calls (across ALL users + IPs).
    # When exceeded, the interpret_common helper short-circuits to the
    # deterministic fallback path until UTC-midnight rollover.
    # Set to 0 to disable the cap entirely.
    llm_daily_budget_usd: float = 5.0


settings = Settings()
