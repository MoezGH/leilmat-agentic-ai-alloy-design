from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenRouter / DeepSeek
    openrouter_api_key: str = ""
    llm_model: str = "deepseek/deepseek-v4-pro"
    # Fast / cheap model for low-stakes utility calls (session
    # auto-naming, etc.) where v4-pro's reasoning is overkill.  DeepSeek
    # V3 chat is ~20x cheaper per token and sub-second.  Override via
    # LLM_MODEL_FAST in .env if a better fast model becomes available.
    llm_model_fast: str = "deepseek/deepseek-chat"
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

    # ── Supabase auth (Phase B) ──────────────────────────────────────
    # Shared HS256 secret across all Leil sub-apps.  When empty, the
    # AuthMiddleware runs in soft-mode: ENFORCED_PREFIXES are allowed
    # with a warning so local-dev without Supabase still works.
    supabase_jwt_secret: str = ""

    # ── LeilAI-5 billing (Phase D, optional) ─────────────────────────
    # Base URL of the LeilAI-5 billing API used by the credit-check
    # middleware.  Blank disables the middleware entirely (Phase 0a not
    # yet deployed — credit deduction stays as logged-only no-op).
    leil_agent_url: str = ""
    # Shared HMAC token sub-apps include on every billing call.  Issued
    # by LeilAI-5 once Phase 0a's service-token middleware is live.
    leil_service_token: str = ""

    # ── Daytona cloud compute (grain-structure tier) ─────────────────
    # When ``daytona_api_key`` is blank the whole cloud-compute feature
    # is DARK: the /api/compute/* endpoints return 503 and the reaper
    # never starts.  Setting the key (in .env) flips it live.  The API
    # is the sole holder of this key — it never reaches the browser.
    daytona_api_key: str = ""
    # Pre-baked snapshot id with Neper + POV-Ray compiled in (built once
    # via apps/api/compute/snapshots/neper.py).  Blank → jobs fall back
    # to the default image and build Neper at runtime (~100 s, slow).
    daytona_snapshot_neper: str = ""
    # Always-on cost guardrails, enforced server-side regardless of the
    # (currently dormant) LeilAI-5 credit system, because real money is
    # spent the moment a sandbox runs.
    daytona_daily_budget_usd: float = 2.0      # hard daily spend ceiling
    daytona_max_concurrent_jobs: int = 2       # parallel sandbox cap
    daytona_job_wall_cap_s: int = 900          # per-job hard kill (15 min)


settings = Settings()
