import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from starlette.concurrency import run_in_threadpool

from app.db import Session
from app.models import User, Wallet

router = APIRouter(prefix="/auth", tags=["auth"])
password_hasher = PasswordHash.recommended()
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
TOKEN_LIFETIME = timedelta(minutes=30)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")
dummy_password_hash = password_hasher.hash("unused-password")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=8, max_length=128)]


class RegisterResponse(BaseModel):
    id: int
    email: EmailStr


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> RegisterResponse:
    """Create a user and their zero-balance wallet in one transaction."""
    email = str(payload.email).lower()
    password_hash = await run_in_threadpool(password_hasher.hash, payload.password)

    async with Session.begin() as session:
        statement = (
            insert(User)
            .values(email=email, password_hash=password_hash)
            .on_conflict_do_nothing(index_elements=[User.email])
            .returning(User.id)
        )
        user_id = await session.scalar(statement)

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )

        session.add(Wallet(user_id=user_id))

    return RegisterResponse(id=user_id, email=email)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def invalid_credentials() -> HTTPException:
    """Build the same unauthorized response for failed authentication."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/token")
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    """Issue a short-lived access token after verifying the password."""
    email = form.username.strip().lower()

    async with Session() as session:
        user = await session.scalar(select(User).where(User.email == email))

    stored_hash = user.password_hash if user is not None else dummy_password_hash
    valid_password = await run_in_threadpool(
        password_hasher.verify, form.password, stored_hash
    )

    if user is None or not valid_password:
        raise invalid_credentials()

    expires_at = datetime.now(timezone.utc) + TOKEN_LIFETIME
    token = jwt.encode(
        {"sub": str(user.id), "exp": expires_at},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return TokenResponse(access_token=token)

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """Verify the token and load its user from the database."""
    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise invalid_credentials() from None

    async with Session() as session:
        user = await session.get(User, user_id)

    if user is None:
        raise invalid_credentials()

    return user

async def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Allow the request only if the authenticated user is an admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )


class CurrentUserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str


@router.get("/me")
async def read_me(
    user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    """Return the profile of the authenticated user."""
    return CurrentUserResponse(id=user.id, email=user.email, role=user.role)
