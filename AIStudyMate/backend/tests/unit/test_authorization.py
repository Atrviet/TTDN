from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.dependencies.auth import require_roles
from app.models.common import UserRole
from app.models.user import User


def make_user(role: UserRole) -> User:
    return User(
        id=uuid4(),
        username=f"{role.value}_user",
        email=f"{role.value}@example.com",
        hashed_password="not-used",
        full_name="Test User",
        role=role,
    )


@pytest.mark.asyncio
async def test_admin_role_is_allowed() -> None:
    admin = make_user(UserRole.ADMIN)

    assert await require_roles(UserRole.ADMIN)(admin) is admin


@pytest.mark.asyncio
async def test_student_role_is_forbidden_from_admin_dependency() -> None:
    student = make_user(UserRole.STUDENT)

    with pytest.raises(HTTPException) as error:
        await require_roles(UserRole.ADMIN)(student)

    assert error.value.status_code == 403

