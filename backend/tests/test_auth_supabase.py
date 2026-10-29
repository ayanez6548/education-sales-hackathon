from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import Settings
from app.security import decode_supabase_token, has_operator_role


def _settings() -> Settings:
    return Settings(
        auth_adapter="supabase",
        supabase_jwt_secret="supabase-test-secret",
        supabase_jwt_audience="authenticated",
        supabase_jwt_issuer="https://example.supabase.co/auth/v1",
    )


def test_supabase_token_requires_audience_and_issuer() -> None:
    settings = _settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "user-1",
        "aud": "authenticated",
        "iss": "https://example.supabase.co/auth/v1",
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "role": "authenticated",
    }
    token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
    decoded = decode_supabase_token(settings, token)
    assert decoded["sub"] == "user-1"

    no_aud = dict(payload)
    no_aud.pop("aud")
    bad = jwt.encode(no_aud, settings.supabase_jwt_secret, algorithm="HS256")
    try:
        decode_supabase_token(settings, bad)
        raise AssertionError("tokens without aud must be rejected")
    except ValueError:
        pass

    wrong_iss = dict(payload)
    wrong_iss["iss"] = "https://evil.example/issuer"
    bad_iss = jwt.encode(wrong_iss, settings.supabase_jwt_secret, algorithm="HS256")
    try:
        decode_supabase_token(settings, bad_iss)
        raise AssertionError("tokens with wrong issuer must be rejected")
    except ValueError:
        pass


def test_operator_role_is_database_gated() -> None:
    assert has_operator_role("operator")
    assert has_operator_role("admin")
    assert not has_operator_role("authenticated")
    assert not has_operator_role("anon")
    assert not has_operator_role("")
