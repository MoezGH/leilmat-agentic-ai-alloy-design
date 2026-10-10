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
    daytona_daily_budget_usd: float = 10.0     # hard daily spend ceiling (long jobs)
    daytona_max_concurrent_jobs: int = 2       # parallel sandbox cap
    daytona_job_wall_cap_s: int = 900          # default per-job hard kill (15 min)
    # Cloud-job billing. LeilAI-5's deduct endpoint has no wall-time shape (only
    # token + flat), so LeilMat prices cloud jobs itself and bills via the flat
    # path: cost_usd = wall_secs/3600 × cpu × daytona_usd_per_vcpu_hour ×
    # cloud_cost_markup, then × credits_per_dollar → flat_credits.
    # 0.1 ≈ Daytona all-in per-vCPU rate (vCPU $0.0504/h + 2 GiB/vCPU mem
    # $0.0324/h ≈ $0.083 at our 4-vCPU/8-GiB sandbox), rounded up for
    # storage/overhead headroom. See daytona.io/pricing.
    daytona_usd_per_vcpu_hour: float = 0.1
    cloud_cost_markup: float = 3.0             # same 3× markup as LLM token cost / LeilCFD
    credits_per_dollar: int = 100              # MUST match LeilAI-5 CREDITS_PER_DOLLAR
    # Pre-baked SPPARKS snapshot (built once via apps/api/compute/snapshots/spparks.py).
    # Blank → grow self-bootstraps SPPARKS at runtime (~7 min build).
    daytona_snapshot_spparks: str = ""
    # SPPARKS grain growth is a legitimately long Monte-Carlo run. Measured rate
    # on a Daytona core is ~1.3e7/nspins site-visits/s (≈12k/s at nspins=1000);
    # e.g. 48³×300 ≈ 45 min, 64³×300 ≈ 106 min. Per the "long jobs are fine,
    # notify when done" design, the cap is generous (2 h); the daily USD ceiling
    # + timeout + reaper are the spend guardrails.
    daytona_grow_wall_cap_s: int = 7200        # 2 h
    # SPPARKS runs MPI-parallel (spk_mpi + mpirun -np N) for near-linear
    # multi-core speedup (~5× at np=4, measured). Daytona Tier 2 caps a sandbox
    # at 4 vCPU, so 4 is the ceiling for now. On Tier 3+ this can rise — bump
    # this AND rebuild the snapshot with the matching higher cpu (the snapshot's
    # baked Resources determine the launched sandbox's core count).
    spparks_mpi_ranks: int = 4
    # Pre-baked DAMASK snapshot (crystal-plasticity FFT solver via conda-forge
    # damask-grid + python-damask; built once by compute/snapshots/damask.py).
    # No runtime self-bootstrap — the ~3 GB conda env makes the snapshot
    # mandatory for the CPFEM stress-strain feature.
    daytona_snapshot_damask: str = ""

    # ── Transactional email (job-complete notifications) ─────────────
    # Dark by default: when MAILTRAP_API_TOKEN is blank the notifier is a
    # no-op (logged), like the Daytona + LeilAI-5 gates.  Uses Mailtrap to
    # match the rest of the Leil stack (LeilAI-5 sends from the same token /
    # hello@leil.xyz sender), so a single Mailtrap account covers everything.
    mailtrap_api_token: str = ""
    # Blank by default: a self-hosted instance has no verified sender domain, and
    # the notifier skips sending (logged) when it is unset.  The hosted
    # deployment supplies its own via MAILTRAP_SENDER_EMAIL.
    mailtrap_sender_email: str = ""
    mailtrap_sender_name: str = "Leil"
    # Public app URL used to build the "view result" link in notification
    # emails and as the domain shown in PDF report footers.  Neutral default;
    # the hosted deployment sets PUBLIC_APP_URL.
    public_app_url: str = "http://localhost:4000"

    # ── Cross-origin access ──────────────────────────────────────────
    # Comma-separated browser origins allowed to call this API WITH credentials.
    # Local development only by default: a self-hosted instance must not trust
    # someone else's domains (the previous hardcoded list trusted the hosted
    # product's origins on every installation).  Set CORS_ORIGINS explicitly.
    cors_origins: str = "http://localhost:3000,http://localhost:4000"


settings = Settings()


def cors_origin_list(raw: str) -> list[str]:
    """Parse a comma-separated origin list; tolerant of spaces and trailing commas.

    ``*`` is deliberately rejected: the API is configured with
    ``allow_credentials=True``, and a wildcard origin combined with credentials
    is both disallowed by browsers and an invitation to misconfiguration.
    """
    origins = [o.strip().rstrip("/") for o in (raw or "").split(",") if o.strip()]
    return [o for o in origins if o != "*"]
