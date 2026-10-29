from app.config import Settings


def test_production_fails_closed_without_credentials() -> None:
    settings = Settings(
        app_env="production",
        demo_mode=False,
        telegram_adapter="live",
        llm_adapter="openai",
        auth_adapter="supabase",
        database_url="postgresql+psycopg://education:education@localhost:5432/education_sales",
        telegram_bot_token="",
        llm_api_key="",
        supabase_jwt_secret="",
        supabase_jwt_issuer="",
    )
    try:
        settings.validate_runtime()
        raise AssertionError("production must fail closed")
    except RuntimeError as exc:
        assert "TELEGRAM_BOT_TOKEN" in str(exc) or "LLM_API_KEY" in str(exc) or "SUPABASE" in str(exc)


def test_missing_token_does_not_enable_demo_adapter() -> None:
    settings = Settings(
        app_env="demo",
        demo_mode=True,
        telegram_adapter="live",
        telegram_bot_token="",
        telegram_webhook_secret="not-a-placeholder-secret-value",
    )
    try:
        settings.validate_runtime()
        raise AssertionError("live adapter without token must fail")
    except RuntimeError as exc:
        assert "TELEGRAM_BOT_TOKEN" in str(exc)
    assert settings.telegram_adapter == "live"
    assert settings.use_demo_telegram is False


def test_demo_runtime_allows_simulated_adapters() -> None:
    settings = Settings(app_env="demo", demo_mode=True, telegram_adapter="demo", llm_adapter="demo", auth_adapter="demo")
    settings.validate_runtime()
