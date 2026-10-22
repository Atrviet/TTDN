import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import get_db_session
from app.main import app
from app.models.user import User


TEST_USERNAME = "auth_integration_user"
TEST_EMAIL = "auth.integration@example.com"
TEST_PASSWORD = "SecurePassword123"


def get_safe_test_database_url() -> str:
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    parsed_test_url = make_url(test_url)
    development_url = os.getenv("DATABASE_URL")
    if parsed_test_url.get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    if not parsed_test_url.database or "test" not in parsed_test_url.database.lower():
        pytest.fail("TEST_DATABASE_URL database name must contain 'test'")
    if development_url and make_url(development_url) == parsed_test_url:
        pytest.fail("TEST_DATABASE_URL must differ from DATABASE_URL")
    return test_url


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_login_refresh_and_protected_endpoint() -> None:
    engine = create_async_engine(get_safe_test_database_url())
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    async with session_factory() as cleanup_session:
        await cleanup_session.execute(delete(User).where(User.username == TEST_USERNAME))
        await cleanup_session.commit()

    app.dependency_overrides[get_db_session] = override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            unauthorized = await client.get("/api/v1/users/me")
            assert unauthorized.status_code == 401

            registration = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": TEST_USERNAME.upper(),
                    "email": TEST_EMAIL.upper(),
                    "password": TEST_PASSWORD,
                    "full_name": "  Auth   Integration  ",
                },
            )
            assert registration.status_code == 201
            assert registration.json()["username"] == TEST_USERNAME
            assert registration.json()["email"] == TEST_EMAIL
            assert registration.json()["full_name"] == "Auth Integration"
            assert registration.json()["role"] == "student"
            assert "hashed_password" not in registration.json()

            duplicate = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": TEST_USERNAME,
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                    "full_name": "Duplicate User",
                },
            )
            assert duplicate.status_code == 409

            invalid_login = await client.post(
                "/api/v1/auth/login",
                data={"username": TEST_USERNAME, "password": "WrongPassword123"},
            )
            assert invalid_login.status_code == 401

            login = await client.post(
                "/api/v1/auth/login",
                data={"username": TEST_USERNAME, "password": TEST_PASSWORD},
            )
            assert login.status_code == 200
            tokens = login.json()
            assert tokens["token_type"] == "bearer"

            profile = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            assert profile.status_code == 200
            assert profile.json()["email"] == TEST_EMAIL

            refresh_as_access = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
            )
            assert refresh_as_access.status_code == 401

            refreshed = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": tokens["refresh_token"]},
            )
            assert refreshed.status_code == 200
            assert refreshed.json()["access_token"] != tokens["access_token"]

            access_as_refresh = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": tokens["access_token"]},
            )
            assert access_as_refresh.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        async with session_factory() as cleanup_session:
            await cleanup_session.execute(delete(User).where(User.username == TEST_USERNAME))
            await cleanup_session.commit()
        await engine.dispose()
