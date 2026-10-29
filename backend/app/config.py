from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"


def default_sqlite_url() -> str:
    db_path = (DATA_DIR / "education_sales_demo.db").resolve()
    return "sqlite+pysqlite:///" + db_path.as_posix()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", Path(".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "demo"
    demo_mode: bool = True
    log_level: str = "INFO"
    database_url: str = Field(default_factory=default_sqlite_url)
    public_api_url: str = "http://localhost:8000"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    jwt_secret: str = "change-me-in-any-non-demo-environment"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    demo_operator_email: str = "operador@demo.local"
    demo_operator_password: str = "demo-operador"
    demo_operator_name: str = "Operador Demo"
    demo_operator_b_email: str = "operador-b@demo.local"
    demo_operator_b_password: str = "demo-operador-b"
    demo_operator_b_name: str = "Operadora Beta"

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = "change-me-webhook-secret"
    telegram_adapter: str = "demo"

    llm_adapter: str = "demo"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = 20
    llm_max_output_tokens: int = 500

    auth_adapter: str = "demo"

    max_history_messages: int = 12
    max_input_chars: int = 4000
    max_output_chars: int = 1200

    worker_id: str = "worker-local"
    job_lease_seconds: int = 45
    job_poll_seconds: float = 0.4
    job_max_attempts: int = 5
    embed_worker: bool = True

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_issuer: str = ""
    supabase_service_role_key: str = ""

    timezone_name: str = "America/Guayaquil"

    @property
    def allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def use_demo_telegram(self) -> bool:
        return self.telegram_adapter == "demo"

    @property
    def use_demo_llm(self) -> bool:
        return self.llm_adapter == "demo"

    @property
    def use_demo_auth(self) -> bool:
        return self.auth_adapter == "demo"

    def validate_runtime(self) -> None:
        """Fail closed. Missing tokens never silently enable demo adapters."""
        known_telegram = {"demo", "live"}
        known_llm = {"demo", "openai"}
        known_auth = {"demo", "supabase"}
        if self.telegram_adapter not in known_telegram:
            raise RuntimeError(f"Unknown TELEGRAM_ADAPTER={self.telegram_adapter}")
        if self.llm_adapter not in known_llm:
            raise RuntimeError(f"Unknown LLM_ADAPTER={self.llm_adapter}")
        if self.auth_adapter not in known_auth:
            raise RuntimeError(f"Unknown AUTH_ADAPTER={self.auth_adapter}")

        if self.is_production:
            if self.demo_mode:
                raise RuntimeError("DEMO_MODE must be false when APP_ENV=production")
            if self.telegram_adapter == "demo" or self.llm_adapter == "demo" or self.auth_adapter == "demo":
                raise RuntimeError("Demo adapters are not allowed when APP_ENV=production")
            if self.is_sqlite:
                raise RuntimeError("SQLite is not allowed when APP_ENV=production")

        if self.telegram_adapter == "live":
            if not self.telegram_bot_token:
                raise RuntimeError("TELEGRAM_BOT_TOKEN is required when TELEGRAM_ADAPTER=live")
            if not self.telegram_webhook_secret or self.telegram_webhook_secret.startswith("change-me"):
                raise RuntimeError("TELEGRAM_WEBHOOK_SECRET must be set for the live Telegram adapter")

        if self.llm_adapter == "openai" and not self.llm_api_key:
            raise RuntimeError("LLM_API_KEY is required when LLM_ADAPTER=openai")

        if self.auth_adapter == "supabase":
            if not self.supabase_jwt_secret:
                raise RuntimeError("SUPABASE_JWT_SECRET is required when AUTH_ADAPTER=supabase")
            if not self.supabase_jwt_issuer:
                raise RuntimeError("SUPABASE_JWT_ISSUER is required when AUTH_ADAPTER=supabase")
            if not self.supabase_jwt_audience:
                raise RuntimeError("SUPABASE_JWT_AUDIENCE is required when AUTH_ADAPTER=supabase")

        if not self.demo_mode and self.auth_adapter == "demo":
            if not self.jwt_secret or self.jwt_secret.startswith("change-me"):
                raise RuntimeError("JWT_SECRET must be replaced when DEMO_MODE is false")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    get_settings.cache_clear()
