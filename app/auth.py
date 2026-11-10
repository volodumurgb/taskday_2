from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.dialects.postgresql import insert
from starlette.concurrency import run_in_threadpool

from app.db import Session
from app.models import User, Wallet

router = APIRouter(prefix="/auth", tags=["auth"])
password_hasher = PasswordHash.recommended()


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