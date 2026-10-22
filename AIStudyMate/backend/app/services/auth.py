from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.common import UserRole
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse


class IdentityAlreadyExistsError(Exception):
    """Raised when a username or email is already registered."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials or a refresh token are invalid."""


class InactiveUserError(Exception):
    """Raised when an inactive account attempts authentication."""


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(self, data: RegisterRequest) -> User:
        if await self.users.identity_exists(data.username, str(data.email)):
            raise IdentityAlreadyExistsError

        user = User(
            username=data.username,
            email=str(data.email),
            hashed_password=await run_in_threadpool(hash_password, data.password),
            full_name=data.full_name,
            role=UserRole.STUDENT,
        )
        self.users.add(user)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise IdentityAlreadyExistsError from exc
        await self.session.refresh(user)
        return user

    async def authenticate(self, identifier: str, password: str) -> User:
        user = await self.users.get_by_username_or_email(identifier)
        if user is None:
            raise InvalidCredentialsError
        password_is_valid = await run_in_threadpool(verify_password, password, user.hashed_password)
        if not password_is_valid:
            raise InvalidCredentialsError
        if not user.is_active:
            raise InactiveUserError
        return user

    def issue_token_pair(self, user: User) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user.id, user.role),
            refresh_token=create_refresh_token(user.id, user.role),
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token, TokenType.REFRESH)
            user_id = UUID(payload["sub"])
        except (InvalidTokenError, ValueError) as exc:
            raise InvalidCredentialsError from exc

        user = await self.users.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError
        if not user.is_active:
            raise InactiveUserError
        return self.issue_token_pair(user)
