from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_username_or_email(self, identifier: str) -> User | None:
        normalized = identifier.strip().lower()
        statement = select(User).where(
            or_(User.username == normalized, User.email == normalized)
        )
        return await self.session.scalar(statement)

    async def identity_exists(self, username: str, email: str) -> bool:
        statement = select(User.id).where(or_(User.username == username, User.email == email)).limit(1)
        return await self.session.scalar(statement) is not None

    def add(self, user: User) -> None:
        self.session.add(user)
