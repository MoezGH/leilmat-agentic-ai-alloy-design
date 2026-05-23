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


settings = Settings()
