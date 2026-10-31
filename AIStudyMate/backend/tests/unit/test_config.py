import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_documented_placeholder_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="change-me-with-at-least-32-random-characters",
        )


def test_production_accepts_non_placeholder_secret() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret_key="unit-test-only-unique-secret-0123456789abcdef",
    )
    assert settings.app_env == "production"
